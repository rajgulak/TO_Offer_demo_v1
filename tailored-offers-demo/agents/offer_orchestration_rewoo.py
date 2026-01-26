"""
Offer Orchestration Agent - Proper LangGraph ReWOO Implementation

This module implements the ReWOO (Reasoning without Observation) pattern
as a proper LangGraph sub-graph with separate Planner, Worker, and Solver nodes.

How it works:
1. PLANNER (Node 1): LLM analyzes customer data and creates a plan of evaluations
   - Outputs: List of evaluation steps with #E variables (E1, E2, E3...)
   - Single LLM call to generate complete plan upfront

2. WORKER (Node 2): Executes each evaluation step from the plan
   - Iterates through plan steps
   - Executes tools/evaluations for each step
   - Stores results with #E variable substitution

3. SOLVER (Node 3): Synthesizes all results into final decision
   - Takes all evidence from Worker
   - Makes final offer selection
   - Single LLM call for synthesis

Key Benefits:
- Streaming: Each node emits events as it completes
- Efficiency: Only 2-3 LLM calls total (vs. N calls in ReAct)
- Transparency: Clear separation of planning, execution, synthesis
"""
from typing import Dict, Any, List, Optional, Literal, Generator
import json
import re
import os
from dataclasses import dataclass, field, asdict

from langgraph.graph import StateGraph, START, END

from .state import ReWOOState, ReWOOPlanStep, ReWOOStepResult, create_rewoo_state
from .llm_service import get_llm, is_llm_available

# Import prompt service for dynamic prompt loading
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.prompt_service import get_planner_prompt, get_solver_prompt
from config.policy_config import get_policy


def get_live_policy(key: str, default: Any = None) -> Any:
    """Get a policy value from PolicyService (live, not cached)."""
    try:
        value = get_policy(key)
        return value if value is not None else default
    except Exception:
        return default


# =============================================================================
# Configuration
# =============================================================================

def load_discount_policies() -> Dict[str, Any]:
    """Load pre-approved discount policies from configuration."""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "config",
        "discount_policies.json"
    )
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "policies": {
                "GOODWILL_RECOVERY": {"discount_percent": 10, "policy_id": "POL-GW-001"},
                "PRICE_SENSITIVE_HIGH": {"discount_percent": 15, "policy_id": "POL-PS-001"},
                "PRICE_SENSITIVE_MEDIUM": {"discount_percent": 5, "policy_id": "POL-PS-002"},
                "NO_DISCOUNT": {"discount_percent": 0, "policy_id": "POL-ND-001"}
            },
            "segment_caps": {}
        }


DISCOUNT_POLICIES = load_discount_policies()

# Offer configuration
OFFER_CONFIG = {
    "business": {
        "offer_type": "IU_BUSINESS",
        "display_name": "Business Class",
        "base_margin": 0.90,
        "max_discount": 0.20,
        "price_key": "iu_business_price"
    },
    "premium_economy": {
        "offer_type": "IU_PREMIUM_ECONOMY",
        "display_name": "Premium Economy",
        "base_margin": 0.85,
        "max_discount": 0.15,
        "price_key": "iu_premium_economy_price"
    },
    "main_cabin_extra": {
        "offer_type": "MCE",
        "display_name": "Main Cabin Extra",
        "base_margin": 0.85,
        "max_discount": 0.10,
        "price_key": "mce_price"
    }
}

CABIN_CODE_MAP = {
    "F": "business",
    "W": "premium_economy",
    "MCE": "main_cabin_extra"
}


# =============================================================================
# LLM Prompts
# =============================================================================

PLANNER_PROMPT = """You are the Planner in a ReWOO agent for airline offer optimization.

Your job is to analyze customer data and create a plan of what to evaluate before deciding which upgrade offer to give.

Available evaluation types:
- CONFIDENCE: Check ML model confidence for each offer
- RELATIONSHIP: Check if customer had recent service issues
- PRICE_SENSITIVITY: Check if customer needs a discount
- INVENTORY: Check which cabins need to be filled
- RECENT_DISRUPTIONS: Check if customer had recent delays or cancellations (only if instructed)

Create a plan with numbered steps like E1, E2, E3. Each step should check ONE thing.
Only include steps that are relevant for this specific customer.

Output format (JSON):
```json
{
  "steps": [
    {"step_id": "E1", "evaluation_type": "CONFIDENCE", "description": "Check ML confidence for each offer"},
    {"step_id": "E2", "evaluation_type": "RELATIONSHIP", "description": "Check for recent service issues"}
  ],
  "reasoning": "Why I chose these steps"
}
```"""

SOLVER_PROMPT = """You are the Solver in a ReWOO agent for airline offer optimization.

The Planner created a plan and the Worker executed all evaluations. Now you have all the evidence.

Your job is to synthesize the evidence and make the final offer decision.

Consider:
- If confidence is low on expensive offers, choose a safer option
- If customer had recent issues, apply goodwill discount if policy allows
- If customer is price sensitive, apply appropriate discount per policy

Output format (JSON):
```json
{
  "selected_offer": "IU_BUSINESS" or "MCE" or "IU_PREMIUM_ECONOMY",
  "reasoning": "How I synthesized the evidence to reach this decision",
  "key_factors": ["factor1", "factor2"]
}
```"""


# Combined prompt for API exposure
ORCHESTRATION_SYSTEM_PROMPT = f"""
Offer Orchestration Agent - ReWOO Pattern

This agent uses the ReWOO (Reasoning without Observation) pattern:

=== STEP 1: PLANNER ===
{PLANNER_PROMPT}

=== STEP 2: WORKER ===
Execute each evaluation step from the plan.

=== STEP 3: SOLVER ===
{SOLVER_PROMPT}
"""


# =============================================================================
# Helper Functions
# =============================================================================

