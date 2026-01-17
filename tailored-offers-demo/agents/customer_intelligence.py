"""
Agent 1: Customer Intelligence Agent

Purpose: Analyzes customer data to determine eligibility and propensity
Data Sources: Loyalty tier, travel history, revenue metrics, preferences
Decisions: Who should receive offers, customer segmentation
"""
from typing import Dict, Any
from .state import AgentState
from .llm_service import generate_dynamic_reasoning


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

        # Check if customer data exists
        if not customer:
            return {
                "customer_eligible": False,
                "customer_segment": "unknown",
                "suppression_reason": "Customer data not found",
                "customer_reasoning": "❌ Cannot evaluate - customer data missing from AADV Database",
                "reasoning_trace": [f"{self.name}: Customer data not found - cannot evaluate"]
            }

        # Extract customer attributes
        first_name = customer.get("first_name", "Customer")
        loyalty_tier = customer.get("loyalty_tier", "General")
        aadv_tenure_days = customer.get("aadv_tenure_days", 0)
        suppression = customer.get("suppression", {})
        historical = customer.get("historical_upgrades", {})
        flight_revenue_amt_history = customer.get("flight_revenue_amt_history", 0)
        consent = customer.get("marketing_consent", {})

        # ========== DATA USED SECTION ==========
        reasoning_parts.append("📊 DATA USED (from MCP Tools):")
        reasoning_parts.append("")
        reasoning_parts.append("┌─ get_customer_profile() → AADV Database")
        reasoning_parts.append(f"│  • Customer: {first_name}")
        reasoning_parts.append(f"│  • Loyalty Tier: {loyalty_tier}")
        reasoning_parts.append(f"│  • Tenure: {aadv_tenure_days} days ({aadv_tenure_days // 365} years)")
        reasoning_parts.append(f"│  • Annual Revenue: ${flight_revenue_amt_history:,}")
        reasoning_parts.append(f"│  • Past Upgrade Acceptance: {historical.get('acceptance_rate', 0):.0%}")
        reasoning_parts.append(f"│  • Avg Upgrade Spend: ${historical.get('avg_upgrade_spend', 0)}")
        reasoning_parts.append("│")
        reasoning_parts.append("├─ get_suppression_status() → CRM System")
        reasoning_parts.append(f"│  • Is Suppressed: {suppression.get('is_suppressed', False)}")
        if suppression.get("is_suppressed"):
            reasoning_parts.append(f"│  • Reason: {suppression.get('complaint_reason', 'Unknown')}")
        reasoning_parts.append("│")
        reasoning_parts.append("└─ Marketing Consent (from Profile)")
        reasoning_parts.append(f"   • Email Consent: {'✓ Yes' if consent.get('email') else '✗ No'}")
        reasoning_parts.append(f"   • Push Consent: {'✓ Yes' if consent.get('push') else '✗ No'}")

        # Check suppression rules
        if suppression.get("is_suppressed", False):
            complaint_reason = suppression.get("complaint_reason", "Unknown")
            reasoning_parts.append("")
            reasoning_parts.append("─" * 50)
            reasoning_parts.append("")
            reasoning_parts.append("🚨 STOP! FOUND A PROBLEM:")
            reasoning_parts.append(f"   {first_name} recently had a bad experience with us.")
            reasoning_parts.append(f"   Complaint: \"{complaint_reason}\"")
            reasoning_parts.append("")
            reasoning_parts.append("❌ DECISION: DO NOT SEND ANY OFFERS")
            reasoning_parts.append("")
            reasoning_parts.append("📍 IN SIMPLE TERMS:")
            reasoning_parts.append(f"   Imagine {first_name} just complained about a delayed flight,")
            reasoning_parts.append("   and then we send them a sales email the next day.")
            reasoning_parts.append("   That would make them even MORE upset!")
            reasoning_parts.append("")
            reasoning_parts.append("💡 WHY THIS AGENT MATTERS:")
            reasoning_parts.append("   A simple ML model only knows: \"This customer might buy.\"")
            reasoning_parts.append("   It has NO IDEA the customer is angry with us.")
            reasoning_parts.append("")
            reasoning_parts.append("   This agent checked the CRM system and PROTECTED us from")
            reasoning_parts.append("   sending an offer that would have backfired badly.")
            reasoning_parts.append("")
            reasoning_parts.append("   🛡️ Disaster avoided. We'll wait until they're happy again.")

            return {
                "customer_eligible": False,
                "customer_segment": self._determine_segment(customer),
                "suppression_reason": f"Customer suppressed: {complaint_reason}",
                "customer_reasoning": "\n".join(reasoning_parts),
                "reasoning_trace": [f"{self.name}: Customer {first_name} SUPPRESSED - {complaint_reason}"]
            }

        # Check marketing consent
        has_any_channel = consent.get("push", False) or consent.get("email", False)
        if not has_any_channel:
            reasoning_parts.append("")
            reasoning_parts.append("─" * 50)
            reasoning_parts.append("")
            reasoning_parts.append("🔍 ANALYSIS:")
            reasoning_parts.append("   Customer has not consented to any marketing channel")
            reasoning_parts.append("")
            reasoning_parts.append("❌ DECISION: NOT ELIGIBLE")
            reasoning_parts.append("")
            reasoning_parts.append("📍 WHY: Cannot send offers without marketing consent.")
            reasoning_parts.append("   This protects customer privacy and complies with regulations.")

            return {
                "customer_eligible": False,
                "customer_segment": self._determine_segment(customer),
                "suppression_reason": "No marketing consent",
                "customer_reasoning": "\n".join(reasoning_parts),
                "reasoning_trace": [f"{self.name}: Customer {first_name} has no marketing consent"]
            }

        # ========== ANALYSIS SECTION ==========
        segment = self._determine_segment(customer)
        acceptance_rate = historical.get("acceptance_rate", 0)
        offers_received = historical.get("offers_received", 0)
        avg_spend = historical.get("avg_upgrade_spend", 0)

        reasoning_parts.append("")
        reasoning_parts.append("─" * 50)
        reasoning_parts.append("")
        reasoning_parts.append("🔍 ANALYSIS:")
        reasoning_parts.append("")

        # Explain segment determination
        tier_names = {"E": "Executive Platinum", "C": "Concierge Key", "T": "Platinum Pro",
                      "P": "Platinum", "G": "Gold", "R": "AAdvantage", "N": "Non-member"}
        tier_display = tier_names.get(loyalty_tier, loyalty_tier)
        reasoning_parts.append(f"   1. Customer Segment: {segment.upper().replace('_', ' ')}")
        if loyalty_tier in ["E", "C", "T"]:
            reasoning_parts.append(f"      → High-tier loyalty ({tier_display}) indicates frequent flyer")
        elif loyalty_tier in ["P", "G"]:
            reasoning_parts.append(f"      → Mid-tier loyalty ({tier_display}) shows engagement potential")
        else:
            reasoning_parts.append(f"      → Standard tier - will use ML scores to guide offer")

        # Explain historical behavior interpretation
        reasoning_parts.append("")
        if acceptance_rate > 0.5:
            reasoning_parts.append(f"   2. Upgrade Behavior: STRONG ({acceptance_rate:.0%} acceptance)")
            reasoning_parts.append(f"      → Has accepted {int(offers_received * acceptance_rate)} of {offers_received} offers")
            reasoning_parts.append(f"      → Avg spend ${avg_spend} shows willingness to pay for upgrades")
        elif acceptance_rate > 0.2:
            reasoning_parts.append(f"   2. Upgrade Behavior: MODERATE ({acceptance_rate:.0%} acceptance)")
            reasoning_parts.append(f"      → Selective buyer - offer quality matters")
        elif offers_received > 0:
            reasoning_parts.append(f"   2. Upgrade Behavior: LOW ({acceptance_rate:.0%} acceptance)")
            reasoning_parts.append(f"      → May need price incentive or right timing")
        else:
            reasoning_parts.append("   2. Upgrade Behavior: NEW (no prior offers)")
            reasoning_parts.append("      → Cold-start: will rely on ML propensity scores")

        # Check ML score confidence
        if ml_scores:
            propensity = ml_scores.get("propensity_scores", {})
            max_confidence = 0
            best_offer = None
            for offer_type, scores in propensity.items():
                conf = scores.get("confidence", 0)
                if conf > max_confidence:
                    max_confidence = conf
                    best_offer = offer_type

            reasoning_parts.append("")
            if max_confidence < 0.3:
                reasoning_parts.append(f"   3. ML Model Confidence: LOW ({max_confidence:.0%})")
                reasoning_parts.append("      → Limited data for this customer profile")
                reasoning_parts.append("      → Will use exploration/rules-based approach")
            else:
                reasoning_parts.append(f"   3. ML Model Confidence: {max_confidence:.0%}")
                reasoning_parts.append(f"      → Model has good signal for {best_offer} offer")

        # ========== TRY DYNAMIC LLM REASONING ==========
        # Collect structured data for LLM
        data_used = {
            "get_customer_profile() → AADV Database": {
                "Customer": first_name,
                "Loyalty Tier": loyalty_tier,
                "Tenure": f"{aadv_tenure_days} days ({aadv_tenure_days // 365} years)",
                "Annual Revenue": f"${flight_revenue_amt_history:,}",
                "Past Upgrade Acceptance": f"{acceptance_rate:.0%}",
                "Avg Upgrade Spend": f"${historical.get('avg_upgrade_spend', 0)}"
            },
            "get_suppression_status() → CRM System": {
                "Is Suppressed": "No"
            },
            "Marketing Consent (from Profile)": {
                "Email Consent": "Yes" if consent.get('email') else "No",
                "Push Consent": "Yes" if consent.get('push') else "No"
            }
        }

        decision_details = {
            "customer_name": first_name,
            "segment": segment,
            "acceptance_rate": f"{acceptance_rate:.0%}",
            "flight_revenue_amt_history": f"${flight_revenue_amt_history:,}",
            "loyalty_tier": loyalty_tier
        }

        # Try dynamic LLM-generated reasoning
        dynamic_reasoning = generate_dynamic_reasoning(
            agent_name=self.name,
            data_used=data_used,
            decision="ELIGIBLE FOR OFFERS",
            decision_details=decision_details,
            context=f"Customer segment: {segment}. This is a rules-based eligibility check."
        )

        if dynamic_reasoning:
            full_reasoning = dynamic_reasoning
        else:
            # Fall back to templated reasoning
            # ========== DECISION SECTION ==========
            reasoning_parts.append("")
            reasoning_parts.append("─" * 50)
            reasoning_parts.append("")
            reasoning_parts.append("✅ DECISION: ELIGIBLE FOR OFFERS")
            reasoning_parts.append("")
            reasoning_parts.append("📍 IN SIMPLE TERMS:")
            reasoning_parts.append(f"   {first_name} is a good candidate for upgrade offers because:")
            reasoning_parts.append(f"   • They're not on our \"do not contact\" list")
            reasoning_parts.append(f"   • They've said yes to receiving marketing messages")
            reasoning_parts.append(f"   • They spend ${flight_revenue_amt_history:,}/year with us - a valuable customer")
            if acceptance_rate > 0:
                reasoning_parts.append(f"   • They've said YES to {acceptance_rate:.0%} of past upgrade offers")

            # ========== WHY AGENTS MATTER ==========
            reasoning_parts.append("")
            reasoning_parts.append("💡 WHY THIS AGENT MATTERS:")
            reasoning_parts.append("   Without this agent, a simple rule might just check:")
            reasoning_parts.append("   \"Is loyalty tier Gold or above? → Send offer\"")
            reasoning_parts.append("")
            reasoning_parts.append("   But this agent checked 3 DIFFERENT SYSTEMS:")
            reasoning_parts.append("   • AADV Database → Customer profile & history")
            reasoning_parts.append("   • CRM System → Are they upset with us?")
            reasoning_parts.append("   • Consent Database → Can we legally contact them?")
            reasoning_parts.append("")
            reasoning_parts.append("   This prevents embarrassing mistakes like sending offers to")
            reasoning_parts.append("   customers who just filed a complaint yesterday.")

            full_reasoning = "\n".join(reasoning_parts)

        # Create trace entry
        trace_entry = (
            f"{self.name}: {first_name} ({loyalty_tier}, {aadv_tenure_days // 365}yr tenure) - "
            f"ELIGIBLE | Segment: {segment} | "
            f"Historical acceptance: {acceptance_rate:.0%}"
        )

        return {
            "customer_eligible": True,
            "customer_segment": segment,
            "suppression_reason": None,
            "customer_reasoning": full_reasoning,
            "reasoning_trace": [trace_entry]
        }

    def _determine_segment(self, customer: Dict[str, Any]) -> str:
        """Determine customer segment based on attributes"""
        loyalty_tier = customer.get("loyalty_tier", "General")
        flight_revenue_amt_history = customer.get("flight_revenue_amt_history", 0)
        business_trip_likelihood = customer.get("business_trip_likelihood", 0)
        aadv_tenure_days = customer.get("aadv_tenure_days", 0)

        # High-value segments (E = Executive Platinum, C = Concierge Key, T = Platinum Pro)
        if loyalty_tier in ["E", "C", "T"]:
            if flight_revenue_amt_history > 50000:
                return "elite_business"
            return "frequent_business"

        # Mid-value segments (P = Platinum, G = Gold)
        if loyalty_tier in ["P", "G"]:
            if business_trip_likelihood > 0.5:
                return "mid_value_business"
            elif flight_revenue_amt_history > 10000:
                return "high_value_leisure"
            return "mid_value_leisure"

        # New or low-value
        if aadv_tenure_days < 90:
            return "new_customer"

        return "general"
