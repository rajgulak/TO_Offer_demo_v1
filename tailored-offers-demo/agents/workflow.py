"""
Tailored Offers Agentic Workflow

This module defines the LangGraph workflow that orchestrates
all 6 agents in the Tailored Offers system.

Workflow:
1. Load Data → 2. Customer Intelligence → 3. Flight Optimization →
4. Offer Orchestration → 5. Personalization → 6. Channel & Timing →
7. Measurement & Learning → 8. Final Decision
"""
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, END

from .state import AgentState, OfferDecision, create_initial_state
from .customer_intelligence import CustomerIntelligenceAgent
from .flight_optimization import FlightOptimizationAgent
from .offer_orchestration import OfferOrchestrationAgent
from .personalization import PersonalizationAgent
from .channel_timing import ChannelTimingAgent
from .measurement_learning import MeasurementLearningAgent

from tools.data_tools import get_enriched_pnr


# Initialize agents
customer_agent = CustomerIntelligenceAgent()
flight_agent = FlightOptimizationAgent()
offer_agent = OfferOrchestrationAgent()
personalization_agent = PersonalizationAgent()
channel_agent = ChannelTimingAgent()
measurement_agent = MeasurementLearningAgent()


def load_data(state: AgentState) -> Dict[str, Any]:
    """
    Load all required data for the PNR.

    This is the first step - gather all data before agent processing.
    """
    pnr_locator = state["pnr_locator"]

    enriched = get_enriched_pnr(pnr_locator)

    if not enriched:
        return {
            "errors": [f"PNR {pnr_locator} not found"],
            "reasoning_trace": [f"DATA LOAD: PNR {pnr_locator} not found - aborting"]
        }

    return {
        "customer_data": enriched["customer"],
        "flight_data": enriched["flight"],
        "reservation_data": enriched["pnr"],
        "ml_scores": enriched["ml_scores"],
        "reasoning_trace": [
            f"DATA LOAD: Loaded data for PNR {pnr_locator} | "
            f"Customer: {enriched['customer']['first_name']} {enriched['customer']['last_name']} | "
            f"Flight: {enriched['flight']['flight_id']}"
        ]
    }


def run_customer_intelligence(state: AgentState) -> Dict[str, Any]:
    """Run Customer Intelligence Agent"""
    return customer_agent.analyze(state)


def run_flight_optimization(state: AgentState) -> Dict[str, Any]:
    """Run Flight Optimization Agent"""
    return flight_agent.analyze(state)


def run_offer_orchestration(state: AgentState) -> Dict[str, Any]:
    """Run Offer Orchestration Agent"""
    return offer_agent.analyze(state)


def run_personalization(state: AgentState) -> Dict[str, Any]:
    """Run Personalization Agent"""
    return personalization_agent.analyze(state)


def run_channel_timing(state: AgentState) -> Dict[str, Any]:
    """Run Channel & Timing Agent"""
    return channel_agent.analyze(state)


def run_measurement(state: AgentState) -> Dict[str, Any]:
    """Run Measurement & Learning Agent"""
    return measurement_agent.analyze(state)