def build_offer_options(state: ReWOOState) -> List[Dict[str, Any]]:
    """Build offer options from state data."""
    customer = state.get("customer_data", {})
    flight = state.get("flight_data", {})
    ml_scores = state.get("ml_scores", {})
    inventory = state.get("inventory_status", {})
    recommended_cabins = state.get("recommended_cabins", [])

    propensity_scores = ml_scores.get("propensity_scores", {}) if ml_scores else {}
    product_catalog = flight.get("product_catalog", {}) if flight else {}

    offer_options = []
    for cabin_code in recommended_cabins:
        config_key = CABIN_CODE_MAP.get(cabin_code, cabin_code)
        config = OFFER_CONFIG.get(config_key)
        if not config:
            continue

        offer_type = config["offer_type"]
        score_data = propensity_scores.get(offer_type, {})

        # Get best price point
        price_points = score_data.get("price_points", {})
        if price_points:
            best_ev = 0
            best_price = 0
            best_p_buy = 0.3
            for price_str, info in price_points.items():
                price = int(price_str)
                p_buy = info.get("p_buy", 0.3)
                ev = p_buy * price * config["base_margin"]
                if ev > best_ev:
                    best_ev = ev
                    best_price = price
                    best_p_buy = p_buy
        else:
            price_key = config.get("price_key", "")
            best_price = product_catalog.get(price_key, 0) or 199
            best_p_buy = 0.3
            best_ev = best_p_buy * best_price * config["base_margin"]

        confidence = score_data.get("confidence", 0.5)

        offer_options.append({
            "cabin": cabin_code,
            "offer_type": offer_type,
            "display_name": config["display_name"],
            "p_buy": best_p_buy,
            "confidence": confidence,
            "price": best_price,
            "margin": config["base_margin"],
            "expected_value": best_ev,
            "max_discount": config["max_discount"],
            "inventory_priority": inventory.get(cabin_code, {}).get("priority", "medium")
        })

    return offer_options


def extract_json(text: str) -> Optional[Dict]:
    """Extract JSON from LLM response."""
    try:
        match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        return json.loads(text)
    except:
        return None


# =============================================================================
# ReWOO Node Functions
# =============================================================================

def planner_node(state: ReWOOState) -> Dict[str, Any]:
    """
    PLANNER NODE: Analyze context and create evaluation plan.

    This runs ONCE and produces a complete plan with all steps.
    """
    # Build offer options from context
    offer_options = build_offer_options(state)

    if not offer_options:
        return {
            "plan": [],
            "plan_reasoning": "No offer options available - skipping planning",
            "offer_options": [],
            "should_send_offer": False,
        }

    customer = state.get("customer_data", {})
    ml_scores = state.get("ml_scores", {})

    # Build planner input
    tier_names = {"E": "Executive Platinum", "T": "Platinum Pro", "P": "Platinum", "G": "Gold"}
    tier_display = tier_names.get(customer.get("loyalty_tier", ""), "General")

    service_recovery = customer.get("recent_service_recovery", {})

    planner_input = f"""
Customer: {customer.get('first_name', '')} {customer.get('last_name', '')}
- Loyalty Tier: {tier_display}
- Annual Revenue: ${customer.get('flight_revenue_amt_history', 0):,}
- Has Recent Service Issue: {service_recovery.get('had_issue', False)}
- Price Sensitivity: {ml_scores.get('price_sensitivity', 'medium') if ml_scores else 'medium'}

Available Offers:
"""
    for opt in offer_options:
        conf_label = '(LOW!)' if opt['confidence'] < 0.6 else '(HIGH)' if opt['confidence'] > 0.85 else ''
        planner_input += f"""
- {opt['display_name']}:
  - P(buy): {opt['p_buy']:.0%}
  - ML Confidence: {opt['confidence']:.0%} {conf_label}
  - Price: ${opt['price']}
  - Expected Value: ${opt['expected_value']:.2f}
"""

    planner_input += "\nCreate an evaluation plan for this offer decision."

    # Generate plan
    steps = []
    plan_reasoning = ""

    if is_llm_available():
        try:
            from langchain_core.messages import SystemMessage, HumanMessage

            # Get the active planner prompt (custom if set, otherwise default)
            active_planner_prompt = get_planner_prompt()

            llm = get_llm(temperature=0.3)
            response = llm.invoke([
                SystemMessage(content=active_planner_prompt),
                HumanMessage(content=planner_input)
            ])

            plan_json = extract_json(response.content)
            if plan_json and "steps" in plan_json:
                for s in plan_json["steps"]:
                    steps.append(ReWOOPlanStep(
                        step_id=s.get("step_id", f"E{len(steps)+1}"),
                        evaluation_type=s.get("evaluation_type", "UNKNOWN"),
                        description=s.get("description", ""),
                        depends_on=s.get("depends_on", [])
                    ))
                plan_reasoning = plan_json.get("reasoning", "LLM generated plan")

        except Exception as e:
            plan_reasoning = f"LLM planning failed: {e}, using default plan"

    # Default plan if LLM fails or unavailable
    if not steps:
        steps = _create_default_plan(offer_options, customer, ml_scores)

        # Generate data-driven reasoning
        customer_name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip() or "Customer"
        revenue = customer.get("flight_revenue_amt_history", 0)
        tier = tier_display
        service_recovery = customer.get("recent_service_recovery", {})
        sensitivity = ml_scores.get("price_sensitivity", "medium") if ml_scores else "medium"

        # Build reasoning from actual data
        reasoning_parts = [f"Analyzing {customer_name} ({tier}, ${revenue:,}/yr revenue)"]

        # Add confidence observations
        low_conf = [o for o in offer_options if o['confidence'] < 0.6]
        high_conf = [o for o in offer_options if o['confidence'] > 0.85]
        if low_conf and high_conf:
            reasoning_parts.append(
                f"ML shows confidence gap: {low_conf[0]['display_name']}={low_conf[0]['confidence']:.0%} vs "
                f"{high_conf[0]['display_name']}={high_conf[0]['confidence']:.0%}"
            )

        # Add service recovery if applicable
        if service_recovery.get("had_issue"):
            reasoning_parts.append(f"Customer had recent {service_recovery.get('issue_type', 'issue')}")

        # Add price sensitivity
        if sensitivity != "low":
            reasoning_parts.append(f"Price sensitivity: {sensitivity}")

        plan_reasoning = ". ".join(reasoning_parts)

    return {
        "plan": steps,
        "plan_reasoning": plan_reasoning,
        "offer_options": offer_options,
        "current_step_index": 0,
        "step_results": {},
    }


