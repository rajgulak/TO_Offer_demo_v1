"""
Agent 3: Offer Orchestration Agent

Purpose: Arbitrates between IU/MCE offers based on propensity × value
Data Sources: Product availability, pricing, customer propensity scores
Decisions: Optimal offer selection, pricing strategy
"""
from typing import Dict, Any, Optional, List, Tuple
from .state import AgentState


class OfferOrchestrationAgent:
    """
    Arbitrates between multiple offer options to select the optimal one.

    This agent answers: "Which offer should we send, at what price?"

    Key insight: ML gives us P(buy) for each offer, but we need to consider:
    - Expected value (P(buy) × revenue)
    - Flight inventory needs
    - Customer's historical preferences
    - Fallback options
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

    def __init__(self):
        self.name = "Offer Orchestration Agent"

    def analyze(self, state: AgentState) -> Dict[str, Any]:
        """
        Select optimal offer based on propensity, value, and constraints.

        Returns updated state with offer decision outputs.
        """
        reasoning_parts = []
        reasoning_parts.append(f"=== {self.name} ===")

        # Check prerequisites
        if not state.get("customer_eligible", False):
            reason = state.get("suppression_reason", "Not eligible")
            reasoning_parts.append(f"Customer not eligible: {reason}")
            reasoning_parts.append("Decision: NO OFFER")

            return {
                "selected_offer": "NONE",
                "offer_price": 0,
                "discount_applied": 0,
                "expected_value": 0,
                "fallback_offer": None,
                "offer_reasoning": "\n".join(reasoning_parts),
                "should_send_offer": False,
                "reasoning_trace": [f"{self.name}: No offer - customer not eligible ({reason})"]
            }

        recommended_cabins = state.get("recommended_cabins", [])
        if not recommended_cabins:
            reasoning_parts.append("No cabins recommended for upgrade")
            reasoning_parts.append("Decision: NO OFFER")

            return {
                "selected_offer": "NONE",
                "offer_price": 0,
                "discount_applied": 0,
                "expected_value": 0,
                "fallback_offer": None,
                "offer_reasoning": "\n".join(reasoning_parts),
                "should_send_offer": False,
                "reasoning_trace": [f"{self.name}: No offer - no cabins need treatment"]
            }

        # Get ML scores and flight data
        ml_scores = state.get("ml_scores", {})
        flight = state.get("flight_data", {})
        customer = state.get("customer_data", {})
        inventory = state.get("inventory_status", {})

        propensity_scores = ml_scores.get("propensity_scores", {}) if ml_scores else {}
        pricing = flight.get("pricing", {}) if flight else {}
        price_sensitivity = ml_scores.get("price_sensitivity", "medium") if ml_scores else "medium"

        reasoning_parts.append(f"Customer price sensitivity: {price_sensitivity}")
        reasoning_parts.append(f"Recommended cabins: {', '.join(recommended_cabins)}")
        reasoning_parts.append("\nEvaluating offers:")

        # Calculate expected value for each recommended cabin
        offer_candidates = []

        for cabin in recommended_cabins:
            config = self.OFFER_CONFIG.get(cabin)
            if not config:
                continue

            offer_type = config["offer_type"]

            # Get P(buy) from ML scores
            ml_key = offer_type
            score_data = propensity_scores.get(ml_key, {})
            p_buy = score_data.get("p_buy")
            confidence = score_data.get("confidence", 0)

            # Handle null/missing scores
            if p_buy is None:
                reasoning_parts.append(f"  - {config['display_name']}: ML score unavailable (cold start)")
                # Use rules-based fallback
                p_buy = self._estimate_rules_based_propensity(customer, cabin)
                confidence = 0.5
                reasoning_parts.append(f"    Using rules-based estimate: {p_buy:.2f}")

            # Get base price
            price_key = f"{cabin.replace('main_cabin_extra', 'mce')}_upgrade_base"
            base_price = pricing.get(price_key, 0)
            if base_price == 0 and cabin == "main_cabin_extra":
                base_price = pricing.get("mce_upgrade_base", 39)
            if base_price == 0 and cabin == "business":
                base_price = pricing.get("business_upgrade_base", 199)
            if base_price == 0 and cabin == "premium_economy":
                base_price = pricing.get("premium_economy_upgrade_base", 129)

            # Calculate optimal price with discount
            discount = self._calculate_discount(
                p_buy=p_buy,
                price_sensitivity=price_sensitivity,
                cabin_priority=inventory.get(cabin, {}).get("priority", "low"),
                max_discount=config["max_discount"]
            )

            final_price = base_price * (1 - discount)
            margin = final_price * config["base_margin"]

            # Calculate expected value
            expected_value = p_buy * margin

            reasoning_parts.append(
                f"  - {config['display_name']}:"
            )
            reasoning_parts.append(
                f"    P(buy)={p_buy:.2f}, Base=${base_price}, "
                f"Discount={discount:.0%}, Final=${final_price:.0f}"
            )
            reasoning_parts.append(
                f"    Expected Value: {p_buy:.2f} × ${margin:.0f} = ${expected_value:.2f}"
            )

            offer_candidates.append({
                "cabin": cabin,
                "offer_type": offer_type,
                "display_name": config["display_name"],
                "p_buy": p_buy,
                "confidence": confidence,
                "base_price": base_price,
                "discount": discount,
                "final_price": final_price,
                "expected_value": expected_value
            })

        if not offer_candidates:
            reasoning_parts.append("\nNo valid offers available")
            return {
                "selected_offer": "NONE",
                "offer_price": 0,
                "discount_applied": 0,
                "expected_value": 0,
                "fallback_offer": None,
                "offer_reasoning": "\n".join(reasoning_parts),
                "should_send_offer": False,
                "reasoning_trace": [f"{self.name}: No valid offers available"]
            }

        # Sort by expected value (descending)
        offer_candidates.sort(key=lambda x: x["expected_value"], reverse=True)

        # Select primary offer
        primary = offer_candidates[0]

        # Select fallback (if available and different enough)
        fallback = None
        if len(offer_candidates) > 1:
            fallback_candidate = offer_candidates[1]
            # Only use as fallback if it's meaningfully different
            if fallback_candidate["expected_value"] > 10:
                fallback = {
                    "offer_type": fallback_candidate["offer_type"],
                    "display_name": fallback_candidate["display_name"],
                    "price": fallback_candidate["final_price"],
                    "p_buy": fallback_candidate["p_buy"]
                }

        reasoning_parts.append(f"\nDecision:")
        reasoning_parts.append(
            f"  PRIMARY: {primary['display_name']} at ${primary['final_price']:.0f} "
            f"(EV: ${primary['expected_value']:.2f})"
        )
        if fallback:
            reasoning_parts.append(
                f"  FALLBACK: {fallback['display_name']} at ${fallback['price']:.0f}"
            )

        full_reasoning = "\n".join(reasoning_parts)

        # Create trace entry
        trace_entry = (
            f"{self.name}: Selected {primary['display_name']} @ ${primary['final_price']:.0f} "
            f"(P(buy)={primary['p_buy']:.2f}, EV=${primary['expected_value']:.2f})"
        )
        if fallback:
            trace_entry += f" | Fallback: {fallback['display_name']}"

        return {
            "selected_offer": primary["offer_type"],
            "offer_price": primary["final_price"],
            "discount_applied": primary["discount"],
            "expected_value": primary["expected_value"],
            "fallback_offer": fallback,
            "offer_reasoning": full_reasoning,
            "should_send_offer": True,
            "reasoning_trace": [trace_entry]
        }

    def _calculate_discount(
        self,
        p_buy: float,
        price_sensitivity: str,
        cabin_priority: str,
        max_discount: float
    ) -> float:
        """
        Calculate optimal discount based on multiple factors.

        Higher discount when:
        - P(buy) is moderate (trying to push over the edge)
        - Customer is price sensitive
        - Cabin priority is high (need to fill seats)
        """
        base_discount = 0

        # Price sensitivity factor
        if price_sensitivity == "high":
            base_discount += 0.10
        elif price_sensitivity == "medium":
            base_discount += 0.05

        # Cabin priority factor
        if cabin_priority == "high":
            base_discount += 0.08
        elif cabin_priority == "medium":
            base_discount += 0.04

        # P(buy) factor - discount more for moderate propensity
        if 0.4 <= p_buy <= 0.7:
            base_discount += 0.05  # Trying to push over the edge

        return min(base_discount, max_discount)

    def _estimate_rules_based_propensity(
        self,
        customer: Dict[str, Any],
        cabin: str
    ) -> float:
        """
        Fallback rules-based propensity when ML score unavailable.

        This handles cold-start customers.
        """
        loyalty_tier = customer.get("loyalty_tier", "General")
        historical = customer.get("historical_upgrades", {})
        acceptance_rate = historical.get("acceptance_rate", 0)

        # Base propensity by loyalty tier
        tier_base = {
            "Executive Platinum": 0.60,
            "Platinum Pro": 0.50,
            "Platinum": 0.40,
            "Gold": 0.35,
            "General": 0.25
        }

        base = tier_base.get(loyalty_tier, 0.25)

        # Adjust by cabin (higher cabins have lower base propensity)
        cabin_multiplier = {
            "business": 0.8,
            "premium_economy": 0.9,
            "main_cabin_extra": 1.1
        }

        base *= cabin_multiplier.get(cabin, 1.0)

        # Adjust by historical acceptance (if available)
        if acceptance_rate > 0:
            base = (base + acceptance_rate) / 2

        return min(base, 0.95)
