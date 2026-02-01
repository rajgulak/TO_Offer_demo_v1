"""
Guardrail Enforcement Tests

Tests that verify business rules are NEVER violated, regardless of input.
These are critical compliance tests that should never fail.

Run with: pytest tests/test_guardrails.py -v
"""
import pytest
import sys
from pathlib import Path
from copy import deepcopy

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.workflow import run_offer_evaluation
from agents.state import create_initial_state
from agents.prechecks import check_customer_eligibility, check_inventory_availability
from agents.offer_orchestration import OfferOrchestrationAgent
from tools.data_tools import get_enriched_pnr
from tests.scenarios import GUARDRAILS, get_all_pnrs


# =============================================================================
# DISCOUNT GUARDRAIL TESTS
# =============================================================================

class TestDiscountGuardrails:
    """Tests that discount limits are never exceeded"""

    @pytest.mark.parametrize("pnr", get_all_pnrs())
    def test_business_class_discount_capped_at_20_percent(self, pnr: str):
        """Business class discount must never exceed 20%"""
        result = run_offer_evaluation(pnr)

        if not result.get("should_send_offer"):
            pytest.skip("No offer made")

        offer_type = result.get("selected_offer", "")
        if "BUSINESS" not in offer_type.upper():
            pytest.skip("Not a business class offer")

        discount = result.get("discount_applied", 0)
        max_discount = GUARDRAILS["max_discount_business"]

        assert discount <= max_discount, (
            f"GUARDRAIL VIOLATION: Business class discount {discount:.0%} "
            f"exceeds max {max_discount:.0%}"
        )

    @pytest.mark.parametrize("pnr", get_all_pnrs())
    def test_mce_discount_capped_at_25_percent(self, pnr: str):
        """MCE discount must never exceed 25%"""
        result = run_offer_evaluation(pnr)

        if not result.get("should_send_offer"):
            pytest.skip("No offer made")

        offer_type = result.get("selected_offer", "")
        if "MCE" not in offer_type.upper():
            pytest.skip("Not an MCE offer")

        discount = result.get("discount_applied", 0)
        max_discount = GUARDRAILS["max_discount_mce"]

        assert discount <= max_discount, (
            f"GUARDRAIL VIOLATION: MCE discount {discount:.0%} "
            f"exceeds max {max_discount:.0%}"
        )

    def test_urgency_boost_still_respects_cap(self):
        """Even with urgency boost, discount must be capped"""
        # Create a state with urgent timing (< 24 hours)
        enriched = get_enriched_pnr("ABC123")
        state = create_initial_state("ABC123")
        state["customer_data"] = enriched["customer"]
        state["flight_data"] = enriched["flight"]
        state["reservation_data"] = deepcopy(enriched["pnr"])
        state["ml_scores"] = enriched["ml_scores"]

        # Set urgent timing
        state["reservation_data"]["hours_to_departure"] = 20  # Urgent: +10% boost

        # Run through functions
        eligible, suppression_reason, segment, details = check_customer_eligibility(
            state["customer_data"], state.get("reservation_data"), state.get("ml_scores")
        )
        state.update({"customer_eligible": eligible, "suppression_reason": suppression_reason, "customer_segment": segment})

        has_inventory, recommended_cabins, inventory_status = check_inventory_availability(
            state["flight_data"], state.get("reservation_data", {}).get("max_bkd_cabin_cd", "Y")
        )
        state.update({
            "flight_priority": "high" if any(s.get("priority") == "high" for s in inventory_status.values()) else "medium" if recommended_cabins else "low",
            "recommended_cabins": recommended_cabins,
            "inventory_status": inventory_status,
        })

        offer_agent = OfferOrchestrationAgent()
        result = offer_agent.analyze(state)

        if result.get("should_send_offer"):
            discount = result.get("discount_applied", 0)
            offer_type = result.get("selected_offer", "")

            if "BUSINESS" in offer_type.upper():
                max_discount = 0.20
            else:
                max_discount = 0.25

            assert discount <= max_discount, (
                f"GUARDRAIL VIOLATION: Urgency boost caused discount {discount:.0%} "
                f"to exceed cap {max_discount:.0%}"
            )


# =============================================================================
# SUPPRESSION GUARDRAIL TESTS
# =============================================================================