def _create_default_plan(
    offer_options: List[Dict],
    customer: Dict,
    ml_scores: Dict
) -> List[ReWOOPlanStep]:
    """Create a default evaluation plan based on context with data-driven descriptions."""
    steps = []

    # Build confidence summary for description
    conf_summary = ", ".join([
        f"{o['display_name']}={o['confidence']:.0%}"
        for o in offer_options
    ])

    # Always evaluate confidence if multiple offers
    if len(offer_options) > 1:
        low_conf_offers = [o for o in offer_options if o['confidence'] < 0.6]
        high_conf_offers = [o for o in offer_options if o['confidence'] > 0.85]

        if low_conf_offers or high_conf_offers:
            low_names = [o['display_name'] for o in low_conf_offers]
            high_names = [o['display_name'] for o in high_conf_offers]

            if low_conf_offers and high_conf_offers:
                desc = f"ML shows {', '.join(low_names)} has LOW confidence vs {', '.join(high_names)} HIGH - need to evaluate risk"
            elif low_conf_offers:
                desc = f"ML confidence is LOW for {', '.join(low_names)} ({low_conf_offers[0]['confidence']:.0%}) - check if acceptable"
            else:
                desc = f"ML confidence is HIGH for {', '.join(high_names)} - verify no concerns"

            steps.append(ReWOOPlanStep(
                step_id="E1",
                description=desc,
                evaluation_type="CONFIDENCE"
            ))

    # Check relationship if recent issue
    service_recovery = customer.get("recent_service_recovery", {})
    if service_recovery.get("had_issue"):
        issue_type = service_recovery.get("issue_type", "service issue")
        customer_name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip() or "Customer"
        revenue = customer.get("flight_revenue_amt_history", 0)

        steps.append(ReWOOPlanStep(
            step_id=f"E{len(steps)+1}",
            description=f"{customer_name} (${revenue:,}/yr) had recent {issue_type} - check if goodwill discount applies",
            evaluation_type="RELATIONSHIP"
        ))

    # Check price sensitivity
    sensitivity = ml_scores.get("price_sensitivity", "medium") if ml_scores else "medium"
    if sensitivity in ["high", "medium"]:
        steps.append(ReWOOPlanStep(
            step_id=f"E{len(steps)+1}",
            description=f"Price sensitivity is '{sensitivity}' - check discount policy",
            evaluation_type="PRICE_SENSITIVITY"
        ))

    # If no trade-offs detected, just evaluate EV
    if not steps:
        best_ev = max(offer_options, key=lambda x: x['expected_value'])
        steps.append(ReWOOPlanStep(
            step_id="E1",
            description=f"No trade-offs detected - {best_ev['display_name']} has highest EV (${best_ev['expected_value']:.2f})",
            evaluation_type="EV_COMPARISON"
        ))

    return steps


def worker_node(state: ReWOOState) -> Dict[str, Any]:
    """
    WORKER NODE: Execute ONE step from the plan.

    This node is called repeatedly via conditional routing until all steps are done.
    Each invocation executes the next step in the plan.
    """
    plan = state.get("plan", [])
    current_index = state.get("current_step_index", 0)
    step_results = dict(state.get("step_results", {}))
    offer_options = state.get("offer_options", [])
    customer = state.get("customer_data", {})
    ml_scores = state.get("ml_scores", {})

    if current_index >= len(plan):
        # All steps done
        return {"current_step_index": current_index}

    step = plan[current_index]

    # Execute the evaluation based on type
    if step.evaluation_type == "CONFIDENCE":
        result = _evaluate_confidence(offer_options)
    elif step.evaluation_type == "RELATIONSHIP":
        result = _evaluate_relationship(customer)
    elif step.evaluation_type == "PRICE_SENSITIVITY":
        result = _evaluate_price_sensitivity(ml_scores)
    elif step.evaluation_type == "INVENTORY":
        result = _evaluate_inventory(offer_options)
    elif step.evaluation_type == "RECENT_DISRUPTIONS":
        result = _evaluate_recent_disruptions(customer)
    else:  # EV_COMPARISON or default
        result = _evaluate_ev(offer_options)

    # Store result
    step_result = ReWOOStepResult(
        step_id=step.step_id,
        evaluation_type=step.evaluation_type,
        result=result,
        recommendation=result.get("recommendation", ""),
        reasoning=result.get("reasoning", "")
    )
    step_results[step.step_id] = step_result

    return {
        "step_results": step_results,
        "current_step_index": current_index + 1,
    }


def _evaluate_confidence(offer_options: List[Dict]) -> Dict[str, Any]:
    """Evaluate ML confidence for each offer with explicit data references.

    Uses live policy values for thresholds.
    """
    # Get live policy values
    min_confidence = get_live_policy("min_confidence_threshold", 0.6)
    high_confidence = get_live_policy("high_confidence_threshold", 0.8)
    if not offer_options:
        return {"recommendation": "NO_DATA", "reasoning": "No offers to evaluate"}

    best_ev_offer = max(offer_options, key=lambda x: x['expected_value'])
    best_conf_offer = max(offer_options, key=lambda x: x['confidence'])

    # Build detailed confidence breakdown
    conf_breakdown = " | ".join([
        f"{o['display_name']}: {o['confidence']:.0%} conf, ${o['expected_value']:.0f} EV"
        for o in sorted(offer_options, key=lambda x: -x['expected_value'])
    ])

    result = {
        "best_ev_offer": best_ev_offer['offer_type'],
        "best_ev": best_ev_offer['expected_value'],
        "best_ev_confidence": best_ev_offer['confidence'],
        "safest_offer": best_conf_offer['offer_type'],
        "safest_confidence": best_conf_offer['confidence'],
        "safest_ev": best_conf_offer['expected_value'],
        "confidence_breakdown": conf_breakdown,
    }

    if best_ev_offer['confidence'] < min_confidence and best_conf_offer['confidence'] > high_confidence:
        ev_gap = best_ev_offer['expected_value'] - best_conf_offer['expected_value']
        conf_gap = best_conf_offer['confidence'] - best_ev_offer['confidence']

        result["recommendation"] = "CHOOSE_SAFER"
        result["reasoning"] = (
            f"⚠️ CONFIDENCE TRADE-OFF DETECTED:\n"
            f"   • {best_ev_offer['display_name']}: EV=${best_ev_offer['expected_value']:.0f} but only {best_ev_offer['confidence']:.0%} confident\n"
            f"   • {best_conf_offer['display_name']}: EV=${best_conf_offer['expected_value']:.0f} with {best_conf_offer['confidence']:.0%} confident\n"
            f"   → Giving up ${ev_gap:.0f} EV for +{conf_gap:.0%} confidence\n"
            f"   → DECISION: Choose {best_conf_offer['display_name']} (safer bet)"
        )
    else:
        result["recommendation"] = "PROCEED_WITH_BEST_EV"
        result["reasoning"] = (
            f"✓ No confidence concern:\n"
            f"   • {best_ev_offer['display_name']}: EV=${best_ev_offer['expected_value']:.0f} @ {best_ev_offer['confidence']:.0%} confidence\n"
            f"   → Confidence acceptable, proceed with highest EV"
        )

    return result


