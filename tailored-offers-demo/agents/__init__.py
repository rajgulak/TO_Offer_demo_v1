"""
Tailored Offers Agents

Functional architecture:
1. Prechecks - Customer eligibility & flight inventory checks with reasoning
2. Offer Orchestration (ReWOO) - Multi-offer arbitration via Planner-Worker-Solver
3. Delivery - Personalized messaging, channel selection & tracking setup
"""

# Prechecks: customer eligibility and flight inventory
from .prechecks import (
    check_customer_eligibility,
    check_inventory_availability,
    generate_customer_reasoning,
    generate_flight_reasoning,
)

# ReWOO Pattern: Planner-Worker-Solver for Offer Orchestration
from .offer_orchestration_rewoo import (
    OfferOrchestrationReWOO as OfferOrchestrationAgent,
    stream_offer_orchestration,
)

# Delivery: personalization, channel selection, tracking
from .delivery import (
    generate_message,
    select_channel,
    setup_tracking,
    generate_personalization_reasoning,
    generate_channel_reasoning,
    generate_tracking_reasoning,
)

# Shared state
from .state import AgentState, OfferDecision

__all__ = [
    # Prechecks
    "check_customer_eligibility",
    "check_inventory_availability",
    "generate_customer_reasoning",
    "generate_flight_reasoning",
    # Orchestration
    "OfferOrchestrationAgent",
    "stream_offer_orchestration",
    # Delivery
    "generate_message",
    "select_channel",
    "setup_tracking",
    "generate_personalization_reasoning",
    "generate_channel_reasoning",
    "generate_tracking_reasoning",
    # State
    "AgentState",
    "OfferDecision",
]
