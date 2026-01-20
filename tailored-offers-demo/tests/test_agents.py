"""
Agent Unit Tests

Tests for individual agent behavior in isolation.
Each agent's analyze() method is tested with controlled inputs.

Run with: pytest tests/test_agents.py -v
"""
import pytest
import sys
from pathlib import Path
from copy import deepcopy

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.state import create_initial_state
from agents.customer_intelligence import CustomerIntelligenceAgent
from agents.flight_optimization import FlightOptimizationAgent
from agents.offer_orchestration import OfferOrchestrationAgent
from agents.personalization import PersonalizationAgent
from agents.channel_timing import ChannelTimingAgent
from agents.measurement_learning import MeasurementLearningAgent
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
def customer_agent():
    return CustomerIntelligenceAgent()


@pytest.fixture
def flight_agent():
    return FlightOptimizationAgent()


@pytest.fixture
def offer_agent():
    return OfferOrchestrationAgent()


@pytest.fixture
def personalization_agent():
    return PersonalizationAgent()


@pytest.fixture
def channel_agent():
    return ChannelTimingAgent()


@pytest.fixture
def measurement_agent():
    return MeasurementLearningAgent()


# =============================================================================
# CUSTOMER INTELLIGENCE AGENT TESTS
# =============================================================================

class TestCustomerIntelligenceAgent:
    """Tests for CustomerIntelligenceAgent"""

    def test_eligible_customer_returns_true(self, customer_agent, base_state):
        """Non-suppressed customer with consent should be eligible"""
        result = customer_agent.analyze(base_state)

        assert result["customer_eligible"] == True
        assert result["suppression_reason"] is None
        assert "customer_segment" in result

    def test_suppressed_customer_returns_false(self, customer_agent, suppressed_state):
        """Suppressed customer must be marked ineligible"""
        result = customer_agent.analyze(suppressed_state)

        assert result["customer_eligible"] == False
        assert result["suppression_reason"] is not None
        # Suppression reason should indicate customer is suppressed
        # (may contain "suppressed", the complaint reason, or both)
        reason_lower = result["suppression_reason"].lower()
        assert "suppressed" in reason_lower or "baggage" in reason_lower or "complaint" in reason_lower

    def test_no_consent_returns_false(self, customer_agent, base_state):
        """Customer without any marketing consent should be ineligible"""
        state = deepcopy(base_state)
        state["customer_data"]["marketing_consent"] = {
            "push": False,
            "email": False,
            "sms": False,
        }

        result = customer_agent.analyze(state)

        assert result["customer_eligible"] == False
        assert "consent" in result["suppression_reason"].lower()

    def test_returns_customer_segment(self, customer_agent, base_state):
        """Agent must return a customer segment"""
        result = customer_agent.analyze(base_state)

        assert "customer_segment" in result
        assert result["customer_segment"] is not None
        assert len(result["customer_segment"]) > 0

    def test_returns_reasoning(self, customer_agent, base_state):
        """Agent must provide reasoning"""
        result = customer_agent.analyze(base_state)

        assert "customer_reasoning" in result
        assert len(result["customer_reasoning"]) > 50


# =============================================================================
# FLIGHT OPTIMIZATION AGENT TESTS
# =============================================================================

class TestFlightOptimizationAgent:
    """Tests for FlightOptimizationAgent"""

    def test_returns_flight_priority(self, flight_agent, base_state):
        """Agent must return flight priority"""
        result = flight_agent.analyze(base_state)

        assert "flight_priority" in result
        assert result["flight_priority"] in ["high", "medium", "low"]

    def test_returns_recommended_cabins(self, flight_agent, base_state):
        """Agent must return recommended cabins list"""
        result = flight_agent.analyze(base_state)

        assert "recommended_cabins" in result
        assert isinstance(result["recommended_cabins"], list)

    def test_returns_inventory_status(self, flight_agent, base_state):
        """Agent must return inventory status"""
        result = flight_agent.analyze(base_state)

        assert "inventory_status" in result
        assert isinstance(result["inventory_status"], dict)

    def test_returns_reasoning(self, flight_agent, base_state):
        """Agent must provide reasoning"""
        result = flight_agent.analyze(base_state)

        assert "flight_reasoning" in result
        assert len(result["flight_reasoning"]) > 50