def _evaluate_relationship(customer: Dict) -> Dict[str, Any]:
    """Evaluate customer relationship and service history with explicit data."""
    service_recovery = customer.get("recent_service_recovery", {})
    annual_revenue = customer.get("flight_revenue_amt_history", 0)
    customer_name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip() or "Customer"
    tier = customer.get("loyalty_tier", "N")
    tier_names = {"E": "Executive Platinum", "T": "Platinum Pro", "P": "Platinum", "G": "Gold", "N": "General"}

    # Get live policy value (overrides JSON config)
    goodwill_percent = get_live_policy("goodwill_discount_percent", 10)
    policy_id = "POL-GW-001"
    policy_discount = goodwill_percent / 100

    result = {
        "has_recent_issue": service_recovery.get("had_issue", False),
        "issue_type": service_recovery.get("issue_type"),
        "sentiment": service_recovery.get("customer_sentiment"),
        "annual_revenue": annual_revenue,
        "goodwill_discount": 0,
        "policy_applied": None,
        "customer_name": customer_name,
        "tier": tier_names.get(tier, "General"),
    }

    # Get VIP threshold from policy
    vip_threshold = get_live_policy("vip_revenue_threshold", 5000)
    if result["has_recent_issue"] and annual_revenue > vip_threshold:
        result["recommendation"] = "APPLY_GOODWILL_DISCOUNT"
        result["goodwill_discount"] = policy_discount
        result["policy_applied"] = policy_id
        result["reasoning"] = (
            f"🎯 RELATIONSHIP RECOVERY TRIGGERED:\n"
            f"   • Customer: {customer_name} ({tier_names.get(tier, 'General')})\n"
            f"   • Annual Revenue: ${annual_revenue:,} (HIGH VALUE)\n"
            f"   • Recent Issue: {result['issue_type']}\n"
            f"   • Sentiment: {result['sentiment'] or 'frustrated'}\n"
            f"   → Policy [{policy_id}] applies: {policy_discount:.0%} goodwill discount\n"
            f"   → DECISION: Apply discount to rebuild relationship"
        )
    elif result["has_recent_issue"]:
        result["recommendation"] = "PROCEED_WITH_CAUTION"
        result["reasoning"] = (
            f"⚠️ Customer Issue (Lower Value):\n"
            f"   • Customer: {customer_name}\n"
            f"   • Annual Revenue: ${annual_revenue:,} (below ${vip_threshold:,} threshold)\n"
            f"   • Recent Issue: {result['issue_type']}\n"
            f"   → No automatic goodwill discount, but proceed carefully"
        )
    else:
        result["recommendation"] = "NO_CONCERN"
        result["reasoning"] = (
            f"✓ Relationship OK:\n"
            f"   • Customer: {customer_name} ({tier_names.get(tier, 'General')})\n"
            f"   • No recent service issues\n"
            f"   → No relationship-based adjustments needed"
        )

    return result


def _evaluate_recent_disruptions(customer: Dict) -> Dict[str, Any]:
    """Evaluate if customer had recent flight disruptions (delays, cancellations).

    This is an OPTIONAL evaluation - only checked if explicitly instructed via prompt.
    By default, the planner does NOT include this step, demonstrating how gaps can occur.
    """
    recent_disruption = customer.get("recent_disruption", {})
    customer_name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip() or "Customer"
    tier = customer.get("loyalty_tier", "N")
    tier_names = {"E": "Executive Platinum", "T": "Platinum Pro", "P": "Platinum", "G": "Gold", "N": "General"}

    result = {
        "has_disruption": recent_disruption.get("had_disruption", False),
        "disruption_type": recent_disruption.get("disruption_type"),
        "delay_minutes": recent_disruption.get("delay_minutes", 0),
        "disruption_date": recent_disruption.get("disruption_date"),
        "flight_number": recent_disruption.get("flight_number"),
        "route": recent_disruption.get("route"),
        "compensation_offered": recent_disruption.get("compensation_offered", False),
        "customer_name": customer_name,
        "tier": tier_names.get(tier, "General"),
        "goodwill_discount": 0,
        "policy_applied": None,
    }

    if result["has_disruption"]:
        delay_mins = result["delay_minutes"]

        # Determine goodwill discount based on delay severity
        if delay_mins >= 180:  # 3+ hours
            goodwill_percent = get_live_policy("disruption_goodwill_percent", 20)
            policy_id = "POL-DISRUPT-001"
        elif delay_mins >= 60:  # 1-3 hours
            goodwill_percent = get_live_policy("disruption_goodwill_percent", 15)
            policy_id = "POL-DISRUPT-002"
        else:
            goodwill_percent = get_live_policy("disruption_goodwill_percent", 10)
            policy_id = "POL-DISRUPT-003"

        result["goodwill_discount"] = goodwill_percent / 100
        result["policy_applied"] = policy_id
        result["recommendation"] = "APPLY_DISRUPTION_GOODWILL"
        result["reasoning"] = (
            f"⚠️ RECENT DISRUPTION DETECTED:\n"
            f"   • Customer: {customer_name} ({tier_names.get(tier, 'General')})\n"
            f"   • Disruption: {delay_mins}-minute {result['disruption_type']} on {result['flight_number']}\n"
            f"   • Route: {result['route']}\n"
            f"   • Date: {result['disruption_date']}\n"
            f"   • Previous Compensation: {'Yes' if result['compensation_offered'] else 'No'}\n"
            f"   → Policy [{policy_id}] applies: {goodwill_percent}% goodwill discount\n"
            f"   → DECISION: Apply disruption recovery discount to maintain relationship"
        )
    else:
        result["recommendation"] = "NO_DISRUPTION_FOUND"
        result["reasoning"] = (
            f"✓ No recent disruptions:\n"
            f"   • Customer: {customer_name}\n"
            f"   • No delays or cancellations in recent history\n"
            f"   → Proceed with standard offer"
        )

    return result