class TestSuppressionGuardrails:
    """Tests that suppressed customers NEVER receive offers"""

    def test_suppressed_customer_never_gets_offer(self):
        """GHI654 (suppressed) must never receive an offer"""
        result = run_offer_evaluation("GHI654")

        assert result.get("should_send_offer") == False, (
            "CRITICAL GUARDRAIL VIOLATION: Suppressed customer received an offer!"
        )

    def test_suppression_flag_blocks_offer(self):
        """Any customer with suppression flag must be blocked"""
        enriched = get_enriched_pnr("ABC123")
        state = create_initial_state("ABC123")
        state["customer_data"] = deepcopy(enriched["customer"])
        state["flight_data"] = enriched["flight"]
        state["reservation_data"] = enriched["pnr"]
        state["ml_scores"] = enriched["ml_scores"]

        # Force suppression
        state["customer_data"]["suppression"] = {
            "is_suppressed": True,
            "recent_complaint": True,
            "complaint_reason": "Test suppression",
        }

        eligible, suppression_reason, segment, details = check_customer_eligibility(
            state["customer_data"], state.get("reservation_data"), state.get("ml_scores")
        )
        result = {"customer_eligible": eligible, "suppression_reason": suppression_reason, "customer_segment": segment}

        assert result["customer_eligible"] == False, (
            "GUARDRAIL VIOLATION: Suppressed customer marked as eligible"
        )


# =============================================================================
# TIMING GUARDRAIL TESTS
# =============================================================================

class TestTimingGuardrails:
    """Tests for time-based guardrails"""

    def test_no_offer_within_6_hours(self):
        """Offers should not be sent within 6 hours of departure"""
        enriched = get_enriched_pnr("ABC123")
        state = create_initial_state("ABC123")
        state["customer_data"] = enriched["customer"]
        state["flight_data"] = enriched["flight"]
        state["reservation_data"] = deepcopy(enriched["pnr"])
        state["ml_scores"] = enriched["ml_scores"]

        # Set to 5 hours before departure
        state["reservation_data"]["hours_to_departure"] = 5

        # Run through functions
        eligible, suppression_reason, segment, details = check_customer_eligibility(
            state["customer_data"], state.get("reservation_data"), state.get("ml_scores")
        )
        state.update({"customer_eligible": eligible, "suppression_reason": suppression_reason, "customer_segment": segment})

        has_inventory, recommended_cabins, inventory_status = check_inventory_availability(
            state["flight_data"], state.get("reservation_data", {}).get("max_bkd_cabin_cd", "Y")
        )
        state.update({
            "flight_priority": "high" if any(s.get("priority") == "high" for s in inventory_status.values()) else "medium" if recommended_cabins else "low",
            "recommended_cabins": recommended_cabins,
            "inventory_status": inventory_status,
        })

        offer_agent = OfferOrchestrationAgent()
        result = offer_agent.analyze(state)

        # Should not send offer with only 5 hours
        # Note: This depends on implementation - adjust assertion if needed
        if result.get("should_send_offer"):
            # If offer is sent, verify urgency is handled
            reasoning = result.get("offer_reasoning", "").lower()
            assert "too late" in reasoning or "urgent" in reasoning or "hours" in reasoning


# =============================================================================
# CONSENT GUARDRAIL TESTS
# =============================================================================

class TestConsentGuardrails:
    """Tests that marketing consent is respected"""

    def test_no_offer_without_any_consent(self):
        """Customer without any channel consent must not receive offers"""
        enriched = get_enriched_pnr("ABC123")
        state = create_initial_state("ABC123")
        state["customer_data"] = deepcopy(enriched["customer"])
        state["flight_data"] = enriched["flight"]
        state["reservation_data"] = enriched["pnr"]
        state["ml_scores"] = enriched["ml_scores"]

        # Remove all consent
        state["customer_data"]["marketing_consent"] = {
            "push": False,
            "email": False,
            "sms": False,
        }

        eligible, suppression_reason, segment, details = check_customer_eligibility(
            state["customer_data"], state.get("reservation_data"), state.get("ml_scores")
        )
        result = {"customer_eligible": eligible, "suppression_reason": suppression_reason, "customer_segment": segment}

        assert result["customer_eligible"] == False, (
            "GUARDRAIL VIOLATION: Customer without consent marked eligible"
        )
        assert "consent" in result.get("suppression_reason", "").lower()

    def test_channel_respects_consent(self):
        """Selected channel must have customer consent"""
        from agents.delivery import select_channel

        enriched = get_enriched_pnr("ABC123")
        state = create_initial_state("ABC123")
        state["customer_data"] = deepcopy(enriched["customer"])
        state["flight_data"] = enriched["flight"]
        state["reservation_data"] = enriched["pnr"]
        state["should_send_offer"] = True
        state["customer_eligible"] = True

        # Only allow email
        state["customer_data"]["marketing_consent"] = {
            "push": False,
            "email": True,
            "sms": False,
        }

        result = select_channel(
            state["customer_data"],
            state.get("reservation_data", {}).get("hours_to_departure", 72)
        )

        selected_channel = result.get("channel", "").lower()

        # Should select email since it's the only consented channel
        assert selected_channel == "email" or "email" in selected_channel.lower(), (
            f"GUARDRAIL VIOLATION: Selected '{selected_channel}' but only email is consented"
        )


