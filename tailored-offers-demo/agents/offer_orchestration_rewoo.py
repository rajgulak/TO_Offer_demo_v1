"""
Offer Agent - Simple 3-Step Process

How it works (in plain English):
1. PLANNER: I look at the customer data and make a plan
   - "I have this customer info and these offers"
   - "Here's what I need to check before deciding"
   - The planner writes down a simple plan

2. WORKER: I do all the checks from the plan
   - "Now I'm checking each thing on the list"
   - "Is the computer sure? Did they have problems? Do they need a discount?"
   - The worker goes through the plan step by step

3. SOLVER: I look at all the results and decide
   - "I checked everything, here's what I found"
   - "Based on all this, here's the best offer to give"
   - I give this offer to the channel for sending
   - The channel decides the best way to send it (email, app, etc)

This way is good because:
- I check everything important (nothing gets skipped)
- Anyone can see what I checked and why I decided
- I make the same kind of decisions every time

IMPORTANT: I don't make up discounts on my own.
I only use discounts that Revenue Management already approved.
See config/discount_policies.json for the approved discount rules.
"""
from typing import Dict, Any, List, Optional
import json
import re
import os
from dataclasses import dataclass
from .state import AgentState
from .llm_service import get_llm, is_llm_available


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
        # Return default policies if file not found
        return {
            "policies": {
                "GOODWILL_RECOVERY": {"discount_percent": 10, "policy_id": "POL-GW-001"},
                "PRICE_SENSITIVE_HIGH": {"discount_percent": 15, "policy_id": "POL-PS-001"},
                "PRICE_SENSITIVE_MEDIUM": {"discount_percent": 5, "policy_id": "POL-PS-002"},
                "NO_DISCOUNT": {"discount_percent": 0, "policy_id": "POL-ND-001"}
            },
            "segment_caps": {}
        }


# Load policies at module level (cached)
DISCOUNT_POLICIES = load_discount_policies()


@dataclass
class EvaluationStep:
    """A single evaluation step in the plan"""
    step_id: str
    description: str
    evaluation_type: str  # confidence, relationship, price_sensitivity, inventory
    result: Optional[Dict[str, Any]] = None


@dataclass
class ReWOOPlan:
    """The complete evaluation plan"""
    steps: List[EvaluationStep]
    context: Dict[str, Any]


# System prompt for the PLANNER phase
PLANNER_PROMPT = """I have information about a customer and some upgrade offers I can give them.

My job is to look at this information and make a simple plan. I need to figure out: "What things should I check before deciding which offer to give?"

Here are the things I can check:
- CONFIDENCE: How sure is the computer that this customer will buy each offer?
- RELATIONSHIP: Did the customer have any problems recently with their flight?
- PRICE_SENSITIVITY: Will this customer only buy if I give them a discount?
- INVENTORY: Which airplane seats do we need to fill the most?

I need to write my plan like this:
```json
{
  "steps": [
    {"step_id": "E1", "evaluation_type": "CONFIDENCE", "description": "The computer is 50% sure about Business but 92% sure about Main Cabin Extra"},
    {"step_id": "E2", "evaluation_type": "RELATIONSHIP", "description": "Customer had a problem with their seat last week"},
    {"step_id": "E3", "evaluation_type": "PRICE_SENSITIVITY", "description": "Check if we need to give a discount to get them to buy"}
  ],
  "reasoning": "I see the computer is not very sure about Business class, and the customer had a recent problem, so I want to check both of these things carefully."
}
```

Important: Only check things that actually matter for this customer. Don't check everything if you don't need to."""