def _evaluate_price_sensitivity(ml_scores: Dict) -> Dict[str, Any]:
    """Evaluate customer price sensitivity with explicit data."""
    sensitivity = ml_scores.get("price_sensitivity", "medium") if ml_scores else "medium"

    high_policy = DISCOUNT_POLICIES.get("policies", {}).get("PRICE_SENSITIVE_HIGH", {})
    medium_policy = DISCOUNT_POLICIES.get("policies", {}).get("PRICE_SENSITIVE_MEDIUM", {})
    no_discount_policy = DISCOUNT_POLICIES.get("policies", {}).get("NO_DISCOUNT", {})

    result = {"sensitivity_level": sensitivity}

    if sensitivity == "high":
        policy_id = high_policy.get("policy_id", "POL-PS-001")
        policy_discount = high_policy.get("discount_percent", 15) / 100
        result["recommendation"] = "APPLY_DISCOUNT"
        result["discount_percent"] = policy_discount
        result["policy_applied"] = policy_id
        result["reasoning"] = (
            f"💰 HIGH PRICE SENSITIVITY:\n"
            f"   • ML Score: price_sensitivity = '{sensitivity}'\n"
            f"   • Customer likely to reject full-price offer\n"
            f"   → Policy [{policy_id}] applies: {policy_discount:.0%} discount\n"
            f"   → DECISION: Apply discount to increase conversion"
        )
    elif sensitivity == "medium":
        policy_id = medium_policy.get("policy_id", "POL-PS-002")
        policy_discount = medium_policy.get("discount_percent", 5) / 100
        result["recommendation"] = "SMALL_DISCOUNT_OPTIONAL"
        result["discount_percent"] = policy_discount
        result["policy_applied"] = policy_id
        result["reasoning"] = (
            f"⚡ MEDIUM PRICE SENSITIVITY:\n"
            f"   • ML Score: price_sensitivity = '{sensitivity}'\n"
            f"   • Customer may respond to small discount\n"
            f"   → Policy [{policy_id}] allows: {policy_discount:.0%} optional discount\n"
            f"   → DECISION: Small discount available if needed"
        )
    else:
        policy_id = no_discount_policy.get("policy_id", "POL-ND-001")
        result["recommendation"] = "NO_DISCOUNT"
        result["discount_percent"] = 0
        result["policy_applied"] = policy_id
        result["reasoning"] = (
            f"✓ LOW PRICE SENSITIVITY:\n"
            f"   • ML Score: price_sensitivity = '{sensitivity}'\n"
            f"   • Customer likely to pay full price\n"
            f"   → Policy [{policy_id}]: No discount needed\n"
            f"   → DECISION: Offer at full price"
        )

    return result


def _evaluate_inventory(offer_options: List[Dict]) -> Dict[str, Any]:
    """Evaluate inventory priority for cabins with explicit data references."""
    high_priority = [o for o in offer_options if o.get("inventory_priority") == "high"]
    medium_priority = [o for o in offer_options if o.get("inventory_priority") == "medium"]
    low_priority = [o for o in offer_options if o.get("inventory_priority") == "low"]

    # Build detailed inventory breakdown
    inventory_breakdown = []
    for o in offer_options:
        priority = o.get("inventory_priority", "unknown")
        icon = "🔴" if priority == "high" else "🟡" if priority == "medium" else "🟢"
        inventory_breakdown.append(f"{icon} {o['display_name']}: {priority} priority")

    result = {
        "high_priority_cabins": [o["offer_type"] for o in high_priority],
        "medium_priority_cabins": [o["offer_type"] for o in medium_priority],
        "low_priority_cabins": [o["offer_type"] for o in low_priority],
        "inventory_breakdown": inventory_breakdown,
    }

    if high_priority:
        high_names = [o['display_name'] for o in high_priority]
        result["recommendation"] = "PRIORITIZE_HIGH_INVENTORY"
        result["reasoning"] = (
            f"📦 INVENTORY PRIORITY DETECTED:\n"
            f"   {chr(10).join('   • ' + line for line in inventory_breakdown)}\n"
            f"   → {', '.join(high_names)} need to be filled\n"
            f"   → DECISION: Boost {', '.join(high_names)} offers"
        )
    else:
        result["recommendation"] = "NO_PRIORITY"
        result["reasoning"] = (
            f"✓ Inventory levels normal:\n"
            f"   {chr(10).join('   • ' + line for line in inventory_breakdown)}\n"
            f"   → No urgent cabin fill needs"
        )


def _evaluate_ev(offer_options: List[Dict]) -> Dict[str, Any]:
    """Expected value comparison with explicit data references."""
    if not offer_options:
        return {"recommendation": "NO_DATA", "reasoning": "No offers available"}

    # Sort by EV descending
    sorted_offers = sorted(offer_options, key=lambda x: -x["expected_value"])
    best = sorted_offers[0]

    # Build EV breakdown for all offers
    ev_breakdown = []
    for o in sorted_offers:
        ev_formula = f"P(buy)={o['p_buy']:.0%} × ${o['price']} × margin={o['margin']:.0%}"
        ev_breakdown.append(f"{o['display_name']}: ${o['expected_value']:.0f} ({ev_formula})")

    result = {
        "best_offer": best["offer_type"],
        "best_ev": best["expected_value"],
        "best_price": best["price"],
        "best_p_buy": best["p_buy"],
        "ev_breakdown": ev_breakdown,
    }

    # Check if there's a clear winner or close competition
    if len(sorted_offers) > 1:
        second = sorted_offers[1]
        ev_gap = best["expected_value"] - second["expected_value"]
        ev_gap_pct = ev_gap / second["expected_value"] * 100 if second["expected_value"] > 0 else 100

        if ev_gap_pct < 10:  # Within 10% is close
            result["recommendation"] = "CLOSE_COMPETITION"
            result["reasoning"] = (
                f"📊 EV COMPARISON (CLOSE):\n"
                f"   {chr(10).join('   • ' + line for line in ev_breakdown)}\n"
                f"   → Gap: ${ev_gap:.0f} ({ev_gap_pct:.0f}%)\n"
                f"   → DECISION: {best['display_name']} leads, but consider other factors"
            )
        else:
            result["recommendation"] = "SELECT_HIGHEST_EV"
            result["reasoning"] = (
                f"📊 EV COMPARISON (CLEAR WINNER):\n"
                f"   {chr(10).join('   • ' + line for line in ev_breakdown)}\n"
                f"   → Gap: ${ev_gap:.0f} ({ev_gap_pct:.0f}%)\n"
                f"   → DECISION: {best['display_name']} is clear winner"
            )
    else:
        result["recommendation"] = "SELECT_HIGHEST_EV"
        result["reasoning"] = (
            f"📊 EV ANALYSIS:\n"
            f"   • {ev_breakdown[0]}\n"
            f"   → Only one offer available\n"
            f"   → DECISION: Select {best['display_name']}"
        )

    return result


