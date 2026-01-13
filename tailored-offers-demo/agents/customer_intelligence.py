"""
Agent 1: Customer Intelligence Agent

Purpose: Analyzes customer data to determine eligibility and propensity
Data Sources: Loyalty tier, travel history, revenue metrics, preferences
Decisions: Who should receive offers, customer segmentation
"""
from typing import Dict, Any
from .state import AgentState


class CustomerIntelligenceAgent:
    """
    Analyzes customer profile to determine offer eligibility and segmentation.

    This agent answers: "Should we send an offer to this customer?"
    """

    def __init__(self):
        self.name = "Customer Intelligence Agent"

    def analyze(self, state: AgentState) -> Dict[str, Any]:
        """
        Analyze customer eligibility and segment.

        Returns updated state with customer intelligence outputs.
        """
        customer = state.get("customer_data", {})
        reservation = state.get("reservation_data", {})
        ml_scores = state.get("ml_scores", {})

        reasoning_parts = []
        reasoning_parts.append(f"=== {self.name} ===")

        # Check if customer data exists
        if not customer:
            return {
                "customer_eligible": False,
                "customer_segment": "unknown",
                "suppression_reason": "Customer data not found",
                "customer_reasoning": "Cannot evaluate - customer data missing",
                "reasoning_trace": [f"{self.name}: Customer data not found - cannot evaluate"]
            }

        # Extract customer attributes
        first_name = customer.get("first_name", "Customer")
        loyalty_tier = customer.get("loyalty_tier", "General")
        tenure_days = customer.get("tenure_days", 0)
        suppression = customer.get("suppression", {})
        historical = customer.get("historical_upgrades", {})
        annual_revenue = customer.get("annual_revenue", 0)

        reasoning_parts.append(f"Analyzing customer: {first_name}")
        reasoning_parts.append(f"  - Loyalty tier: {loyalty_tier}")
        reasoning_parts.append(f"  - Tenure: {tenure_days} days ({tenure_days // 365} years)")
        reasoning_parts.append(f"  - Annual revenue: ${annual_revenue:,}")

        # Check suppression rules
        if suppression.get("is_suppressed", False):
            reason = "recent_complaint" if suppression.get("recent_complaint") else "manual_suppression"
            complaint_reason = suppression.get("complaint_reason", "Unknown")
            reasoning_parts.append(f"  - SUPPRESSED: {complaint_reason}")
            reasoning_parts.append(f"  Decision: NOT ELIGIBLE (suppression active)")

            return {
                "customer_eligible": False,
                "customer_segment": self._determine_segment(customer),
                "suppression_reason": f"Customer suppressed: {complaint_reason}",
                "customer_reasoning": "\n".join(reasoning_parts),
                "reasoning_trace": [f"{self.name}: Customer {first_name} SUPPRESSED - {complaint_reason}"]
            }

        # Check marketing consent
        consent = customer.get("marketing_consent", {})
        has_any_channel = consent.get("push", False) or consent.get("email", False)
        if not has_any_channel:
            reasoning_parts.append("  - No marketing consent for any channel")
            reasoning_parts.append("  Decision: NOT ELIGIBLE (no consent)")

            return {
                "customer_eligible": False,
                "customer_segment": self._determine_segment(customer),
                "suppression_reason": "No marketing consent",
                "customer_reasoning": "\n".join(reasoning_parts),
                "reasoning_trace": [f"{self.name}: Customer {first_name} has no marketing consent"]
            }

        # Analyze historical upgrade behavior
        acceptance_rate = historical.get("acceptance_rate", 0)
        offers_received = historical.get("offers_received", 0)
        avg_spend = historical.get("avg_upgrade_spend", 0)

        reasoning_parts.append(f"  - Historical acceptance rate: {acceptance_rate:.0%}")
        reasoning_parts.append(f"  - Offers received: {offers_received}")
        reasoning_parts.append(f"  - Avg upgrade spend: ${avg_spend}")

        # Determine segment
        segment = self._determine_segment(customer)
        reasoning_parts.append(f"  - Segment: {segment}")

        # Check ML score confidence
        if ml_scores:
            propensity = ml_scores.get("propensity_scores", {})
            # Find highest confidence score
            max_confidence = 0
            for offer_type, scores in propensity.items():
                conf = scores.get("confidence", 0)
                if conf > max_confidence:
                    max_confidence = conf

            if max_confidence < 0.3:
                reasoning_parts.append(f"  - ML confidence: LOW ({max_confidence:.2f})")
                reasoning_parts.append("  - Will use exploration/rules-based approach")
            else:
                reasoning_parts.append(f"  - ML confidence: {max_confidence:.2f}")

        # Final eligibility decision
        eligible = True
        reasoning_parts.append(f"\n  Decision: ELIGIBLE for offer evaluation")

        # Build detailed reasoning
        full_reasoning = "\n".join(reasoning_parts)

        # Create trace entry
        trace_entry = (
            f"{self.name}: {first_name} ({loyalty_tier}, {tenure_days // 365}yr tenure) - "
            f"ELIGIBLE | Segment: {segment} | "
            f"Historical acceptance: {acceptance_rate:.0%}"
        )

        return {
            "customer_eligible": eligible,
            "customer_segment": segment,
            "suppression_reason": None,
            "customer_reasoning": full_reasoning,
            "reasoning_trace": [trace_entry]
        }

    def _determine_segment(self, customer: Dict[str, Any]) -> str:
        """Determine customer segment based on attributes"""
        loyalty_tier = customer.get("loyalty_tier", "General")
        annual_revenue = customer.get("annual_revenue", 0)
        travel_pattern = customer.get("travel_pattern", "unknown")
        tenure_days = customer.get("tenure_days", 0)

        # High-value segments
        if loyalty_tier in ["Executive Platinum", "Platinum Pro"]:
            if annual_revenue > 50000:
                return "elite_business"
            return "frequent_business"

        # Mid-value segments
        if loyalty_tier in ["Platinum", "Gold"]:
            if travel_pattern == "business":
                return "mid_value_business"
            elif annual_revenue > 10000:
                return "high_value_leisure"
            return "mid_value_leisure"

        # New or low-value
        if tenure_days < 90:
            return "new_customer"

        return "general"
