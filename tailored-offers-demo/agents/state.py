"""
Shared state definitions for Tailored Offers Agents
"""
from typing import TypedDict, Optional, List, Dict, Any, Annotated
from dataclasses import dataclass, field
from datetime import datetime
import operator


@dataclass
class OfferDecision:
    """Final offer decision output"""
    offer_type: str  # IU_BUSINESS, IU_PREMIUM_ECONOMY, MCE
    price: float
    discount_percent: float
    channel: str  # push, email, in_app
    send_time: str
    message_subject: str
    message_body: str
    fallback_offer: Optional[Dict[str, Any]] = None
    experiment_group: str = "control"
    tracking_id: str = ""


def merge_reasoning(left: List[str], right: List[str]) -> List[str]:
    """Merge reasoning traces from agents"""
    return left + right


class AgentState(TypedDict):
    """
    Shared state passed between agents in the workflow

    This state accumulates information as each agent processes
    """
    # Input
    pnr_locator: str

    # Raw data (populated by data retrieval)
    customer_data: Optional[Dict[str, Any]]
    flight_data: Optional[Dict[str, Any]]
    reservation_data: Optional[Dict[str, Any]]
    ml_scores: Optional[Dict[str, Any]]

    # Agent 1: Customer Intelligence outputs
    customer_eligible: bool
    customer_segment: str
    suppression_reason: Optional[str]
    customer_reasoning: str

    # Agent 2: Flight Optimization outputs
    flight_priority: str  # high, medium, low
    recommended_cabins: List[str]
    inventory_status: Dict[str, Any]
    flight_reasoning: str

    # Agent 3: Offer Orchestration outputs
    selected_offer: str  # IU_BUSINESS, IU_PREMIUM_ECONOMY, MCE, NONE
    offer_price: float
    discount_applied: float
    expected_value: float
    fallback_offer: Optional[Dict[str, Any]]
    offer_reasoning: str

    # Agent 4: Personalization outputs
    message_subject: str
    message_body: str
    message_tone: str
    personalization_elements: List[str]
    personalization_reasoning: str

    # Agent 5: Channel & Timing outputs
    selected_channel: str  # push, email, in_app
    send_time: str
    backup_channel: Optional[str]
    channel_reasoning: str

    # Agent 6: Measurement & Learning outputs
    experiment_group: str  # control, test_a, test_b, exploration
    tracking_id: str
    measurement_reasoning: str

    # Workflow control
    should_send_offer: bool
    final_decision: Optional[OfferDecision]

    # Reasoning trace (accumulated)
    reasoning_trace: Annotated[List[str], merge_reasoning]

    # Error handling
    errors: List[str]


def create_initial_state(pnr_locator: str) -> AgentState:
    """Create initial state for a new offer evaluation"""
    return AgentState(
        pnr_locator=pnr_locator,
        customer_data=None,
        flight_data=None,
        reservation_data=None,
        ml_scores=None,
        customer_eligible=False,
        customer_segment="unknown",
        suppression_reason=None,
        customer_reasoning="",
        flight_priority="unknown",
        recommended_cabins=[],
        inventory_status={},
        flight_reasoning="",
        selected_offer="NONE",
        offer_price=0.0,
        discount_applied=0.0,
        expected_value=0.0,
        fallback_offer=None,
        offer_reasoning="",
        message_subject="",
        message_body="",
        message_tone="",
        personalization_elements=[],
        personalization_reasoning="",
        selected_channel="",
        send_time="",
        backup_channel=None,
        channel_reasoning="",
        experiment_group="",
        tracking_id="",
        measurement_reasoning="",
        should_send_offer=False,
        final_decision=None,
        reasoning_trace=[],
        errors=[]
    )
