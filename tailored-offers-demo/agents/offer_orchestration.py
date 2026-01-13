"""
Agent 3: Offer Orchestration Agent (LLM-Powered)

Purpose: Arbitrates between IU/MCE offers based on propensity × value
Data Sources: Product availability, pricing, customer propensity scores
Decisions: Optimal offer selection, pricing strategy

This agent demonstrates LLM REASONING:
- Uses AI to analyze multiple factors holistically
- Considers nuances that rule engines miss
- Provides explainable decision-making

Architecture:
- LangGraph: Workflow orchestration (routing between agents)
- LLM: Dynamic reasoning within this agent
- Can fall back to rules if LLM unavailable
"""
from typing import Dict, Any, Optional, List, Tuple
import json
import re
from .state import AgentState
from .llm_service import get_llm, is_llm_available


# System prompt for LLM reasoning
ORCHESTRATION_SYSTEM_PROMPT = """You are an Offer Orchestration Agent for American Airlines' Tailored Offers system.

Your job is to analyze customer data, ML propensity scores, and inventory status to select the OPTIMAL upgrade offer.

You must consider:
1. Expected Value (EV) = P(buy) × margin - higher EV offers are generally preferred
2. Customer context - loyalty tier, price sensitivity, historical behavior
3. Inventory needs - cabins with high priority need more aggressive offers
4. Risk factors - low confidence scores, cold-start customers

Output your reasoning step-by-step, then provide a final decision in this exact JSON format:

```json
{
  "selected_offer": "IU_BUSINESS" or "IU_PREMIUM_ECONOMY" or "MCE" or "NONE",
  "offer_price": <number>,
  "discount_percent": <number 0-20>,
  "fallback_offer": "MCE" or "IU_PREMIUM_ECONOMY" or null,
  "fallback_price": <number or null>,
  "confidence": "high" or "medium" or "low",
  "key_factors": ["factor1", "factor2", "factor3"]
}
```

Think like a strategic revenue manager, not a rule engine. Consider the holistic picture."""