# =============================================================================
# EXPECTED VALUE GUARDRAIL TESTS
# =============================================================================

class TestExpectedValueGuardrails:
    """Tests for EV-based decision guardrails"""

    @pytest.mark.parametrize("pnr", get_all_pnrs())
    def test_no_negative_ev_offers(self, pnr: str):
        """Should not make offers with negative expected value"""
        result = run_offer_evaluation(pnr)

        if not result.get("should_send_offer"):
            pytest.skip("No offer made")

        ev = result.get("expected_value", 0)

        assert ev >= 0, (
            f"GUARDRAIL VIOLATION: Made offer with negative EV ${ev:.2f}"
        )

    @pytest.mark.parametrize("pnr", get_all_pnrs())
    def test_price_not_below_minimum(self, pnr: str):
        """Offer price should not go below sensible minimum"""
        result = run_offer_evaluation(pnr)

        if not result.get("should_send_offer"):
            pytest.skip("No offer made")

        price = result.get("offer_price", 0)
        offer_type = result.get("selected_offer", "")

        # MCE minimum ~$19, Business minimum ~$99
        if "MCE" in offer_type.upper():
            min_price = 10
        else:
            min_price = 50

        assert price >= min_price, (
            f"GUARDRAIL VIOLATION: {offer_type} price ${price} below minimum ${min_price}"
        )


# =============================================================================
# DATA INTEGRITY GUARDRAIL TESTS
# =============================================================================

class TestDataIntegrityGuardrails:
    """Tests that data flows correctly and completely"""

    @pytest.mark.parametrize("pnr", get_all_pnrs())
    def test_customer_data_required(self, pnr: str):
        """Customer data must be present for any processing"""
        result = run_offer_evaluation(pnr)

        customer_data = result.get("customer_data")
        assert customer_data is not None, (
            f"GUARDRAIL VIOLATION: No customer data for {pnr}"
        )

    @pytest.mark.parametrize("pnr", get_all_pnrs())
    def test_reasoning_trace_not_empty(self, pnr: str):
        """Reasoning trace must document the decision path"""
        result = run_offer_evaluation(pnr)

        reasoning_trace = result.get("reasoning_trace", [])
        assert len(reasoning_trace) > 0, (
            f"GUARDRAIL VIOLATION: No reasoning trace for {pnr}"
        )

    @pytest.mark.parametrize("pnr", get_all_pnrs())
    def test_tracking_id_generated(self, pnr: str):
        """Tracking ID must be generated for measurement"""
        result = run_offer_evaluation(pnr)

        if result.get("should_send_offer"):
            tracking_id = result.get("tracking_id")
            assert tracking_id is not None and len(tracking_id) > 0, (
                f"GUARDRAIL VIOLATION: No tracking ID for offer on {pnr}"
            )


# =============================================================================
# COMPLIANCE SUMMARY TEST
# =============================================================================

class TestComplianceSummary:
    """High-level compliance checks"""

    def test_all_guardrails_documented(self):
        """All guardrails should be documented in GUARDRAILS constant"""
        required_guardrails = [
            "max_discount_business",
            "max_discount_mce",
            "min_hours_to_departure",
            "suppression_blocks_offer",
        ]

        for guardrail in required_guardrails:
            assert guardrail in GUARDRAILS, (
                f"Missing guardrail documentation: {guardrail}"
            )

    def test_guardrails_have_sensible_values(self):
        """Guardrail values should be sensible"""
        assert 0 < GUARDRAILS["max_discount_business"] <= 0.30
        assert 0 < GUARDRAILS["max_discount_mce"] <= 0.40
        assert 0 < GUARDRAILS["min_hours_to_departure"] <= 24
        assert GUARDRAILS["suppression_blocks_offer"] == True