def solver_node(state: ReWOOState) -> Dict[str, Any]:
    """
    SOLVER NODE: Synthesize all evidence and make final decision.

    This runs ONCE after all Worker steps complete.
    """
    offer_options = state.get("offer_options", [])
    step_results = state.get("step_results", {})
    customer = state.get("customer_data", {})
    ml_scores = state.get("ml_scores", {})

    if not offer_options:
        return {
            "selected_offer": "NONE",
            "offer_price": 0,
            "discount_applied": 0,
            "expected_value": 0,
            "solver_reasoning": "No offers available",
            "should_send_offer": False,
            "policies_applied": [],
        }

    # Get customer info for reasoning
    customer_name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip() or "Customer"
    tier = customer.get("loyalty_tier", "N")
    tier_names = {"E": "Executive Platinum", "T": "Platinum Pro", "P": "Platinum", "G": "Gold", "N": "General"}
    tier_display = tier_names.get(tier, "General")
    annual_revenue = customer.get("flight_revenue_amt_history", 0)

    # Start with best EV as default
    best_ev_offer = max(offer_options, key=lambda x: x["expected_value"])
    selected = best_ev_offer
    discount = 0
    synthesis_parts = []
    decision_factors = []
    policies_applied = []

    # Apply evaluation results
    for step_id, step_result in step_results.items():
        rec = step_result.recommendation
        result = step_result.result
        policy_id = result.get("policy_applied")

        if rec == "CHOOSE_SAFER":
            safest_type = result.get("safest_offer")
            safest = next((o for o in offer_options if o["offer_type"] == safest_type), None)
            if safest:
                ev_loss = selected["expected_value"] - safest["expected_value"]
                conf_gain = safest["confidence"] - selected["confidence"]
                selected = safest
                decision_factors.append(f"Confidence trade-off: -{ev_loss:.0f} EV for +{conf_gain:.0%} confidence")
                synthesis_parts.append(f"→ Switched to {safest['display_name']} (safer choice)")

        elif rec == "APPLY_GOODWILL_DISCOUNT":
            goodwill = result.get("goodwill_discount", 0.10)
            discount = max(discount, goodwill)
            if policy_id:
                policies_applied.append(policy_id)
                decision_factors.append(f"Goodwill recovery: {result.get('issue_type', 'service issue')}")
                synthesis_parts.append(f"→ Applied [{policy_id}]: {goodwill:.0%} goodwill discount")

        elif rec == "APPLY_DISRUPTION_GOODWILL":
            disruption_discount = result.get("goodwill_discount", 0.15)
            discount = max(discount, disruption_discount)
            policy_id = result.get("policy_applied")
            if policy_id:
                policies_applied.append(policy_id)
                delay_mins = result.get("delay_minutes", 0)
                decision_factors.append(f"Disruption recovery: {delay_mins}min delay")
                synthesis_parts.append(f"→ Applied [{policy_id}]: {disruption_discount:.0%} disruption goodwill discount")

        elif rec == "APPLY_DISCOUNT":
            price_disc = result.get("discount_percent", 0.15)
            sensitivity = result.get("sensitivity_level", "high")
            discount = max(discount, price_disc)
            if policy_id:
                policies_applied.append(policy_id)
                decision_factors.append(f"Price sensitivity: {sensitivity}")
                synthesis_parts.append(f"→ Applied [{policy_id}]: {price_disc:.0%} price sensitivity discount")

        elif rec == "PRIORITIZE_HIGH_INVENTORY":
            high_cabins = result.get("high_priority_cabins", [])
            if high_cabins:
                decision_factors.append(f"Inventory priority: {', '.join(high_cabins)}")

    # Cap discount - use live policy value
    max_discount_policy = get_live_policy("max_discount_percent", 25) / 100

    customer_segment = customer.get("segment", "mid_value_mixed")
    segment_caps = DISCOUNT_POLICIES.get("segment_caps", {})
    segment_config = segment_caps.get(customer_segment, {})
    max_segment_discount = segment_config.get("max_total_discount", 20) / 100

    config_key = CABIN_CODE_MAP.get(selected["cabin"], "business")
    config = OFFER_CONFIG.get(config_key, {})
    max_offer_discount = config.get("max_discount", 0.20)

    # Use the minimum of policy, segment, and offer limits
    max_discount = min(max_discount_policy, max_segment_discount, max_offer_discount)
    original_discount = discount
    discount = min(discount, max_discount)

    if discount < original_discount:
        synthesis_parts.append(f"→ Discount capped at {max_discount:.0%} (segment: {customer_segment})")

    # Calculate final price
    original_price = selected["price"]
    final_price = original_price * (1 - discount)
    final_ev = selected["p_buy"] * final_price * selected["margin"]

    # Build comprehensive reasoning with explicit WHY
    reasoning_lines = [
        f"🎯 WHY THIS DECISION FOR {customer_name}?",
        "",
        f"📋 CUSTOMER PROFILE:",
        f"   • Status: {tier_display}",
        f"   • Annual Revenue: ${annual_revenue:,}",
        "",
    ]

    # Explain WHY this offer was chosen
    reasoning_lines.append("🤔 WHY THIS OFFER?")
    if decision_factors:
        for factor in decision_factors:
            reasoning_lines.append(f"   → {factor}")
    else:
        # Default explanation based on offer selection
        reasoning_lines.append(f"   → {selected['display_name']} has best expected value (${selected['expected_value']:.0f})")
        reasoning_lines.append(f"   → ML confidence is {selected['confidence']:.0%} - acceptable risk level")
        reasoning_lines.append(f"   → P(buy) = {selected['p_buy']:.0%} at ${selected['price']}")
    reasoning_lines.append("")

    # Explain WHY this price/discount
    if discount > 0:
        reasoning_lines.append("💰 WHY THIS DISCOUNT?")
        for part in synthesis_parts:
            reasoning_lines.append(f"   {part}")
        reasoning_lines.append("")
    elif synthesis_parts:
        reasoning_lines.append("📊 ANALYSIS:")
        for part in synthesis_parts:
            reasoning_lines.append(f"   {part}")
        reasoning_lines.append("")

    # Final decision summary
    reasoning_lines.append("════════════════════════════════════")
    reasoning_lines.append(f"✅ DECISION: {selected['display_name']}")
    if discount > 0:
        reasoning_lines.append(f"   Price: ${original_price:.0f} → ${final_price:.0f} ({discount:.0%} off)")
        reasoning_lines.append(f"   Policies: {', '.join(policies_applied)}")
    else:
        reasoning_lines.append(f"   Price: ${final_price:.0f} (full price - no discount needed)")
    reasoning_lines.append(f"   Expected Value: ${final_ev:.2f}")
    reasoning_lines.append(f"   Probability of Purchase: {selected['p_buy']:.0%}")
    reasoning_lines.append("════════════════════════════════════")

    solver_reasoning = "\n".join(reasoning_lines)

    return {
        "selected_offer": selected["offer_type"],
        "offer_price": final_price,
        "discount_applied": discount,
        "expected_value": final_ev,
        "solver_reasoning": solver_reasoning,
        "should_send_offer": True,
        "policies_applied": policies_applied,
    }