# =============================================================================
# OFFER ORCHESTRATION AGENT TESTS
# =============================================================================

class TestOfferOrchestrationAgent:
    """Tests for OfferOrchestrationAgent (the core decision agent)"""

    def test_returns_decision_when_eligible(self, offer_agent, base_state):
        """Agent must return offer decision for eligible customer"""
        # First run customer intelligence to set eligibility
        customer_agent = CustomerIntelligenceAgent()
        customer_result = customer_agent.analyze(base_state)
        base_state.update(customer_result)

        # Then run flight optimization
        flight_agent = FlightOptimizationAgent()
        flight_result = flight_agent.analyze(base_state)
        base_state.update(flight_result)

        # Now run offer orchestration
        result = offer_agent.analyze(base_state)

        assert "selected_offer" in result
        assert "offer_price" in result
        assert "should_send_offer" in result

    def test_skips_ineligible_customer(self, offer_agent, suppressed_state):
        """Agent should not offer to ineligible customer"""
        # First run customer intelligence
        customer_agent = CustomerIntelligenceAgent()
        customer_result = customer_agent.analyze(suppressed_state)
        suppressed_state.update(customer_result)

        result = offer_agent.analyze(suppressed_state)

        assert result.get("should_send_offer") == False

    def test_returns_expected_value(self, offer_agent, base_state):
        """Agent must calculate and return expected value"""
        customer_agent = CustomerIntelligenceAgent()
        customer_result = customer_agent.analyze(base_state)
        base_state.update(customer_result)

        flight_agent = FlightOptimizationAgent()
        flight_result = flight_agent.analyze(base_state)
        base_state.update(flight_result)

        result = offer_agent.analyze(base_state)

        if result.get("should_send_offer"):
            assert "expected_value" in result
            assert result["expected_value"] > 0

    def test_returns_reasoning(self, offer_agent, base_state):
        """Agent must provide detailed reasoning"""
        customer_agent = CustomerIntelligenceAgent()
        base_state.update(customer_agent.analyze(base_state))

        flight_agent = FlightOptimizationAgent()
        base_state.update(flight_agent.analyze(base_state))

        result = offer_agent.analyze(base_state)

        assert "offer_reasoning" in result
        assert len(result["offer_reasoning"]) > 100  # Detailed reasoning expected


# =============================================================================
# PERSONALIZATION AGENT TESTS
# =============================================================================

class TestPersonalizationAgent:
    """Tests for PersonalizationAgent (LLM-powered)"""

    def test_generates_message_when_offering(self, personalization_agent, base_state):
        """Agent must generate message when there's an offer"""
        # Set up state with an offer
        base_state["should_send_offer"] = True
        base_state["selected_offer"] = "MCE"
        base_state["offer_price"] = 49
        base_state["customer_eligible"] = True

        result = personalization_agent.analyze(base_state)

        assert "message_subject" in result
        assert "message_body" in result
        assert len(result["message_subject"]) > 0
        assert len(result["message_body"]) > 50

    def test_skips_when_no_offer(self, personalization_agent, base_state):
        """Agent should skip personalization when no offer"""
        base_state["should_send_offer"] = False

        result = personalization_agent.analyze(base_state)

        # Should still return fields but may be empty
        assert "message_subject" in result or "personalization_reasoning" in result

    def test_message_includes_customer_name(self, personalization_agent, base_state):
        """Message should be personalized with customer name"""
        base_state["should_send_offer"] = True
        base_state["selected_offer"] = "MCE"
        base_state["offer_price"] = 49
        base_state["customer_eligible"] = True

        result = personalization_agent.analyze(base_state)

        customer_name = base_state["customer_data"]["first_name"]
        message_body = result.get("message_body", "")

        assert customer_name in message_body, (
            f"Message should include customer name '{customer_name}'"
        )


# =============================================================================
# CHANNEL & TIMING AGENT TESTS
# =============================================================================

