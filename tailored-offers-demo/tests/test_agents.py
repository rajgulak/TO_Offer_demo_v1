"""
Agent Unit Tests

Tests for individual agent behavior in isolation.
Each agent's function is tested with controlled inputs.

Run with: pytest tests/test_agents.py -v
"""
import pytest
import sys
from pathlib import Path
from copy import deepcopy

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.state import create_initial_state
from agents.prechecks import check_customer_eligibility, check_inventory_availability
from agents.delivery import generate_message, select_channel, setup_tracking
from agents.offer_orchestration import OfferOrchestrationAgent
from tools.data_tools import get_enriched_pnr


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def base_state():
    """Create a base state with ABC123 data for testing"""
    enriched = get_enriched_pnr("ABC123")
    state = create_initial_state("ABC123")
    state["customer_data"] = enriched["customer"]
    state["flight_data"] = enriched["flight"]
    state["reservation_data"] = enriched["pnr"]
    state["ml_scores"] = enriched["ml_scores"]
    return state


@pytest.fixture
def suppressed_state():
    """Create state with suppressed customer (GHI654)"""
    enriched = get_enriched_pnr("GHI654")
    state = create_initial_state("GHI654")
    state["customer_data"] = enriched["customer"]
    state["flight_data"] = enriched["flight"]
    state["reservation_data"] = enriched["pnr"]
    state["ml_scores"] = enriched["ml_scores"]
    return state


@pytest.fixture
def offer_agent():
    return OfferOrchestrationAgent()


# =============================================================================
# CUSTOMER INTELLIGENCE AGENT TESTS
# =============================================================================

class TestCustomerIntelligenceAgent:
    """Tests for check_customer_eligibility"""

    def test_eligible_customer_returns_true(self, base_state):
        """Non-suppressed customer with consent should be eligible"""
        eligible, suppression_reason, segment, details = check_customer_eligibility(
            base_state["customer_data"], base_state.get("reservation_data"), base_state.get("ml_scores")
        )
        result = {"customer_eligible": eligible, "suppression_reason": suppression_reason, "customer_segment": segment}

        assert result["customer_eligible"] == True
        assert result["suppression_reason"] is None
        assert "customer_segment" in result

    def test_suppressed_customer_returns_false(self, suppressed_state):
        """Suppressed customer must be marked ineligible"""
        eligible, suppression_reason, segment, details = check_customer_eligibility(
            suppressed_state["customer_data"], suppressed_state.get("reservation_data"), suppressed_state.get("ml_scores")
        )
        result = {"customer_eligible": eligible, "suppression_reason": suppression_reason, "customer_segment": segment}

        assert result["customer_eligible"] == False
        assert result["suppression_reason"] is not None
        # Suppression reason should indicate customer is suppressed
        # (may contain "suppressed", the complaint reason, or both)
        reason_lower = result["suppression_reason"].lower()
        assert "suppressed" in reason_lower or "baggage" in reason_lower or "complaint" in reason_lower

    def test_no_consent_returns_false(self, base_state):
        """Customer without any marketing consent should be ineligible"""
        state = deepcopy(base_state)
        state["customer_data"]["marketing_consent"] = {
            "push": False,
            "email": False,
            "sms": False,
        }

        eligible, suppression_reason, segment, details = check_customer_eligibility(
            state["customer_data"], state.get("reservation_data"), state.get("ml_scores")
        )
        result = {"customer_eligible": eligible, "suppression_reason": suppression_reason, "customer_segment": segment}

        assert result["customer_eligible"] == False
        assert "consent" in result["suppression_reason"].lower()

    def test_returns_customer_segment(self, base_state):
        """Function must return a customer segment"""
        eligible, suppression_reason, segment, details = check_customer_eligibility(
            base_state["customer_data"], base_state.get("reservation_data"), base_state.get("ml_scores")
        )
        result = {"customer_eligible": eligible, "suppression_reason": suppression_reason, "customer_segment": segment}

        assert "customer_segment" in result
        assert result["customer_segment"] is not None
        assert len(result["customer_segment"]) > 0