def should_continue_worker(state: ReWOOState) -> Literal["worker", "solver"]:
    """Determine if worker should continue or move to solver."""
    plan = state.get("plan", [])
    current_index = state.get("current_step_index", 0)

    if current_index < len(plan):
        return "worker"
    return "solver"


# =============================================================================
# ReWOO Sub-Graph Creation
# =============================================================================

def create_rewoo_graph() -> StateGraph:
    """
    Create the ReWOO sub-graph for Offer Orchestration.

    Graph Structure:
        START → planner → worker ←→ (loop until done) → solver → END

    Returns:
        Compiled StateGraph that can be invoked or streamed
    """
    workflow = StateGraph(ReWOOState)

    # Add nodes
    workflow.add_node("planner", planner_node)
    workflow.add_node("worker", worker_node)
    workflow.add_node("solver", solver_node)

    # Add edges
    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", "worker")

    # Conditional edge: worker loops until all steps done, then goes to solver
    workflow.add_conditional_edges(
        "worker",
        should_continue_worker,
        {
            "worker": "worker",
            "solver": "solver"
        }
    )

    workflow.add_edge("solver", END)

    return workflow


# Compile the graph once at module level
_rewoo_graph = None


def get_rewoo_graph():
    """Get the compiled ReWOO graph (singleton)."""
    global _rewoo_graph
    if _rewoo_graph is None:
        _rewoo_graph = create_rewoo_graph().compile()
    return _rewoo_graph


# =============================================================================
# Streaming Interface
# =============================================================================

def stream_offer_orchestration(
    customer_data: Dict[str, Any],
    flight_data: Dict[str, Any],
    ml_scores: Dict[str, Any],
    recommended_cabins: List[str],
    inventory_status: Dict[str, Any],
) -> Generator[Dict[str, Any], None, None]:
    """
    Stream the ReWOO execution, yielding events for each phase.

    Yields events:
        - {"phase": "planner", "status": "start"}
        - {"phase": "planner", "status": "complete", "plan": [...], "reasoning": "..."}
        - {"phase": "worker", "status": "step_start", "step": {...}}
        - {"phase": "worker", "status": "step_complete", "step_id": "E1", "result": {...}}
        - {"phase": "solver", "status": "start"}
        - {"phase": "solver", "status": "complete", "decision": {...}}
    """
    # Create initial state
    initial_state = create_rewoo_state(
        customer_data=customer_data,
        flight_data=flight_data,
        ml_scores=ml_scores,
        recommended_cabins=recommended_cabins,
        inventory_status=inventory_status,
    )

    graph = get_rewoo_graph()

    # Track last known state for detecting changes
    last_step_index = 0
    planner_done = False
    worker_done = False

    # Stream through the graph
    for event in graph.stream(initial_state):
        # event is a dict like {"planner": {...}} or {"worker": {...}} or {"solver": {...}}

        if "planner" in event:
            planner_state = event["planner"]
            plan = planner_state.get("plan", [])
            plan_reasoning = planner_state.get("plan_reasoning", "")
            offer_options = planner_state.get("offer_options", [])

            # Convert plan steps to dicts for JSON serialization
            plan_dicts = []
            for step in plan:
                if hasattr(step, '__dict__'):
                    plan_dicts.append({
                        "step_id": step.step_id,
                        "evaluation_type": step.evaluation_type,
                        "description": step.description,
                    })
                else:
                    plan_dicts.append(step)

            yield {
                "phase": "planner",
                "status": "complete",
                "plan": plan_dicts,
                "reasoning": plan_reasoning,
                "offer_options": offer_options,
            }
            planner_done = True

        elif "worker" in event:
            worker_state = event["worker"]
            current_index = worker_state.get("current_step_index", 0)
            step_results = worker_state.get("step_results", {})

            # Find newly completed step
            if current_index > last_step_index and step_results:
                # Get the step that just completed
                completed_step_id = f"E{current_index}"  # Worker increments after completion
                if completed_step_id in step_results:
                    step_result = step_results[completed_step_id]
                    yield {
                        "phase": "worker",
                        "status": "step_complete",
                        "step_id": completed_step_id,
                        "evaluation_type": step_result.evaluation_type if hasattr(step_result, 'evaluation_type') else step_result.get("evaluation_type"),
                        "result": step_result.result if hasattr(step_result, 'result') else step_result.get("result", {}),
                        "recommendation": step_result.recommendation if hasattr(step_result, 'recommendation') else step_result.get("recommendation"),
                        "reasoning": step_result.reasoning if hasattr(step_result, 'reasoning') else step_result.get("reasoning"),
                    }

            last_step_index = current_index

        elif "solver" in event:
            solver_state = event["solver"]
            yield {
                "phase": "solver",
                "status": "complete",
                "decision": {
                    "selected_offer": solver_state.get("selected_offer"),
                    "offer_price": solver_state.get("offer_price"),
                    "discount_applied": solver_state.get("discount_applied"),
                    "expected_value": solver_state.get("expected_value"),
                    "reasoning": solver_state.get("solver_reasoning"),
                    "policies_applied": solver_state.get("policies_applied", []),
                    "should_send_offer": solver_state.get("should_send_offer"),
                },
            }