class OfferOrchestrationAgent:
    """
    Arbitrates between multiple offer options using LLM reasoning.

    This agent demonstrates HOW AGENTS DIFFER FROM RULE ENGINES:
    - Rule engine: if p_buy > 0.5 then send_offer()
    - Agent: "Given the customer's high price sensitivity but strong brand affinity,
              and the fact that Business cabin needs treatment, I recommend..."

    Architecture shows:
    - LangGraph: orchestrates the workflow (agent sequence)
    - LLM: provides reasoning WITHIN this agent
    - Temporal: could provide durable execution (shown in workflow.py)
    """

    # Offer configuration
    OFFER_CONFIG = {
        "business": {
            "offer_type": "IU_BUSINESS",
            "display_name": "Business Class",
            "base_margin": 0.90,
            "min_discount": 0,
            "max_discount": 0.20
        },
        "premium_economy": {
            "offer_type": "IU_PREMIUM_ECONOMY",
            "display_name": "Premium Economy",
            "base_margin": 0.88,
            "min_discount": 0,
            "max_discount": 0.15
        },
        "main_cabin_extra": {
            "offer_type": "MCE",
            "display_name": "Main Cabin Extra",
            "base_margin": 0.85,
            "min_discount": 0,
            "max_discount": 0.25
        }
    }

    def __init__(self, use_llm: bool = True):
        self.name = "Offer Orchestration Agent"
        self.use_llm = use_llm
        self._llm = None

    @property
    def llm(self):
        if self._llm is None:
            self._llm = get_llm(temperature=0.3)  # Lower temp for consistent decisions
        return self._llm

    def analyze(self, state: AgentState) -> Dict[str, Any]:
        """
        Select optimal offer using LLM reasoning (or rules fallback).

        Returns updated state with offer decision outputs.
        """
        reasoning_parts = []
        reasoning_parts.append(f"=== {self.name} ===")

        # Check prerequisites
        if not state.get("customer_eligible", False):
            reason = state.get("suppression_reason", "Not eligible")
            return self._no_offer_response(reason, "customer not eligible")

        recommended_cabins = state.get("recommended_cabins", [])
        if not recommended_cabins:
            return self._no_offer_response("No cabins recommended for upgrade", "no cabins need treatment")

        # Gather context for LLM
        context = self._build_context(state, recommended_cabins)
        reasoning_parts.append(f"Customer: {context['customer_summary']}")
        reasoning_parts.append(f"Available offers: {', '.join(recommended_cabins)}")

        # Use LLM reasoning if available, otherwise fall back to rules
        if self.use_llm and is_llm_available():
            result = self._llm_reasoning(context, reasoning_parts)
            result["reasoning_mode"] = "LLM"
        else:
            result = self._rules_based_reasoning(state, recommended_cabins, reasoning_parts)
            result["reasoning_mode"] = "RULES"

        return result

    def _build_context(self, state: AgentState, recommended_cabins: List[str]) -> Dict[str, Any]:
        """Build context dictionary for LLM prompt."""
        customer = state.get("customer_data", {})
        flight = state.get("flight_data", {})
        ml_scores = state.get("ml_scores", {})
        inventory = state.get("inventory_status", {})

        # Build offer options with calculated values
        offer_options = []
        propensity_scores = ml_scores.get("propensity_scores", {}) if ml_scores else {}
        pricing = flight.get("pricing", {}) if flight else {}

        for cabin in recommended_cabins:
            config = self.OFFER_CONFIG.get(cabin)
            if not config:
                continue

            offer_type = config["offer_type"]
            score_data = propensity_scores.get(offer_type, {})
            p_buy = score_data.get("p_buy", 0.3)
            confidence = score_data.get("confidence", 0.5)

            # Get base price
            price_key = f"{cabin.replace('main_cabin_extra', 'mce')}_upgrade_base"
            base_price = pricing.get(price_key, 0)
            if base_price == 0:
                base_price = {"business": 199, "premium_economy": 129, "main_cabin_extra": 39}.get(cabin, 50)

            # Calculate EV
            margin = base_price * config["base_margin"]
            ev = p_buy * margin

            offer_options.append({
                "cabin": cabin,
                "offer_type": offer_type,
                "display_name": config["display_name"],
                "p_buy": p_buy,
                "confidence": confidence,
                "base_price": base_price,
                "margin": margin,
                "expected_value": ev,
                "max_discount": config["max_discount"],
                "inventory_priority": inventory.get(cabin, {}).get("priority", "low")
            })

        return {
            "customer": {
                "name": f"{customer.get('first_name', '')} {customer.get('last_name', '')}",
                "loyalty_tier": customer.get("loyalty_tier", "General"),
                "annual_revenue": customer.get("annual_revenue", 0),
                "travel_pattern": customer.get("travel_pattern", "mixed"),
                "historical_acceptance_rate": customer.get("historical_upgrades", {}).get("acceptance_rate", 0),
                "avg_upgrade_spend": customer.get("historical_upgrades", {}).get("avg_upgrade_spend", 0)
            },
            "customer_summary": f"{customer.get('first_name', 'Customer')} ({customer.get('loyalty_tier', 'General')}, ${customer.get('annual_revenue', 0):,}/yr)",
            "price_sensitivity": ml_scores.get("price_sensitivity", "medium") if ml_scores else "medium",
            "offer_options": offer_options,
            "flight": {
                "route": f"{flight.get('origin', '')} → {flight.get('destination', '')}",
                "hours_to_departure": state.get("reservation_data", {}).get("hours_to_departure", 72)
            }
        }

    def _llm_reasoning(self, context: Dict[str, Any], reasoning_parts: List[str]) -> Dict[str, Any]:
        """Use LLM for dynamic reasoning about offer selection."""
        reasoning_parts.append("\n[LLM REASONING MODE]")

        # Build prompt
        user_prompt = f"""Analyze this offer opportunity and select the optimal offer:

## Customer Profile
- Name: {context['customer']['name']}
- Loyalty Tier: {context['customer']['loyalty_tier']}
- Annual Revenue: ${context['customer']['annual_revenue']:,}
- Travel Pattern: {context['customer']['travel_pattern']}
- Historical Acceptance Rate: {context['customer']['historical_acceptance_rate']:.0%}
- Price Sensitivity: {context['price_sensitivity']}

## Flight Context
- Route: {context['flight']['route']}
- Hours to Departure: {context['flight']['hours_to_departure']}

## Available Offers
"""
        for opt in context['offer_options']:
            user_prompt += f"""
### {opt['display_name']} ({opt['offer_type']})
- P(buy): {opt['p_buy']:.2f} (confidence: {opt['confidence']:.2f})
- Base Price: ${opt['base_price']}
- Expected Value: ${opt['expected_value']:.2f}
- Inventory Priority: {opt['inventory_priority']}
- Max Discount: {opt['max_discount']:.0%}
"""

        user_prompt += """
## Your Task
1. Reason through the factors step-by-step
2. Consider what a RULE ENGINE would miss
3. Select the optimal offer with pricing
4. Provide your decision in the JSON format specified
"""

        try:
            # Call LLM
            from langchain_core.messages import SystemMessage, HumanMessage

            response = self.llm.invoke([
                SystemMessage(content=ORCHESTRATION_SYSTEM_PROMPT),
                HumanMessage(content=user_prompt)
            ])

            llm_output = response.content
            reasoning_parts.append(f"\n{llm_output}")

            # Parse JSON from response
            decision = self._parse_llm_decision(llm_output, context)

            if decision["selected_offer"] == "NONE":
                return self._no_offer_response("LLM decided no offer is appropriate", "LLM reasoning")

            # Build response
            trace_entry = (
                f"{self.name} [LLM]: Selected {decision['selected_offer']} @ ${decision['offer_price']:.0f} | "
                f"Key factors: {', '.join(decision.get('key_factors', [])[:2])}"
            )

            return {
                "selected_offer": decision["selected_offer"],
                "offer_price": decision["offer_price"],
                "discount_applied": decision["discount_percent"] / 100,
                "expected_value": self._calculate_ev(decision, context),
                "fallback_offer": self._build_fallback(decision, context),
                "offer_reasoning": "\n".join(reasoning_parts),
                "should_send_offer": True,
                "llm_confidence": decision.get("confidence", "medium"),
                "llm_key_factors": decision.get("key_factors", []),
                "reasoning_trace": [trace_entry]
            }

        except Exception as e:
            reasoning_parts.append(f"\n[LLM Error: {str(e)} - falling back to rules]")
            return self._rules_based_reasoning(
                {"ml_scores": {"propensity_scores": {opt["offer_type"]: {"p_buy": opt["p_buy"]} for opt in context["offer_options"]}}},
                [opt["cabin"] for opt in context["offer_options"]],
                reasoning_parts
            )

    def _parse_llm_decision(self, llm_output: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Parse the LLM's JSON decision from its response."""
        # Try to find JSON in the response
        json_match = re.search(r'```json\s*(.*?)\s*```', llm_output, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find raw JSON
        try:
            start = llm_output.find('{')
            end = llm_output.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(llm_output[start:end])
        except json.JSONDecodeError:
            pass

        # Default: use highest EV option
        best = max(context['offer_options'], key=lambda x: x['expected_value'])
        return {
            "selected_offer": best["offer_type"],
            "offer_price": best["base_price"],
            "discount_percent": 0,
            "confidence": "medium",
            "key_factors": ["Expected value optimization"]
        }

    def _calculate_ev(self, decision: Dict[str, Any], context: Dict[str, Any]) -> float:
        """Calculate expected value for the decision."""
        for opt in context['offer_options']:
            if opt['offer_type'] == decision['selected_offer']:
                price = decision.get('offer_price', opt['base_price'])
                return opt['p_buy'] * price * 0.85  # Approximate margin
        return 0

    def _build_fallback(self, decision: Dict[str, Any], context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Build fallback offer from LLM decision."""
        fallback_type = decision.get("fallback_offer")
        if not fallback_type:
            return None

        for opt in context['offer_options']:
            if opt['offer_type'] == fallback_type:
                return {
                    "offer_type": fallback_type,
                    "display_name": opt['display_name'],
                    "price": decision.get("fallback_price", opt['base_price']),
                    "p_buy": opt['p_buy']
                }
        return None

    def _rules_based_reasoning(
        self,
        state: AgentState,
        recommended_cabins: List[str],
        reasoning_parts: List[str]
    ) -> Dict[str, Any]:
        """
        Fallback rules-based reasoning when LLM is unavailable.

        This shows the CONTRAST with LLM reasoning - simple if-then logic.
        """
        ml_scores = state.get("ml_scores", {})
        flight = state.get("flight_data", {})
        customer = state.get("customer_data", {})
        inventory = state.get("inventory_status", {})

        propensity_scores = ml_scores.get("propensity_scores", {}) if ml_scores else {}
        pricing = flight.get("pricing", {}) if flight else {}
        price_sensitivity = ml_scores.get("price_sensitivity", "medium") if ml_scores else "medium"

        # ========== DATA USED SECTION ==========
        reasoning_parts.append("📊 DATA USED (from MCP Tools):")
        reasoning_parts.append("")
        reasoning_parts.append("┌─ get_propensity_scores() → ML Model")
        reasoning_parts.append("│  P(buy) = Probability customer will purchase this offer")
        reasoning_parts.append("│  (Based on historical behavior + similar customer patterns)")
        for cabin in recommended_cabins:
            config = self.OFFER_CONFIG.get(cabin)
            if config:
                score_data = propensity_scores.get(config["offer_type"], {})
                p_buy = score_data.get("p_buy", 0.3)
                conf = score_data.get("confidence", 0.5)
                reasoning_parts.append(f"│  • {config['display_name']}: P(buy) = {p_buy:.0%} (confidence: {conf:.0%})")
        reasoning_parts.append("│")
        reasoning_parts.append("├─ get_pricing() → Revenue Management Engine")
        for cabin in recommended_cabins:
            config = self.OFFER_CONFIG.get(cabin)
            if config:
                price_key = f"{cabin.replace('main_cabin_extra', 'mce')}_upgrade_base"
                base_price = pricing.get(price_key, {"business": 199, "premium_economy": 129, "main_cabin_extra": 39}.get(cabin, 50))
                reasoning_parts.append(f"│  • {config['display_name']}: ${base_price}")
        reasoning_parts.append("│")
        reasoning_parts.append("└─ Customer Price Sensitivity (from ML)")
        reasoning_parts.append(f"   • Sensitivity Level: {price_sensitivity.upper()}")
        if price_sensitivity == "high":
            reasoning_parts.append("   • Will apply 5% discount to increase conversion")

        # ========== ANALYSIS SECTION ==========
        reasoning_parts.append("")
        reasoning_parts.append("─" * 50)
        reasoning_parts.append("")
        reasoning_parts.append("🔍 ANALYSIS:")
        reasoning_parts.append("")
        reasoning_parts.append("   Calculating Expected Value (EV) for each offer:")
        reasoning_parts.append("")
        reasoning_parts.append("   ┌────────────────────────────────────────────────┐")
        reasoning_parts.append("   │  EV = P(buy) × Price × Margin                  │")
        reasoning_parts.append("   │                                                │")
        reasoning_parts.append("   │  EV tells us: \"How much revenue can we        │")
        reasoning_parts.append("   │  expect ON AVERAGE from sending this offer?\"  │")
        reasoning_parts.append("   │                                                │")
        reasoning_parts.append("   │  Higher EV = Better business outcome           │")
        reasoning_parts.append("   └────────────────────────────────────────────────┘")
        reasoning_parts.append("")

        # Calculate EV for each offer
        offer_candidates = []
        for cabin in recommended_cabins:
            config = self.OFFER_CONFIG.get(cabin)
            if not config:
                continue

            offer_type = config["offer_type"]
            score_data = propensity_scores.get(offer_type, {})
            p_buy = score_data.get("p_buy", 0.3)

            price_key = f"{cabin.replace('main_cabin_extra', 'mce')}_upgrade_base"
            base_price = pricing.get(price_key, 0)
            if base_price == 0:
                base_price = {"business": 199, "premium_economy": 129, "main_cabin_extra": 39}.get(cabin, 50)

            # Simple discount rule
            discount = 0.05 if price_sensitivity == "high" else 0
            final_price = base_price * (1 - discount)
            margin = config["base_margin"]
            ev = p_buy * final_price * margin

            reasoning_parts.append(f"   {config['display_name']}:")
            reasoning_parts.append(f"      EV = {p_buy:.0%} × ${final_price:.0f} × {margin:.0%} margin")
            reasoning_parts.append(f"         = ${ev:.2f} expected revenue per offer sent")
            reasoning_parts.append("")

            offer_candidates.append({
                "cabin": cabin,
                "offer_type": offer_type,
                "display_name": config["display_name"],
                "p_buy": p_buy,
                "final_price": final_price,
                "discount": discount,
                "expected_value": ev
            })

        # Select highest EV
        offer_candidates.sort(key=lambda x: x["expected_value"], reverse=True)
        primary = offer_candidates[0]

        # ========== DECISION SECTION ==========
        reasoning_parts.append("─" * 50)
        reasoning_parts.append("")
        reasoning_parts.append(f"✅ DECISION: OFFER {primary['display_name'].upper()} at ${primary['final_price']:.0f}")
        reasoning_parts.append("")
        reasoning_parts.append("📍 IN SIMPLE TERMS:")
        reasoning_parts.append(f"   We're offering {primary['display_name']} because:")
        reasoning_parts.append(f"   • {primary['p_buy']:.0%} chance they'll say yes (pretty good!)")
        reasoning_parts.append(f"   • We expect to make ~${primary['expected_value']:.0f} on average from this offer")
        if len(offer_candidates) > 1:
            second = offer_candidates[1]
            reasoning_parts.append(f"   • This beats {second['display_name']} (would only make ~${second['expected_value']:.0f})")

        fallback = None
        if len(offer_candidates) > 1:
            fb = offer_candidates[1]
            fallback = {
                "offer_type": fb["offer_type"],
                "display_name": fb["display_name"],
                "price": fb["final_price"],
                "p_buy": fb["p_buy"]
            }
            reasoning_parts.append("")
            reasoning_parts.append(f"📍 BACKUP PLAN:")
            reasoning_parts.append(f"   If they say no, we'll offer {fb['display_name']} at ${fb['final_price']:.0f}")
            reasoning_parts.append(f"   (Cheaper option = higher chance they'll say yes)")

        # ========== WHY AGENTS MATTER ==========
        reasoning_parts.append("")
        reasoning_parts.append("💡 WHY THIS AGENT MATTERS:")
        reasoning_parts.append("   A simple rule engine would do this:")
        reasoning_parts.append("   \"If P(buy) > 50% → Send the most expensive offer\"")
        reasoning_parts.append("")
        reasoning_parts.append("   But this agent THOUGHT about it:")
        reasoning_parts.append("   • Compared multiple offers side-by-side")
        reasoning_parts.append("   • Calculated which one makes the MOST money (not just any money)")
        reasoning_parts.append("   • Considered the customer's price sensitivity")
        reasoning_parts.append("   • Prepared a backup offer if the first one fails")
        reasoning_parts.append("")
        reasoning_parts.append("   This is strategic thinking, not just if-then rules!")

        trace_entry = (
            f"{self.name} [RULES]: Selected {primary['display_name']} @ ${primary['final_price']:.0f} "
            f"(EV=${primary['expected_value']:.2f})"
        )

        return {
            "selected_offer": primary["offer_type"],
            "offer_price": primary["final_price"],
            "discount_applied": primary["discount"],
            "expected_value": primary["expected_value"],
            "fallback_offer": fallback,
            "offer_reasoning": "\n".join(reasoning_parts),
            "should_send_offer": True,
            "reasoning_trace": [trace_entry]
        }

    def _no_offer_response(self, reason: str, trace_reason: str) -> Dict[str, Any]:
        """Build no-offer response."""
        return {
            "selected_offer": "NONE",
            "offer_price": 0,
            "discount_applied": 0,
            "expected_value": 0,
            "fallback_offer": None,
            "offer_reasoning": f"No offer: {reason}",
            "should_send_offer": False,
            "reasoning_trace": [f"{self.name}: No offer - {trace_reason}"]
        }