class TestChannelTimingAgent:
    """Tests for ChannelTimingAgent"""

    def test_selects_channel_based_on_consent(self, channel_agent, base_state):
        """Agent should only select channels customer consented to"""
        base_state["should_send_offer"] = True
        base_state["customer_eligible"] = True

        result = channel_agent.analyze(base_state)

        assert "selected_channel" in result
        selected = result["selected_channel"].lower()

        # Check consent
        consent = base_state["customer_data"]["marketing_consent"]
        if selected == "push":
            assert consent.get("push", False)
        elif selected == "email":
            assert consent.get("email", False)
        elif selected == "sms":
            assert consent.get("sms", False)

    def test_returns_send_time(self, channel_agent, base_state):
        """Agent must return send time"""
        base_state["should_send_offer"] = True
        base_state["customer_eligible"] = True

        result = channel_agent.analyze(base_state)

        assert "send_time" in result
        assert len(result["send_time"]) > 0

    def test_returns_reasoning(self, channel_agent, base_state):
        """Agent must provide reasoning"""
        base_state["should_send_offer"] = True
        base_state["customer_eligible"] = True

        result = channel_agent.analyze(base_state)

        assert "channel_reasoning" in result


# =============================================================================
# MEASUREMENT & LEARNING AGENT TESTS
# =============================================================================

class TestMeasurementLearningAgent:
    """Tests for MeasurementLearningAgent (Tracking Setup)"""

    def test_assigns_experiment_group(self, measurement_agent, base_state):
        """Agent must assign an experiment group"""
        base_state["should_send_offer"] = True

        result = measurement_agent.analyze(base_state)

        assert "experiment_group" in result
        # Experiment groups can be control, treatment variants, or model versions
        valid_groups = ["control", "treatment", "exploration", "test_model_v1", "test_model_v2"]
        assert result["experiment_group"] in valid_groups, f"Unexpected group: {result['experiment_group']}"

    def test_generates_tracking_id(self, measurement_agent, base_state):
        """Agent must generate a tracking ID"""
        base_state["should_send_offer"] = True

        result = measurement_agent.analyze(base_state)

        assert "tracking_id" in result
        assert len(result["tracking_id"]) > 10
        assert "ABC123" in result["tracking_id"]  # Should include PNR

    def test_tracking_id_unique(self, measurement_agent, base_state):
        """Tracking IDs should be unique across calls"""
        base_state["should_send_offer"] = True

        result1 = measurement_agent.analyze(base_state)
        result2 = measurement_agent.analyze(base_state)

        # IDs should be different (includes timestamp + random)
        assert result1["tracking_id"] != result2["tracking_id"]


# =============================================================================
# AGENT INTERFACE COMPLIANCE TESTS
# =============================================================================

class TestAgentInterfaces:
    """Tests that all agents comply with expected interface"""

    @pytest.fixture
    def all_agents(self):
        return [
            CustomerIntelligenceAgent(),
            FlightOptimizationAgent(),
            OfferOrchestrationAgent(),
            PersonalizationAgent(),
            ChannelTimingAgent(),
            MeasurementLearningAgent(),
        ]

    def test_all_agents_have_analyze_method(self, all_agents):
        """All agents must have analyze() method"""
        for agent in all_agents:
            assert hasattr(agent, "analyze")
            assert callable(getattr(agent, "analyze"))

    def test_analyze_returns_dict(self, all_agents, base_state):
        """analyze() must return a dictionary"""
        for agent in all_agents:
            result = agent.analyze(base_state)
            assert isinstance(result, dict), (
                f"{agent.__class__.__name__}.analyze() must return dict"
            )

    def test_analyze_includes_reasoning(self, all_agents, base_state):
        """Each agent should include reasoning in output"""
        reasoning_keys = [
            "customer_reasoning",
            "flight_reasoning",
            "offer_reasoning",
            "personalization_reasoning",
            "channel_reasoning",
            "measurement_reasoning",
        ]

        for agent in all_agents:
            result = agent.analyze(base_state)

            # At least one reasoning key should be present
            has_reasoning = any(key in result for key in reasoning_keys)
            assert has_reasoning, (
                f"{agent.__class__.__name__} should include reasoning in output"
            )