def run_offer_orchestration(
    customer_data: Dict[str, Any],
    flight_data: Dict[str, Any],
    ml_scores: Dict[str, Any],
    recommended_cabins: List[str],
    inventory_status: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Run the ReWOO graph synchronously and return final result.

    This is a convenience wrapper for non-streaming use cases.
    """
    initial_state = create_rewoo_state(
        customer_data=customer_data,
        flight_data=flight_data,
        ml_scores=ml_scores,
        recommended_cabins=recommended_cabins,
        inventory_status=inventory_status,
    )

    graph = get_rewoo_graph()
    final_state = graph.invoke(initial_state)

    # Build reasoning trace from plan and results
    reasoning_parts = ["=== Offer Orchestration Agent (ReWOO) ===", ""]

    # Planner section
    reasoning_parts.append("=" * 50)
    reasoning_parts.append("STEP 1: PLANNER (Making a Plan)")
    reasoning_parts.append("=" * 50)
    reasoning_parts.append(f"LLM Plan: {final_state.get('plan_reasoning', '')}")
    reasoning_parts.append(f"Plan has {len(final_state.get('plan', []))} evaluation steps:")
    for step in final_state.get("plan", []):
        if hasattr(step, 'step_id'):
            reasoning_parts.append(f"  {step.step_id}: [{step.evaluation_type}] {step.description}")
        else:
            reasoning_parts.append(f"  {step.get('step_id')}: [{step.get('evaluation_type')}] {step.get('description')}")

    # Worker section
    reasoning_parts.append("")
    reasoning_parts.append("=" * 50)
    reasoning_parts.append("STEP 2: WORKER (Doing the Checks)")
    reasoning_parts.append("=" * 50)
    for step_id, result in final_state.get("step_results", {}).items():
        reasoning_parts.append("")
        eval_type = result.evaluation_type if hasattr(result, 'evaluation_type') else result.get("evaluation_type")
        reasoning = result.reasoning if hasattr(result, 'reasoning') else result.get("reasoning", "")
        reasoning_parts.append(f"--- Executing {step_id}: {eval_type} ---")
        reasoning_parts.append(f"  {reasoning}")

    # Solver section
    reasoning_parts.append("")
    reasoning_parts.append("=" * 50)
    reasoning_parts.append("STEP 3: SOLVER (Making the Final Decision)")
    reasoning_parts.append("=" * 50)
    reasoning_parts.append("")
    reasoning_parts.append(f"SYNTHESIS: {final_state.get('solver_reasoning', '')}")
    reasoning_parts.append("")

    selected = final_state.get("selected_offer", "NONE")
    price = final_state.get("offer_price", 0)
    discount = final_state.get("discount_applied", 0)
    ev = final_state.get("expected_value", 0)

    # Get display name
    display_name = selected
    for config in OFFER_CONFIG.values():
        if config["offer_type"] == selected:
            display_name = config["display_name"]
            break

    reasoning_parts.append(f"FINAL DECISION: {display_name} @ ${price:.0f}")
    if discount > 0:
        reasoning_parts.append(f"   Discount: {discount:.0%}")
        policies = final_state.get("policies_applied", [])
        if policies:
            reasoning_parts.append(f"   Policies Applied: {', '.join(policies)}")
    reasoning_parts.append(f"   Expected Value: ${ev:.2f}")

    return {
        "selected_offer": selected,
        "offer_price": price,
        "discount_applied": discount,
        "expected_value": ev,
        "should_send_offer": final_state.get("should_send_offer", False),
        "fallback_offer": None,
        "offer_reasoning": "\n".join(reasoning_parts),
        "reasoning_trace": [f"Offer Orchestration [ReWOO]: {selected} @ ${price:.0f}"],
        "rewoo_plan": [s.step_id if hasattr(s, 'step_id') else s.get('step_id') for s in final_state.get("plan", [])],
        "rewoo_results": {
            k: {
                "evaluation_type": v.evaluation_type if hasattr(v, 'evaluation_type') else v.get("evaluation_type"),
                "recommendation": v.recommendation if hasattr(v, 'recommendation') else v.get("recommendation"),
                "reasoning": v.reasoning if hasattr(v, 'reasoning') else v.get("reasoning"),
            }
            for k, v in final_state.get("step_results", {}).items()
        },
        "policies_applied": final_state.get("policies_applied", []),
    }


# =============================================================================
# Legacy Interface (for backward compatibility)
# =============================================================================

class OfferOrchestrationReWOO:
    """
    Legacy wrapper class for backward compatibility.

    The actual implementation uses the LangGraph sub-graph above.
    This class provides the same interface as before.
    """

    def __init__(self):
        self.name = "Offer Orchestration Agent (ReWOO)"

    def analyze(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point - executes the ReWOO pattern.

        For streaming, use stream_offer_orchestration() directly.
        """
        # Check prerequisites
        if not state.get("customer_eligible", False):
            reason = state.get("suppression_reason", "Not eligible")
            return self._no_offer_response(reason, "customer not eligible")

        recommended_cabins = state.get("recommended_cabins", [])
        if not recommended_cabins:
            return self._no_offer_response("No cabins recommended", "no inventory")

        # Run the ReWOO graph
        return run_offer_orchestration(
            customer_data=state.get("customer_data", {}),
            flight_data=state.get("flight_data", {}),
            ml_scores=state.get("ml_scores", {}),
            recommended_cabins=recommended_cabins,
            inventory_status=state.get("inventory_status", {}),
        )

    def _no_offer_response(self, reason: str, trace_reason: str) -> Dict[str, Any]:
        """Return a no-offer response."""
        return {
            "selected_offer": "NONE",
            "offer_price": 0,
            "discount_applied": 0,
            "expected_value": 0,
            "should_send_offer": False,
            "fallback_offer": None,
            "offer_reasoning": f"No offer: {reason}",
            "reasoning_trace": [f"{self.name}: No offer - {trace_reason}"]
        }
