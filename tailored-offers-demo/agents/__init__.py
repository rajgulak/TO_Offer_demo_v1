"""
Tailored Offers Agents

6-Agent Architecture:
1. Customer Intelligence Agent - Eligibility & propensity analysis
2. Flight Optimization Agent - Capacity & revenue optimization
3. Offer Orchestration Agent - Multi-offer arbitration
4. Personalization Agent - GenAI messaging
5. Channel & Timing Agent - Communication optimization
6. Measurement & Learning Agent - A/B testing & feedback
"""

from .customer_intelligence import CustomerIntelligenceAgent
from .flight_optimization import FlightOptimizationAgent
from .offer_orchestration import OfferOrchestrationAgent
from .personalization import PersonalizationAgent
from .channel_timing import ChannelTimingAgent
from .measurement_learning import MeasurementLearningAgent
from .state import AgentState, OfferDecision

__all__ = [
    "CustomerIntelligenceAgent",
    "FlightOptimizationAgent",
    "OfferOrchestrationAgent",
    "PersonalizationAgent",
    "ChannelTimingAgent",
    "MeasurementLearningAgent",
    "AgentState",
    "OfferDecision"
]