def compile_final_decision(state: AgentState) -> Dict[str, Any]:
    """
    Compile final offer decision from all agent outputs.

    This is the supervisor's final step - assembling the complete decision.
    """
    reasoning_parts = ["=== FINAL DECISION ==="]

    if not state.get("should_send_offer", False):
        reason = state.get("suppression_reason") or "Offer criteria not met"
        reasoning_parts.append(f"Decision: NO OFFER")
        reasoning_parts.append(f"Reason: {reason}")

        return {
            "final_decision": None,
            "reasoning_trace": [f"SUPERVISOR: Final decision - NO OFFER ({reason})"]
        }

    # Compile the offer decision
    decision = OfferDecision(
        offer_type=state.get("selected_offer", ""),
        price=state.get("offer_price", 0),
        discount_percent=state.get("discount_applied", 0),
        channel=state.get("selected_channel", ""),
        send_time=state.get("send_time", ""),
        message_subject=state.get("message_subject", ""),
        message_body=state.get("message_body", ""),
        fallback_offer=state.get("fallback_offer"),
        experiment_group=state.get("experiment_group", ""),
        tracking_id=state.get("tracking_id", "")
    )

    reasoning_parts.append(f"Decision: SEND OFFER")
    reasoning_parts.append(f"Offer: {decision.offer_type} @ ${decision.price:.0f}")
    reasoning_parts.append(f"Channel: {decision.channel} at {decision.send_time}")
    reasoning_parts.append(f"Experiment: {decision.experiment_group}")
    reasoning_parts.append(f"Tracking: {decision.tracking_id}")

    return {
        "final_decision": decision,
        "reasoning_trace": [
            f"SUPERVISOR: Final decision - SEND {decision.offer_type} @ ${decision.price:.0f} "
            f"via {decision.channel} | Tracking: {decision.tracking_id}"
        ]
    }


def should_continue_after_customer(state: AgentState) -> Literal["flight_optimization", "end"]:
    """Determine if workflow should continue after customer intelligence"""
    if state.get("customer_eligible", False):
        return "flight_optimization"
    return "end"


def should_continue_after_offer(state: AgentState) -> Literal["personalization", "end"]:
    """Determine if workflow should continue after offer orchestration"""
    if state.get("should_send_offer", False):
        return "personalization"
    return "end"


def create_workflow() -> StateGraph:
    """
    Create the LangGraph workflow for Tailored Offers.

    Returns a compiled workflow graph.
    """
    # Create the graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("load_data", load_data)
    workflow.add_node("customer_intelligence", run_customer_intelligence)
    workflow.add_node("flight_optimization", run_flight_optimization)
    workflow.add_node("offer_orchestration", run_offer_orchestration)
    workflow.add_node("personalization", run_personalization)
    workflow.add_node("channel_timing", run_channel_timing)
    workflow.add_node("measurement", run_measurement)
    workflow.add_node("final_decision", compile_final_decision)

    # Set entry point
    workflow.set_entry_point("load_data")

    # Add edges
    workflow.add_edge("load_data", "customer_intelligence")

    # Conditional edge after customer intelligence
    workflow.add_conditional_edges(
        "customer_intelligence",
        should_continue_after_customer,
        {
            "flight_optimization": "flight_optimization",
            "end": "final_decision"
        }
    )

    workflow.add_edge("flight_optimization", "offer_orchestration")

    # Conditional edge after offer orchestration
    workflow.add_conditional_edges(
        "offer_orchestration",
        should_continue_after_offer,
        {
            "personalization": "personalization",
            "end": "final_decision"
        }
    )

    workflow.add_edge("personalization", "channel_timing")
    workflow.add_edge("channel_timing", "measurement")
    workflow.add_edge("measurement", "final_decision")
    workflow.add_edge("final_decision", END)

    return workflow


def run_offer_evaluation(pnr_locator: str) -> Dict[str, Any]:
    """
    Run the complete offer evaluation workflow for a PNR.

    Args:
        pnr_locator: The PNR to evaluate

    Returns:
        Dictionary with final state including decision and reasoning trace
    """
    # Create workflow
    workflow = create_workflow()
    app = workflow.compile()

    # Create initial state
    initial_state = create_initial_state(pnr_locator)

    # Run the workflow
    final_state = app.invoke(initial_state)

    return final_state


def run_offer_evaluation_streaming(pnr_locator: str):
    """
    Run workflow with streaming to show agent-by-agent progress.

    Yields state updates as each agent completes.
    """
    workflow = create_workflow()
    app = workflow.compile()

    initial_state = create_initial_state(pnr_locator)

    # Stream the execution
    for event in app.stream(initial_state):
        yield event