# System prompt for the SOLVER phase
SOLVER_PROMPT = """The planner made a plan. The worker did all the checks. Now I have all the results.

My job is to look at everything and make the final decision about which upgrade offer to give this customer.

Here's what I have:
1. Information about the customer
2. Different upgrade offers I can give (with prices)
3. Results from all the checks that were done

Now I need to put it all together and decide:

Things to think about:
- If the computer is not very sure about an expensive offer, maybe I should give them a cheaper, safer offer instead
- If the customer had a problem recently, I should give them a discount to make them feel better
- If the customer usually only buys when things are on sale, I should give them a discount

I need to write my decision like this:
```json
{
  "selected_offer": "IU_BUSINESS" or "MCE" or "IU_PREMIUM_ECONOMY",
  "offer_price": <number>,
  "discount_percent": <0-20>,
  "confidence": "high" or "medium" or "low",
  "synthesis": "Simple explanation of how I made this decision",
  "key_factors": ["reason1", "reason2"]
}
```

After I make this decision, I will give it to the channel. The channel will figure out the best way to send it to the customer (email, app notification, etc)."""


# Combined prompt for API exposure (for prompt management endpoints)
ORCHESTRATION_SYSTEM_PROMPT = f"""
Offer Agent - Simple 3-Step Process

This is how the Offer Agent works:

=== STEP 1: PLANNER (Make a Plan) ===
{PLANNER_PROMPT}

=== STEP 2: WORKER (Do the Checks) ===
Now I do each check from the plan, one by one.
I look at the data and figure out the answer to each question.

=== STEP 3: SOLVER (Make the Final Decision) ===
{SOLVER_PROMPT}
"""