# =============================================================================
# FLIGHT OPTIMIZATION AGENT TESTS
# =============================================================================

class TestFlightOptimizationAgent:
    """Tests for check_inventory_availability"""

    def _get_result(self, state):
        has_inventory, recommended_cabins, inventory_status = check_inventory_availability(
            state["flight_data"], state.get("reservation_data", {}).get("max_bkd_cabin_cd", "Y")
        )
        return {
            "flight_priority": "high" if any(s.get("priority") == "high" for s in inventory_status.values()) else "medium" if recommended_cabins else "low",
            "recommended_cabins": recommended_cabins,
            "inventory_status": inventory_status,
        }

    def test_returns_flight_priority(self, base_state):
        """Function must return flight priority"""
        result = self._get_result(base_state)

        assert "flight_priority" in result
        assert result["flight_priority"] in ["high", "medium", "low"]

    def test_returns_recommended_cabins(self, base_state):
        """Function must return recommended cabins list"""
        result = self._get_result(base_state)

        assert "recommended_cabins" in result
        assert isinstance(result["recommended_cabins"], list)

    def test_returns_inventory_status(self, base_state):
        """Function must return inventory status"""
        result = self._get_result(base_state)

        assert "inventory_status" in result
        assert isinstance(result["inventory_status"], dict)


# =============================================================================
# OFFER ORCHESTRATION AGENT TESTS
# =============================================================================

class TestOfferOrchestrationAgent:
    """Tests for OfferOrchestrationAgent (the core decision agent)"""

    def _prepare_state(self, state):
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

    def test_returns_decision_when_eligible(self, offer_agent, base_state):
        """Agent must return offer decision for eligible customer"""
        self._prepare_state(base_state)

        result = offer_agent.analyze(base_state)

        assert "selected_offer" in result
        assert "offer_price" in result
        assert "should_send_offer" in result

    def test_skips_ineligible_customer(self, offer_agent, suppressed_state):
        """Agent should not offer to ineligible customer"""
        eligible, suppression_reason, segment, details = check_customer_eligibility(
            suppressed_state["customer_data"], suppressed_state.get("reservation_data"), suppressed_state.get("ml_scores")
        )
        suppressed_state.update({"customer_eligible": eligible, "suppression_reason": suppression_reason, "customer_segment": segment})

        result = offer_agent.analyze(suppressed_state)

        assert result.get("should_send_offer") == False

    def test_returns_expected_value(self, offer_agent, base_state):
        """Agent must calculate and return expected value"""
        self._prepare_state(base_state)

        result = offer_agent.analyze(base_state)

        if result.get("should_send_offer"):
            assert "expected_value" in result
            assert result["expected_value"] > 0

    def test_returns_reasoning(self, offer_agent, base_state):
        """Agent must provide detailed reasoning"""
        self._prepare_state(base_state)

        result = offer_agent.analyze(base_state)

        assert "offer_reasoning" in result
        assert len(result["offer_reasoning"]) > 100  # Detailed reasoning expected


# =============================================================================
# PERSONALIZATION AGENT TESTS
# =============================================================================

class TestPersonalizationAgent:
    """Tests for generate_message"""

    def test_generates_message_when_offering(self, base_state):
        """Function must generate message when there's an offer"""
        result = generate_message(
            base_state["customer_data"], base_state["flight_data"],
            "MCE", 49
        )

        message_subject = result["subject"]
        message_body = result["body"]
        assert len(message_subject) > 0
        assert len(message_body) > 50

    def test_message_includes_customer_name(self, base_state):
        """Message should be personalized with customer name"""
        result = generate_message(
            base_state["customer_data"], base_state["flight_data"],
            "MCE", 49
        )

        customer_name = base_state["customer_data"]["first_name"]
        message_body = result.get("body", "")

        assert customer_name in message_body, (
            f"Message should include customer name '{customer_name}'"
        )


# =============================================================================
# CHANNEL & TIMING AGENT TESTS
# =============================================================================

