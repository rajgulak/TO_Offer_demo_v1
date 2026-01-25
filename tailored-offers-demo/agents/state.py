"""
Shared state definitions for Tailored Offers Agents
"""
from typing import TypedDict, Optional, List, Dict, Any, Annotated
from dataclasses import dataclass, field
from datetime import datetime
import operator


# =============================================================================
# ReWOO State (for Offer Orchestration sub-graph)
# =============================================================================

@dataclass
class ReWOOPlanStep:
    """A single step in the ReWOO plan"""
    step_id: str           # E1, E2, E3, etc.
    evaluation_type: str   # CONFIDENCE, RELATIONSHIP, PRICE_SENSITIVITY, etc.
    description: str       # Human-readable description
    depends_on: List[str] = field(default_factory=list)  # Dependencies like ["E1", "E2"]


@dataclass
class ReWOOStepResult:
    """Result from executing a single ReWOO step"""
    step_id: str
    evaluation_type: str
    result: Dict[str, Any]
    recommendation: str
    reasoning: str


class ReWOOState(TypedDict):
    """
    State for the ReWOO sub-graph (Planner → Worker → Solver)

    This is separate from AgentState and used internally by the
    Offer Orchestration agent's LangGraph sub-graph.
    """
    # Input context (passed from parent workflow)
    customer_data: Optional[Dict[str, Any]]
    flight_data: Optional[Dict[str, Any]]
    ml_scores: Optional[Dict[str, Any]]
    recommended_cabins: List[str]
    inventory_status: Dict[str, Any]

    # Planner outputs
    plan: List[ReWOOPlanStep]
    plan_reasoning: str

    # Worker outputs (accumulated as each step executes)
    current_step_index: int
    step_results: Dict[str, ReWOOStepResult]  # keyed by step_id

    # Solver outputs
    selected_offer: str
    offer_price: float
    discount_applied: float
    expected_value: float
    solver_reasoning: str
    policies_applied: List[str]

    # Control
    should_send_offer: bool

    # Offer options (built from context)
    offer_options: List[Dict[str, Any]]


def create_rewoo_state(
    customer_data: Dict[str, Any],
    flight_data: Dict[str, Any],
    ml_scores: Dict[str, Any],
    recommended_cabins: List[str],
    inventory_status: Dict[str, Any],
) -> ReWOOState:
    """Create initial ReWOO state from parent workflow data"""
    return ReWOOState(
        customer_data=customer_data,
        flight_data=flight_data,
        ml_scores=ml_scores,
        recommended_cabins=recommended_cabins,
        inventory_status=inventory_status,
        plan=[],
        plan_reasoning="",
        current_step_index=0,
        step_results={},
        selected_offer="NONE",
        offer_price=0.0,
        discount_applied=0.0,
        expected_value=0.0,
        solver_reasoning="",
        policies_applied=[],
        should_send_offer=False,
        offer_options=[],
    )


# =============================================================================
# Main Agent State
# =============================================================================

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