class OfferOrchestrationReWOO:
    """
    Offer Agent - Figures out which upgrade offer to give each customer.

    How it works:
    1. PLANNER: I look at the customer data and make a plan of what to check
    2. WORKER: I do each check from the plan and write down what I found
    3. SOLVER: I look at all the results and decide which offer is best

    Then I give this offer to the channel for sending. The channel decides
    the best way to send it (email, app notification, text message, etc).
    """

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

    def __init__(self):
        self.name = "Offer Orchestration Agent (ReWOO)"
        self._llm = None

    @property
    def llm(self):
        if self._llm is None:
            self._llm = get_llm(temperature=0.3)
        return self._llm

    def analyze(self, state: AgentState) -> Dict[str, Any]:
        """
        Main entry point - executes the ReWOO pattern.
        """
        reasoning_parts = []
        reasoning_parts.append(f"=== {self.name} ===")
        reasoning_parts.append("")

        # Check prerequisites
        if not state.get("customer_eligible", False):
            reason = state.get("suppression_reason", "Not eligible")
            return self._no_offer_response(reason, "customer not eligible")

        recommended_cabins = state.get("recommended_cabins", [])
        if not recommended_cabins:
            return self._no_offer_response("No cabins recommended", "no inventory")

        # Build context for planning
        context = self._build_context(state, recommended_cabins)
        reasoning_parts.append(f"Customer: {context['customer']['name']} ({context['customer']['loyalty_tier_display']}, ${context['customer']['annual_revenue']:,}/yr)")
        reasoning_parts.append(f"Available offers: {', '.join([o['display_name'] for o in context['offer_options']])}")
        reasoning_parts.append("")

        # ============================================================
        # STEP 1: PLANNER - Make a plan of what to check
        # ============================================================
        reasoning_parts.append("=" * 50)
        reasoning_parts.append("STEP 1: PLANNER (Making a Plan)")
        reasoning_parts.append("=" * 50)

        plan = self._run_planner(context, reasoning_parts)

        # ============================================================
        # STEP 2: WORKER - Do each check from the plan
        # ============================================================
        reasoning_parts.append("")
        reasoning_parts.append("=" * 50)
        reasoning_parts.append("STEP 2: WORKER (Doing the Checks)")
        reasoning_parts.append("=" * 50)

        evaluation_results = self._run_worker(plan, context, reasoning_parts)

        # ============================================================
        # STEP 3: SOLVER - Look at everything and make the decision
        # ============================================================
        reasoning_parts.append("")
        reasoning_parts.append("=" * 50)
        reasoning_parts.append("STEP 3: SOLVER (Making the Final Decision)")
        reasoning_parts.append("=" * 50)

        decision = self._run_solver(context, evaluation_results, reasoning_parts)

        # Build response
        return {
            "selected_offer": decision["selected_offer"],
            "offer_price": decision["offer_price"],
            "discount_applied": decision.get("discount_percent", 0) / 100,
            "expected_value": decision.get("expected_value", 0),
            "should_send_offer": decision["selected_offer"] != "NONE",
            "fallback_offer": decision.get("fallback_offer"),
            "offer_reasoning": "\n".join(reasoning_parts),
            "reasoning_trace": [f"{self.name} [ReWOO]: {decision['selected_offer']} @ ${decision['offer_price']}"],
            "rewoo_plan": [s.step_id for s in plan.steps],
            "rewoo_results": evaluation_results
        }

    def _build_context(self, state: AgentState, recommended_cabins: List[str]) -> Dict[str, Any]:
        """Build context for the ReWOO phases."""
        customer = state.get("customer_data", {})
        flight = state.get("flight_data", {})
        ml_scores = state.get("ml_scores", {})
        inventory = state.get("inventory_status", {})

        propensity_scores = ml_scores.get("propensity_scores", {}) if ml_scores else {}
        product_catalog = flight.get("product_catalog", {}) if flight else {}

        # Build offer options
        offer_options = []
        for cabin_code in recommended_cabins:
            config_key = self.CABIN_CODE_MAP.get(cabin_code, cabin_code)
            config = self.OFFER_CONFIG.get(config_key)
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

        # Tier display names
        tier_names = {"E": "Executive Platinum", "T": "Platinum Pro", "P": "Platinum", "G": "Gold"}
        tier_display = tier_names.get(customer.get("loyalty_tier", ""), "General")

        # Service recovery context
        service_recovery = customer.get("recent_service_recovery", {})

        return {
            "customer": {
                "name": f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip(),
                "loyalty_tier": customer.get("loyalty_tier", "General"),
                "loyalty_tier_display": tier_display,
                "annual_revenue": customer.get("flight_revenue_amt_history", 0),
                "has_recent_issue": service_recovery.get("had_issue", False),
                "issue_type": service_recovery.get("issue_type"),
                "customer_sentiment": service_recovery.get("customer_sentiment"),
                "price_sensitivity": ml_scores.get("price_sensitivity", "medium") if ml_scores else "medium"
            },
            "offer_options": offer_options,
            "hours_to_departure": state.get("reservation_data", {}).get("hours_to_departure", 72)
        }

    def _run_planner(self, context: Dict[str, Any], reasoning_parts: List[str]) -> ReWOOPlan:
        """
        PLANNER: Look at the customer data and make a plan of what to check.
        """
        # Build planner prompt
        planner_input = f"""
Customer: {context['customer']['name']}
- Loyalty Tier: {context['customer']['loyalty_tier_display']}
- Annual Revenue: ${context['customer']['annual_revenue']:,}
- Has Recent Service Issue: {context['customer']['has_recent_issue']}
- Price Sensitivity: {context['customer']['price_sensitivity']}

Available Offers:
"""
        for opt in context['offer_options']:
            planner_input += f"""
- {opt['display_name']}:
  - P(buy): {opt['p_buy']:.0%}
  - ML Confidence: {opt['confidence']:.0%} {'(LOW!)' if opt['confidence'] < 0.6 else '(HIGH)' if opt['confidence'] > 0.85 else ''}
  - Price: ${opt['price']}
  - Expected Value: ${opt['expected_value']:.2f}
"""

        planner_input += "\nCreate an evaluation plan for this offer decision."

        steps = []

        if is_llm_available():
            try:
                from langchain_core.messages import SystemMessage, HumanMessage

                response = self.llm.invoke([
                    SystemMessage(content=PLANNER_PROMPT),
                    HumanMessage(content=planner_input)
                ])

                # Parse plan from response
                plan_json = self._extract_json(response.content)
                if plan_json and "steps" in plan_json:
                    for s in plan_json["steps"]:
                        steps.append(EvaluationStep(
                            step_id=s.get("step_id", f"E{len(steps)+1}"),
                            description=s.get("description", ""),
                            evaluation_type=s.get("evaluation_type", "UNKNOWN")
                        ))
                    reasoning_parts.append(f"LLM Plan: {plan_json.get('reasoning', 'No reasoning provided')}")

            except Exception as e:
                reasoning_parts.append(f"LLM planning failed: {e}, using default plan")

        # Default plan if LLM fails or unavailable
        if not steps:
            steps = self._create_default_plan(context)
            reasoning_parts.append("Using default evaluation plan")

        reasoning_parts.append(f"Plan has {len(steps)} evaluation steps:")
        for step in steps:
            reasoning_parts.append(f"  {step.step_id}: [{step.evaluation_type}] {step.description}")

        return ReWOOPlan(steps=steps, context=context)

    def _create_default_plan(self, context: Dict[str, Any]) -> List[EvaluationStep]:
        """Create a default evaluation plan based on context."""
        steps = []

        # Always evaluate confidence if multiple offers
        if len(context['offer_options']) > 1:
            low_conf = any(o['confidence'] < 0.6 for o in context['offer_options'])
            high_conf = any(o['confidence'] > 0.85 for o in context['offer_options'])
            if low_conf and high_conf:
                steps.append(EvaluationStep(
                    step_id="E1",
                    description="Confidence trade-off: Low vs High confidence offers",
                    evaluation_type="CONFIDENCE"
                ))

        # Check relationship if recent issue
        if context['customer'].get('has_recent_issue'):
            steps.append(EvaluationStep(
                step_id=f"E{len(steps)+1}",
                description=f"Relationship risk: Recent {context['customer'].get('issue_type', 'issue')}",
                evaluation_type="RELATIONSHIP"
            ))

        # Check price sensitivity
        if context['customer'].get('price_sensitivity') == 'high':
            steps.append(EvaluationStep(
                step_id=f"E{len(steps)+1}",
                description="Price sensitivity: Customer is price-sensitive",
                evaluation_type="PRICE_SENSITIVITY"
            ))

        # If no trade-offs detected, just evaluate EV
        if not steps:
            steps.append(EvaluationStep(
                step_id="E1",
                description="Standard EV comparison - no trade-offs detected",
                evaluation_type="EV_COMPARISON"
            ))

        return steps

    def _run_worker(self, plan: ReWOOPlan, context: Dict[str, Any], reasoning_parts: List[str]) -> Dict[str, Any]:
        """
        WORKER: Go through the plan and do each check, one by one.
        """
        results = {}

        for step in plan.steps:
            reasoning_parts.append("")
            reasoning_parts.append(f"--- Executing {step.step_id}: {step.evaluation_type} ---")

            if step.evaluation_type == "CONFIDENCE":
                result = self._evaluate_confidence(context, reasoning_parts)
            elif step.evaluation_type == "RELATIONSHIP":
                result = self._evaluate_relationship(context, reasoning_parts)
            elif step.evaluation_type == "PRICE_SENSITIVITY":
                result = self._evaluate_price_sensitivity(context, reasoning_parts)
            elif step.evaluation_type == "INVENTORY":
                result = self._evaluate_inventory(context, reasoning_parts)
            else:  # EV_COMPARISON or default
                result = self._evaluate_ev(context, reasoning_parts)

            step.result = result
            results[step.step_id] = result

        return results

    def _evaluate_confidence(self, context: Dict[str, Any], reasoning_parts: List[str]) -> Dict[str, Any]:
        """Check: How sure is the computer about each offer?"""
        offers = context['offer_options']

        # Find highest EV offer and highest confidence offer
        best_ev_offer = max(offers, key=lambda x: x['expected_value'])
        best_conf_offer = max(offers, key=lambda x: x['confidence'])

        result = {
            "best_ev_offer": best_ev_offer['offer_type'],
            "best_ev": best_ev_offer['expected_value'],
            "best_ev_confidence": best_ev_offer['confidence'],
            "safest_offer": best_conf_offer['offer_type'],
            "safest_confidence": best_conf_offer['confidence'],
            "safest_ev": best_conf_offer['expected_value'],
            "recommendation": None,
            "reasoning": ""
        }

        # Trade-off logic: If best EV has LOW confidence and there's a HIGH confidence alternative
        if best_ev_offer['confidence'] < 0.60 and best_conf_offer['confidence'] > 0.85:
            result["recommendation"] = "CHOOSE_SAFER"
            result["reasoning"] = (
                f"Best EV ({best_ev_offer['display_name']}) has LOW confidence ({best_ev_offer['confidence']:.0%}). "
                f"Recommend safer {best_conf_offer['display_name']} with {best_conf_offer['confidence']:.0%} confidence."
            )
            reasoning_parts.append(f"  ⚠️ CONFIDENCE TRADE-OFF: {result['reasoning']}")
        else:
            result["recommendation"] = "PROCEED_WITH_BEST_EV"
            result["reasoning"] = f"Best EV offer has acceptable confidence ({best_ev_offer['confidence']:.0%})"
            reasoning_parts.append(f"  ✓ No confidence concern: {result['reasoning']}")

        return result

    def _evaluate_relationship(self, context: Dict[str, Any], reasoning_parts: List[str]) -> Dict[str, Any]:
        """
        Check: Did the customer have any problems recently?

        NOTE: I only use discounts that were already approved.
        Policy: GOODWILL_RECOVERY (POL-GW-001) - Already approved by Customer Experience Team
        """
        customer = context['customer']

        # Get pre-approved policy
        goodwill_policy = DISCOUNT_POLICIES.get("policies", {}).get("GOODWILL_RECOVERY", {})
        policy_id = goodwill_policy.get("policy_id", "POL-GW-001")
        policy_discount = goodwill_policy.get("discount_percent", 10) / 100  # Convert to decimal

        result = {
            "has_recent_issue": customer.get('has_recent_issue', False),
            "issue_type": customer.get('issue_type'),
            "sentiment": customer.get('customer_sentiment'),
            "annual_revenue": customer.get('annual_revenue', 0),
            "recommendation": None,
            "goodwill_discount": 0,
            "policy_applied": None,
            "reasoning": ""
        }

        if result['has_recent_issue'] and result['annual_revenue'] > 50000:
            result["recommendation"] = "APPLY_GOODWILL_DISCOUNT"
            result["goodwill_discount"] = policy_discount
            result["policy_applied"] = policy_id
            result["reasoning"] = (
                f"High-value customer (${result['annual_revenue']:,}/yr) had recent {result['issue_type']}. "
                f"Applying pre-approved policy [{policy_id}]: {policy_discount:.0%} goodwill discount."
            )
            reasoning_parts.append(f"  ⚠️ RELATIONSHIP RISK: {result['reasoning']}")
        elif result['has_recent_issue']:
            result["recommendation"] = "PROCEED_WITH_CAUTION"
            result["reasoning"] = "Customer had recent issue but lower LTV - proceed carefully (no policy triggered)"
            reasoning_parts.append(f"  ⚡ Relationship note: {result['reasoning']}")
        else:
            result["recommendation"] = "NO_CONCERN"
            result["reasoning"] = "No recent service issues"
            reasoning_parts.append(f"  ✓ Relationship OK: {result['reasoning']}")

        return result

    def _evaluate_price_sensitivity(self, context: Dict[str, Any], reasoning_parts: List[str]) -> Dict[str, Any]:
        """
        Check: Will this customer only buy if we give them a discount?

        NOTE: I only use discounts that were already approved.
        Policies:
        - PRICE_SENSITIVE_HIGH (POL-PS-001) - Already approved by Revenue Management
        - PRICE_SENSITIVE_MEDIUM (POL-PS-002) - Already approved by Revenue Management
        """
        sensitivity = context['customer'].get('price_sensitivity', 'medium')

        # Get pre-approved policies
        high_policy = DISCOUNT_POLICIES.get("policies", {}).get("PRICE_SENSITIVE_HIGH", {})
        medium_policy = DISCOUNT_POLICIES.get("policies", {}).get("PRICE_SENSITIVE_MEDIUM", {})
        no_discount_policy = DISCOUNT_POLICIES.get("policies", {}).get("NO_DISCOUNT", {})

        result = {
            "sensitivity_level": sensitivity,
            "recommendation": None,
            "discount_percent": 0,
            "policy_applied": None,
            "reasoning": ""
        }

        if sensitivity == 'high':
            policy_id = high_policy.get("policy_id", "POL-PS-001")
            policy_discount = high_policy.get("discount_percent", 15) / 100
            result["recommendation"] = "APPLY_DISCOUNT"
            result["discount_percent"] = policy_discount
            result["policy_applied"] = policy_id
            result["reasoning"] = f"High price sensitivity - applying pre-approved policy [{policy_id}]: {policy_discount:.0%} discount"
            reasoning_parts.append(f"  💰 PRICE SENSITIVE: {result['reasoning']}")
        elif sensitivity == 'medium':
            policy_id = medium_policy.get("policy_id", "POL-PS-002")
            policy_discount = medium_policy.get("discount_percent", 5) / 100
            result["recommendation"] = "SMALL_DISCOUNT_OPTIONAL"
            result["discount_percent"] = policy_discount
            result["policy_applied"] = policy_id
            result["reasoning"] = f"Medium sensitivity - pre-approved policy [{policy_id}] allows {policy_discount:.0%} discount"
            reasoning_parts.append(f"  ⚡ Price note: {result['reasoning']}")
        else:
            policy_id = no_discount_policy.get("policy_id", "POL-ND-001")
            result["recommendation"] = "NO_DISCOUNT"
            result["discount_percent"] = 0
            result["policy_applied"] = policy_id
            result["reasoning"] = f"Low price sensitivity - policy [{policy_id}]: no discount needed"
            reasoning_parts.append(f"  ✓ Price OK: {result['reasoning']}")

        return result

    def _evaluate_inventory(self, context: Dict[str, Any], reasoning_parts: List[str]) -> Dict[str, Any]:
        """Check: Which airplane seats do we need to fill the most?"""
        offers = context['offer_options']

        high_priority = [o for o in offers if o.get('inventory_priority') == 'high']

        result = {
            "high_priority_cabins": [o['offer_type'] for o in high_priority],
            "recommendation": "PRIORITIZE_HIGH_INVENTORY" if high_priority else "NO_PRIORITY",
            "reasoning": f"{len(high_priority)} cabins need inventory treatment" if high_priority else "No urgent inventory needs"
        }

        reasoning_parts.append(f"  📦 Inventory: {result['reasoning']}")
        return result

    def _evaluate_ev(self, context: Dict[str, Any], reasoning_parts: List[str]) -> Dict[str, Any]:
        """Check: Which offer will make the most money?"""
        offers = context['offer_options']
        best = max(offers, key=lambda x: x['expected_value'])

        result = {
            "best_offer": best['offer_type'],
            "best_ev": best['expected_value'],
            "best_price": best['price'],
            "recommendation": "SELECT_HIGHEST_EV",
            "reasoning": f"Clear winner: {best['display_name']} with EV ${best['expected_value']:.2f}"
        }

        reasoning_parts.append(f"  ✓ Best EV: {result['reasoning']}")
        return result

    def _run_solver(self, context: Dict[str, Any], evaluation_results: Dict[str, Any], reasoning_parts: List[str]) -> Dict[str, Any]:
        """
        SOLVER: Look at all the check results and decide which offer is best.
        Then give it to the channel for sending.
        """
        offers = context['offer_options']
        best_ev_offer = max(offers, key=lambda x: x['expected_value'])

        # Start with best EV as default
        selected = best_ev_offer
        discount = 0
        synthesis_parts = []

        # Track which policies were applied
        policies_applied = []

        # Apply evaluation results
        for step_id, result in evaluation_results.items():
            rec = result.get('recommendation', '')
            policy_id = result.get('policy_applied')

            if rec == "CHOOSE_SAFER":
                # Find the safer offer
                safest_type = result.get('safest_offer')
                safest = next((o for o in offers if o['offer_type'] == safest_type), None)
                if safest:
                    selected = safest
                    synthesis_parts.append(f"Chose {safest['display_name']} due to confidence trade-off")

            elif rec == "APPLY_GOODWILL_DISCOUNT":
                goodwill = result.get('goodwill_discount', 0.10)
                discount = max(discount, goodwill)
                if policy_id:
                    policies_applied.append(policy_id)
                    synthesis_parts.append(f"Applied pre-approved policy [{policy_id}]: {goodwill:.0%} goodwill discount")
                else:
                    synthesis_parts.append(f"Applied {goodwill:.0%} goodwill discount for relationship")

            elif rec == "APPLY_DISCOUNT":
                price_disc = result.get('discount_percent', 0.15)
                discount = max(discount, price_disc)
                if policy_id:
                    policies_applied.append(policy_id)
                    synthesis_parts.append(f"Applied pre-approved policy [{policy_id}]: {price_disc:.0%} discount")
                else:
                    synthesis_parts.append(f"Applied {price_disc:.0%} discount for price sensitivity")

        # Cap discount at max allowed by segment policy
        customer_segment = context['customer'].get('segment', 'mid_value_mixed')
        segment_caps = DISCOUNT_POLICIES.get("segment_caps", {})
        segment_config = segment_caps.get(customer_segment, {})
        max_segment_discount = segment_config.get("max_total_discount", 20) / 100

        # Also check offer-level max discount
        config_key = self.CABIN_CODE_MAP.get(selected['cabin'], 'business')
        config = self.OFFER_CONFIG.get(config_key, {})
        max_offer_discount = config.get('max_discount', 0.20)

        # Use the more restrictive cap
        max_discount = min(max_segment_discount, max_offer_discount)
        original_discount = discount
        discount = min(discount, max_discount)

        if discount < original_discount:
            synthesis_parts.append(f"Discount capped at {max_discount:.0%} per segment policy")

        # Calculate final price
        final_price = selected['price'] * (1 - discount)
        final_ev = selected['p_buy'] * final_price * selected['margin']

        # Build synthesis
        if not synthesis_parts:
            synthesis_parts.append(f"Selected {selected['display_name']} as highest EV with no trade-off concerns")

        synthesis = "; ".join(synthesis_parts)

        reasoning_parts.append("")
        reasoning_parts.append(f"SYNTHESIS: {synthesis}")
        reasoning_parts.append("")
        reasoning_parts.append(f"✅ FINAL DECISION: {selected['display_name']} @ ${final_price:.0f}")
        if discount > 0:
            reasoning_parts.append(f"   Discount: {discount:.0%} (from ${selected['price']} to ${final_price:.0f})")
            if policies_applied:
                reasoning_parts.append(f"   Policies Applied: {', '.join(policies_applied)}")
                reasoning_parts.append(f"   ℹ️  Discounts are PRE-APPROVED by Revenue Management, not agent decisions")
        reasoning_parts.append(f"   Expected Value: ${final_ev:.2f}")

        # Use LLM for synthesis if available (optional enhancement)
        if is_llm_available():
            reasoning_parts.append("")
            reasoning_parts.append("[LLM Synthesis Confirmation]")
            # Could add LLM call here for additional reasoning

        return {
            "selected_offer": selected['offer_type'],
            "offer_price": final_price,
            "discount_percent": discount * 100,
            "expected_value": final_ev,
            "confidence": "high" if selected['confidence'] > 0.85 else "medium" if selected['confidence'] > 0.6 else "low",
            "synthesis": synthesis,
            "key_factors": [r.get('recommendation', '') for r in evaluation_results.values() if r.get('recommendation')],
            "policies_applied": policies_applied,
            "fallback_offer": None
        }

    def _extract_json(self, text: str) -> Optional[Dict]:
        """Extract JSON from LLM response."""
        try:
            # Try to find JSON in code block
            match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            # Try to parse entire response as JSON
            return json.loads(text)
        except:
            return None

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