class TestChannelTimingAgent:
    """Tests for select_channel"""

    def test_selects_channel_based_on_consent(self, base_state):
        """Function should only select channels customer consented to"""
        result = select_channel(
            base_state["customer_data"],
            base_state.get("reservation_data", {}).get("hours_to_departure", 72)
        )

        selected = result["channel"].lower()

        # Check consent
        consent = base_state["customer_data"]["marketing_consent"]
        if selected == "push":
            assert consent.get("push", False)
        elif selected == "email":
            assert consent.get("email", False)
        elif selected == "sms":
            assert consent.get("sms", False)

    def test_returns_send_time(self, base_state):
        """Function must return send time"""
        result = select_channel(
            base_state["customer_data"],
            base_state.get("reservation_data", {}).get("hours_to_departure", 72)
        )

        assert "send_time" in result
        assert len(result["send_time"]) > 0


# =============================================================================
# MEASUREMENT & LEARNING AGENT TESTS
# =============================================================================

class TestMeasurementLearningAgent:
    """Tests for setup_tracking"""

    def test_assigns_experiment_group(self, base_state):
        """Function must assign an experiment group"""
        result = setup_tracking("ABC123", "MCE")

        assert "experiment_group" in result
        valid_groups = ["control", "treatment", "exploration", "test_model_v1", "test_model_v2"]
        assert result["experiment_group"] in valid_groups, f"Unexpected group: {result['experiment_group']}"

    def test_generates_tracking_id(self, base_state):
        """Function must generate a tracking ID"""
        result = setup_tracking("ABC123", "MCE")

        assert "tracking_id" in result
        assert len(result["tracking_id"]) > 10
        assert "ABC123" in result["tracking_id"]  # Should include PNR

    def test_tracking_id_unique(self, base_state):
        """Tracking IDs should be unique across calls"""
        result1 = setup_tracking("ABC123", "MCE")
        result2 = setup_tracking("ABC123", "MCE")

        # IDs should be different (includes timestamp + random)
        assert result1["tracking_id"] != result2["tracking_id"]


# =============================================================================
# AGENT INTERFACE COMPLIANCE TESTS
# =============================================================================

class TestAgentInterfaces:
    """Tests that all functions comply with expected interface"""

    def test_check_customer_eligibility_returns_tuple(self, base_state):
        """check_customer_eligibility must return a 4-tuple"""
        result = check_customer_eligibility(
            base_state["customer_data"], base_state.get("reservation_data"), base_state.get("ml_scores")
        )
        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_check_inventory_availability_returns_tuple(self, base_state):
        """check_inventory_availability must return a 3-tuple"""
        result = check_inventory_availability(
            base_state["flight_data"], base_state.get("reservation_data", {}).get("max_bkd_cabin_cd", "Y")
        )
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_generate_message_returns_dict(self, base_state):
        """generate_message must return a dict with subject, body, tone"""
        result = generate_message(
            base_state["customer_data"], base_state["flight_data"], "MCE", 49
        )
        assert isinstance(result, dict)
        assert "subject" in result
        assert "body" in result
        assert "tone" in result

    def test_select_channel_returns_dict(self, base_state):
        """select_channel must return a dict with channel, send_time"""
        result = select_channel(
            base_state["customer_data"],
            base_state.get("reservation_data", {}).get("hours_to_departure", 72)
        )
        assert isinstance(result, dict)
        assert "channel" in result
        assert "send_time" in result

    def test_setup_tracking_returns_dict(self):
        """setup_tracking must return a dict with experiment_group, tracking_id"""
        result = setup_tracking("ABC123", "MCE")
        assert isinstance(result, dict)
        assert "experiment_group" in result
        assert "tracking_id" in result

    def test_offer_orchestration_has_analyze(self):
        """OfferOrchestrationAgent must have analyze() method"""
        agent = OfferOrchestrationAgent()
        assert hasattr(agent, "analyze")
        assert callable(getattr(agent, "analyze"))
