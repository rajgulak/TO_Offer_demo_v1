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

Your PRIMARY GOAL is to MAXIMIZE REVENUE, not maximize acceptance rate.

## CRITICAL: Expected Value (EV) is your PRIMARY decision factor

EV = P(buy) × Price × Margin

The offer with the HIGHEST EV should almost always win, even if:
- It has a LOWER acceptance probability
- It has a HIGHER price

Example:
- Business Class: 40% chance × $171 = $68 EV ← PICK THIS ONE
- Main Cabin Extra: 80% chance × $39 = $31 EV

Even though MCE has DOUBLE the acceptance rate, Business has MORE THAN DOUBLE the EV.
We make MORE MONEY sending Business offers, even if fewer people say yes.

## Secondary factors (only matter when EVs are close):
- Customer price sensitivity (may warrant small discount)
- Inventory priority (may break ties)
- Confidence scores (low confidence = more uncertainty)

## Your Task
1. Calculate EV for each offer (already provided)
2. Select the offer with the HIGHEST EV
3. Only deviate if EVs are within 20% AND there's a compelling secondary reason

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

Remember: You are a REVENUE MANAGER. Higher EV = More revenue = Better decision."""


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

    ============================================================
    15+ FACTORS CONSIDERED IN DECISION
    ============================================================

    CUSTOMER FACTORS (6):
      1. Loyalty Tier (G/P/PP/E) - from customer_data.loyalty_tier
      2. Annual Revenue - from customer_data.flight_revenue_amt_history
      3. Travel Pattern - derived from business_trip_likelihood
      4. Historical Acceptance Rate - from historical_upgrades.acceptance_rate
      5. Avg Upgrade Spend - from historical_upgrades.avg_upgrade_spend
      6. Price Sensitivity - from ml_scores.price_sensitivity

    FLIGHT/TIMING FACTORS (3):
      7. Route (origin/destination) - from flight_data airports
      8. Hours to Departure - from reservation_data.hours_to_departure
      9. Inventory Priority - from inventory_status per cabin

    PER-OFFER FACTORS (6 per offer × 2-3 offers = 12-18):
      10. P(buy) at multiple price points - from ml_scores.propensity_scores
      11. ML Model Confidence - from propensity_scores.confidence
      12. Base Price - from flight_data.product_catalog
      13. Margin Percentage - from OFFER_CONFIG
      14. Max Discount Allowed - from OFFER_CONFIG
      15. Expected Value - CALCULATED: P(buy) × Price × Margin

    UPSTREAM AGENT DECISIONS (3):
      16. Customer Eligible - from Customer Intelligence Agent
      17. Recommended Cabins - from Flight Optimization Agent
      18. Flight Priority - from Flight Optimization Agent

    TOTAL: 18+ factors when evaluating multiple offers
    ============================================================
    """

    # Cabin code to config key mapping
    CABIN_CODE_MAP = {
        "F": "business",
        "W": "premium_economy",
        "MCE": "main_cabin_extra"
    }

    # ================================================================
    # GUARDRAILS: Business-defined limits that Agent CANNOT exceed
    # These are set by Revenue Management, not the Agent
    # ================================================================
    OFFER_CONFIG = {
        "business": {
            "offer_type": "IU_BUSINESS",
            "display_name": "Business Class",
            "base_margin": 0.90,
            "min_discount": 0,
            "max_discount": 0.20,      # ⛔ GUARDRAIL: Never exceed 20% off
            "price_key": "iu_business_price"
        },
        "premium_economy": {
            "offer_type": "IU_PREMIUM_ECONOMY",
            "display_name": "Premium Economy",
            "base_margin": 0.88,
            "min_discount": 0,
            "max_discount": 0.15,      # ⛔ GUARDRAIL: Never exceed 15% off
            "price_key": "iu_premium_economy_price"
        },
        "main_cabin_extra": {
            "offer_type": "MCE",
            "display_name": "Main Cabin Extra",
            "base_margin": 0.85,
            "min_discount": 0,
            "max_discount": 0.25,      # ⛔ GUARDRAIL: Never exceed 25% off
            "price_key": "mce_price"
        }
    }

    # ================================================================
    # TIME-BASED DISCOUNT POLICY (Guardrails for urgency discounts)
    # ================================================================
    # Data Source: hours_to_departure from reservation_data
    # Loaded by: load_data node via get_reservation() MCP tool
    # Origin: Reservation System API (in production) / reservations.json (demo)
    # ================================================================
    URGENCY_DISCOUNT_POLICY = {
        # hours_to_departure thresholds and corresponding discount boosts
        # Agent can ADD these to base discount, but total still capped by max_discount
        "tiers": [
            {
                "name": "TOO_LATE",
                "max_hours": 6,           # T-6hrs or less
                "discount_boost": 0,       # No discount - don't send offer
                "send_offer": False,       # ⛔ GUARDRAIL: Stop sending at T-6hrs
                "reason": "Too close to departure - customer likely checked in"
            },
            {
                "name": "URGENT",
                "max_hours": 24,           # T-24hrs to T-6hrs
                "discount_boost": 0.10,    # +10% urgency discount
                "send_offer": True,
                "reason": "Last chance - flight tomorrow"
            },
            {
                "name": "SOON",
                "max_hours": 48,           # T-48hrs to T-24hrs
                "discount_boost": 0.05,    # +5% urgency discount
                "send_offer": True,
                "reason": "Flight approaching - encourage quick decision"
            },
            {
                "name": "NORMAL",
                "max_hours": 168,          # T-7days to T-48hrs
                "discount_boost": 0,       # No urgency discount
                "send_offer": True,
                "reason": "Standard timing - full price acceptable"
            },
            {
                "name": "EARLY",
                "max_hours": float('inf'), # More than 7 days out
                "discount_boost": 0,       # No urgency discount
                "send_offer": True,
                "reason": "Early booking - no urgency pressure"
            }
        ],
        # ⛔ ABSOLUTE GUARDRAIL: Even with urgency, never exceed product max_discount
        "respect_max_discount": True
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
        product_catalog = flight.get("product_catalog", {}) if flight else {}

        for cabin_code in recommended_cabins:
            # Map cabin code (F, W, MCE) to config key (business, premium_economy, main_cabin_extra)
            config_key = self.CABIN_CODE_MAP.get(cabin_code, cabin_code)
            config = self.OFFER_CONFIG.get(config_key)
            if not config:
                continue

            offer_type = config["offer_type"]
            score_data = propensity_scores.get(offer_type, {})

            # Get P(buy) from price_points in ML scores
            price_points = score_data.get("price_points", {})
            # Use mid-range price point for context building
            if price_points:
                prices = sorted([int(p) for p in price_points.keys()])
                mid_price = prices[len(prices) // 2]
                p_buy = price_points.get(str(mid_price), {}).get("p_buy", 0.3)
            else:
                p_buy = 0.3
            confidence = score_data.get("confidence", 0.5)

            # Get base price from product_catalog
            price_key = config.get("price_key", "")
            base_price = product_catalog.get(price_key, 0)
            if base_price == 0:
                base_price = {"business": 199, "premium_economy": 129, "main_cabin_extra": 39}.get(config_key, 50)

            # Calculate EV
            margin_pct = config["base_margin"]  # e.g., 0.90 = 90%
            margin_dollars = base_price * margin_pct  # e.g., $199 * 0.90 = $179
            ev = p_buy * margin_dollars  # e.g., 0.68 * $179 = $121.79

            offer_options.append({
                "cabin": cabin_code,
                "config_key": config_key,
                "offer_type": offer_type,
                "display_name": config["display_name"],
                "p_buy": p_buy,
                "confidence": confidence,
                "base_price": base_price,
                "margin_pct": margin_pct,
                "margin_dollars": margin_dollars,
                "expected_value": ev,
                "max_discount": config["max_discount"],
                "inventory_priority": inventory.get(cabin_code, {}).get("priority", "low")
            })

        return {
            "customer": {
                "name": f"{customer.get('first_name', '')} {customer.get('last_name', '')}",
                "loyalty_tier": customer.get("loyalty_tier", "General"),
                "annual_revenue": customer.get("flight_revenue_amt_history", 0),
                "travel_pattern": "business" if customer.get("business_trip_likelihood", 0) > 0.5 else "leisure",
                "historical_acceptance_rate": customer.get("historical_upgrades", {}).get("acceptance_rate", 0),
                "avg_upgrade_spend": customer.get("historical_upgrades", {}).get("avg_upgrade_spend", 0)
            },
            "customer_summary": f"{customer.get('first_name', 'Customer')} ({customer.get('loyalty_tier', 'General')}, ${customer.get('flight_revenue_amt_history', 0):,}/yr)",
            "price_sensitivity": ml_scores.get("price_sensitivity", "medium") if ml_scores else "medium",
            "offer_options": offer_options,
            "flight": {
                "route": f"{flight.get('schd_leg_dep_airprt_iata_cd', '')} → {flight.get('schd_leg_arvl_airprt_iata_cd', '')}",
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
- P(buy): {opt['p_buy']:.0%} chance customer will purchase
- Price: ${opt['base_price']}
- Our margin: {opt['margin_pct']:.0%} (= ${opt['margin_dollars']:.0f} profit per sale)
- **EXPECTED VALUE: ${opt['expected_value']:.2f}**
  (Calculation: {opt['p_buy']:.0%} × ${opt['margin_dollars']:.0f} = ${opt['expected_value']:.2f})
- Inventory Priority: {opt['inventory_priority']}
"""

        user_prompt += """
## Your Task
1. COMPARE the Expected Values (EV) - this is the PRIMARY factor
2. Select the offer with the HIGHEST EV (even if it has lower acceptance probability!)
3. Only consider secondary factors if EVs are within 20% of each other
4. Apply a small discount (5-15%) only if customer has high price sensitivity
5. Provide your decision in the JSON format specified

REMEMBER: A $121 EV beats a $27 EV, even if the $27 option has higher acceptance rate.
We maximize REVENUE, not acceptance rate.
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
                margin_pct = opt.get('margin_pct', 0.85)
                return opt['p_buy'] * price * margin_pct
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
        reservation = state.get("reservation_data", {})

        propensity_scores = ml_scores.get("propensity_scores", {}) if ml_scores else {}
        product_catalog = flight.get("product_catalog", {}) if flight else {}
        price_sensitivity = ml_scores.get("price_sensitivity", "medium") if ml_scores else "medium"

        # ================================================================
        # GET hours_to_departure FROM STATE
        # Data Source: reservation_data.hours_to_departure
        # Loaded by: load_data node via get_reservation() MCP tool
        # Origin: Reservation System API → reservations.json (demo)
        # ================================================================
        hours_to_departure = reservation.get("hours_to_departure", 72)
        urgency_tier = self._get_urgency_tier(hours_to_departure)

        # ⛔ GUARDRAIL CHECK: Too close to departure?
        if not urgency_tier["send_offer"]:
            reasoning_parts.append("📊 DATA USED (from MCP Tools):")
            reasoning_parts.append("")
            reasoning_parts.append("┌─ get_reservation() → Reservation System")
            reasoning_parts.append(f"│  • Hours to Departure: {hours_to_departure} (T-{hours_to_departure}hrs)")
            reasoning_parts.append(f"│  • Urgency Tier: {urgency_tier['name']}")
            reasoning_parts.append("│")
            reasoning_parts.append("└─ ⛔ GUARDRAIL TRIGGERED")
            reasoning_parts.append(f"   • Reason: {urgency_tier['reason']}")
            reasoning_parts.append("")
            reasoning_parts.append("─" * 50)
            reasoning_parts.append("")
            reasoning_parts.append("❌ DECISION: DO NOT SEND OFFER")
            reasoning_parts.append("")
            reasoning_parts.append("📍 IN SIMPLE TERMS:")
            reasoning_parts.append(f"   The flight departs in {hours_to_departure} hours.")
            reasoning_parts.append("   It's too late to send an upgrade offer because:")
            reasoning_parts.append("   • Customer has likely already checked in")
            reasoning_parts.append("   • Sending offers now would be annoying, not helpful")
            reasoning_parts.append("   • Better to focus on customers with more time")
            reasoning_parts.append("")
            reasoning_parts.append("💡 GUARDRAIL IN ACTION:")
            reasoning_parts.append("   The Agent COULD send an offer, but the business rule")
            reasoning_parts.append("   (T-6hrs cutoff) prevents it. This is bounded autonomy.")

            return {
                "selected_offer": "NONE",
                "offer_price": 0,
                "discount_applied": 0,
                "expected_value": 0,
                "fallback_offer": None,
                "offer_reasoning": "\n".join(reasoning_parts),
                "should_send_offer": False,
                "urgency_tier": urgency_tier["name"],
                "reasoning_trace": [f"{self.name}: No offer - T-{hours_to_departure}hrs too close to departure"]
            }

        # ========== DATA USED SECTION ==========
        reasoning_parts.append("📊 DATA USED (from MCP Tools):")
        reasoning_parts.append("")
        reasoning_parts.append("┌─ get_reservation() → Reservation System")
        reasoning_parts.append(f"│  • Hours to Departure: {hours_to_departure} (T-{hours_to_departure}hrs)")
        reasoning_parts.append(f"│  • Urgency Tier: {urgency_tier['name']}")
        if urgency_tier["discount_boost"] > 0:
            reasoning_parts.append(f"│  • Urgency Discount Boost: +{urgency_tier['discount_boost']:.0%}")
        reasoning_parts.append("│")
        reasoning_parts.append("├─ get_propensity_scores() → ML Model")
        reasoning_parts.append("│  P(buy) = Probability customer will purchase this offer")
        reasoning_parts.append("│  (Based on historical behavior + similar customer patterns)")
        for cabin_code in recommended_cabins:
            config_key = self.CABIN_CODE_MAP.get(cabin_code, cabin_code)
            config = self.OFFER_CONFIG.get(config_key)
            if config:
                score_data = propensity_scores.get(config["offer_type"], {})
                price_points = score_data.get("price_points", {})
                # Get mid-range P(buy)
                if price_points:
                    prices = sorted([int(p) for p in price_points.keys()])
                    mid_price = prices[len(prices) // 2]
                    p_buy = price_points.get(str(mid_price), {}).get("p_buy", 0.3)
                else:
                    p_buy = 0.3
                conf = score_data.get("confidence", 0.5)
                reasoning_parts.append(f"│  • {config['display_name']}: P(buy) = {p_buy:.0%} (confidence: {conf:.0%})")
        reasoning_parts.append("│")
        reasoning_parts.append("├─ get_pricing() → Revenue Management Engine")
        for cabin_code in recommended_cabins:
            config_key = self.CABIN_CODE_MAP.get(cabin_code, cabin_code)
            config = self.OFFER_CONFIG.get(config_key)
            if config:
                price_key = config.get("price_key", "")
                base_price = product_catalog.get(price_key, 0)
                if base_price == 0:
                    base_price = {"business": 199, "premium_economy": 129, "main_cabin_extra": 39}.get(config_key, 50)
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

        # Calculate EV for each offer - evaluate ALL price points to find optimal
        offer_candidates = []
        for cabin_code in recommended_cabins:
            config_key = self.CABIN_CODE_MAP.get(cabin_code, cabin_code)
            config = self.OFFER_CONFIG.get(config_key)
            if not config:
                continue

            offer_type = config["offer_type"]
            score_data = propensity_scores.get(offer_type, {})
            price_points = score_data.get("price_points", {})
            price_key = config.get("price_key", "")
            base_price = product_catalog.get(price_key, 0)
            if base_price == 0:
                base_price = {"business": 199, "premium_economy": 129, "main_cabin_extra": 39}.get(config_key, 50)

            margin = config["base_margin"]
            max_discount = config["max_discount"]

            # Evaluate ALL available price points to find optimal EV
            best_ev = 0
            best_price = base_price
            best_p_buy = 0.3
            best_discount = 0
            all_price_evs = []

            if price_points:
                for price_str, score_info in price_points.items():
                    price = int(price_str)
                    p_buy = score_info.get("p_buy", 0.3)

                    # Calculate what discount this price represents
                    if base_price > 0:
                        discount_pct = 1 - (price / base_price)
                    else:
                        discount_pct = 0

                    # Only consider prices within our discount limit
                    if discount_pct <= max_discount + 0.01:  # Small tolerance
                        ev = p_buy * price * margin
                        all_price_evs.append({
                            "price": price,
                            "p_buy": p_buy,
                            "discount": discount_pct,
                            "ev": ev
                        })
                        if ev > best_ev:
                            best_ev = ev
                            best_price = price
                            best_p_buy = p_buy
                            best_discount = max(0, discount_pct)
            else:
                # No price points - use base price with standard logic
                discount = 0.05 if price_sensitivity == "high" else 0
                best_price = base_price * (1 - discount)
                best_p_buy = 0.3
                best_discount = discount
                best_ev = best_p_buy * best_price * margin

            # ================================================================
            # APPLY URGENCY-BASED DISCOUNT (with guardrail enforcement)
            # Agent Autonomy: Can add urgency boost
            # Guardrail: Total discount capped at max_discount
            # ================================================================
            urgency_boost = urgency_tier["discount_boost"]
            if urgency_boost > 0:
                # Calculate urgency-adjusted discount
                proposed_total_discount = best_discount + urgency_boost

                # ⛔ GUARDRAIL: Cap at max_discount
                final_discount = min(proposed_total_discount, max_discount)
                guardrail_hit = proposed_total_discount > max_discount

                # Recalculate price with urgency discount
                urgency_adjusted_price = base_price * (1 - final_discount)
                # Use same p_buy for simplicity (in reality would re-lookup)
                urgency_adjusted_ev = best_p_buy * urgency_adjusted_price * margin

                # Update best values with urgency adjustment
                best_price = urgency_adjusted_price
                best_discount = final_discount
                best_ev = urgency_adjusted_ev

            # Show analysis of all price points if multiple exist
            reasoning_parts.append(f"   {config['display_name']}:")
            if len(all_price_evs) > 1:
                reasoning_parts.append(f"      Evaluating {len(all_price_evs)} price points to find optimal:")
                for pe in sorted(all_price_evs, key=lambda x: x['price'], reverse=True):
                    marker = " ← SELECTED" if pe['price'] == best_price or abs(pe['price'] - best_price) < 5 else ""
                    reasoning_parts.append(f"      • ${pe['price']}: {pe['p_buy']:.0%} chance → EV = ${pe['ev']:.2f}{marker}")
                reasoning_parts.append("")
            reasoning_parts.append(f"      OPTIMAL: {best_p_buy:.0%} × ${best_price:.0f} × {margin:.0%} margin")
            reasoning_parts.append(f"             = ${best_ev:.2f} expected revenue per offer sent")

            # Show discount breakdown
            if urgency_boost > 0:
                reasoning_parts.append("")
                reasoning_parts.append(f"      📉 DISCOUNT BREAKDOWN:")
                base_disc_display = best_discount - urgency_boost if best_discount > urgency_boost else 0
                reasoning_parts.append(f"         Base discount:    {base_disc_display:.0%}")
                reasoning_parts.append(f"         + Urgency boost:  +{urgency_boost:.0%} (T-{hours_to_departure}hrs)")
                reasoning_parts.append(f"         ─────────────────────")
                if guardrail_hit:
                    reasoning_parts.append(f"         Proposed total:   {proposed_total_discount:.0%}")
                    reasoning_parts.append(f"         ⛔ GUARDRAIL:     Max {max_discount:.0%} allowed")
                    reasoning_parts.append(f"         Final discount:   {final_discount:.0%} (capped)")
                else:
                    reasoning_parts.append(f"         Final discount:   {best_discount:.0%}")
            elif best_discount > 0:
                reasoning_parts.append(f"      📉 Applying {best_discount:.0%} discount (max allowed: {max_discount:.0%})")
            reasoning_parts.append("")

            offer_candidates.append({
                "cabin": cabin_code,
                "config_key": config_key,
                "offer_type": offer_type,
                "display_name": config["display_name"],
                "p_buy": best_p_buy,
                "final_price": best_price,
                "discount": best_discount,
                "expected_value": best_ev,
                "urgency_tier": urgency_tier["name"],
                "urgency_boost_applied": urgency_boost
            })

        # Select highest EV
        offer_candidates.sort(key=lambda x: x["expected_value"], reverse=True)
        primary = offer_candidates[0]

        # ========== DECISION SECTION ==========
        reasoning_parts.append("─" * 50)
        reasoning_parts.append("")
        reasoning_parts.append(f"✅ DECISION: OFFER {primary['display_name'].upper()} at ${primary['final_price']:.0f}")
        reasoning_parts.append(f"   Urgency: {urgency_tier['name']} (T-{hours_to_departure}hrs)")
        reasoning_parts.append("")
        reasoning_parts.append("📍 IN SIMPLE TERMS:")
        reasoning_parts.append(f"   We're offering {primary['display_name']} because:")
        reasoning_parts.append(f"   • {primary['p_buy']:.0%} chance they'll say yes (pretty good!)")
        reasoning_parts.append(f"   • We expect to make ~${primary['expected_value']:.0f} on average from this offer")
        if primary.get('urgency_boost_applied', 0) > 0:
            reasoning_parts.append(f"   • Added {primary['urgency_boost_applied']:.0%} urgency discount (flight in {hours_to_departure}hrs)")
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
            f"(EV=${primary['expected_value']:.2f}, T-{hours_to_departure}hrs)"
        )

        return {
            "selected_offer": primary["offer_type"],
            "offer_price": primary["final_price"],
            "discount_applied": primary["discount"],
            "expected_value": primary["expected_value"],
            "fallback_offer": fallback,
            "offer_reasoning": "\n".join(reasoning_parts),
            "should_send_offer": True,
            "urgency_tier": urgency_tier["name"],
            "hours_to_departure": hours_to_departure,
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

    def _get_urgency_tier(self, hours_to_departure: int) -> Dict[str, Any]:
        """
        Determine urgency tier based on hours to departure.

        Data Source: hours_to_departure from reservation_data
        Loaded by: load_data node via get_reservation() MCP tool
        Origin: Calculated from leg_dep_dt - current_time

        Returns tier config with discount_boost and send_offer flag.
        """
        for tier in self.URGENCY_DISCOUNT_POLICY["tiers"]:
            if hours_to_departure <= tier["max_hours"]:
                return tier
        # Default to EARLY tier
        return self.URGENCY_DISCOUNT_POLICY["tiers"][-1]

    def _calculate_urgency_adjusted_discount(
        self,
        base_discount: float,
        hours_to_departure: int,
        max_discount: float
    ) -> tuple[float, Dict[str, Any]]:
        """
        Calculate final discount with urgency adjustment, respecting guardrails.

        Agent Autonomy: Can ADD urgency discount to base discount
        Guardrail: Total discount NEVER exceeds product max_discount

        Returns: (final_discount, urgency_tier_info)
        """
        urgency_tier = self._get_urgency_tier(hours_to_departure)

        # Agent's proposed discount = base + urgency boost
        proposed_discount = base_discount + urgency_tier["discount_boost"]

        # ⛔ GUARDRAIL ENFORCEMENT: Cap at max_discount
        final_discount = min(proposed_discount, max_discount)

        # Track if guardrail was hit
        urgency_tier["guardrail_applied"] = proposed_discount > max_discount
        urgency_tier["proposed_discount"] = proposed_discount
        urgency_tier["final_discount"] = final_discount

        return final_discount, urgency_tier
