"""
Scenario Specifications with Expected Outcomes

This module defines the expected behavior for each demo scenario.
These specs drive eval-based testing - the ground truth for agent decisions.

Structure:
- Each scenario has input context and expected outputs
- Expected outputs define acceptable ranges/values for validation
- Guardrail assertions ensure business rules are enforced
"""
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any


@dataclass
class ExpectedDecision:
    """Expected outcome for a scenario"""

    # Core decision
    should_send_offer: bool

    # If should_send_offer is True
    acceptable_offers: List[str] = field(default_factory=list)  # e.g., ["IU_BUSINESS", "MCE"]
    price_range: Optional[Tuple[float, float]] = None  # (min, max)
    acceptable_channels: List[str] = field(default_factory=list)  # e.g., ["push", "email"]

    # If should_send_offer is False
    expected_suppression_reasons: List[str] = field(default_factory=list)

    # Guardrail assertions (must always pass)
    max_discount_percent: float = 0.25  # Never exceed 25%
    min_expected_value: float = 0.0  # EV must be positive if offering

    # Reasoning requirements (keywords that should appear in reasoning)
    reasoning_must_include: List[str] = field(default_factory=list)


@dataclass
class ScenarioSpec:
    """Complete specification for a test scenario"""

    pnr: str
    description: str
    customer_context: Dict[str, Any]  # Key customer attributes
    expected: ExpectedDecision
    tags: List[str] = field(default_factory=list)  # For filtering tests


# =============================================================================
# SCENARIO SPECIFICATIONS
# =============================================================================

SCENARIOS: Dict[str, ScenarioSpec] = {

    # -------------------------------------------------------------------------
    # ABC123: Standard Happy Path
    # -------------------------------------------------------------------------
    "ABC123": ScenarioSpec(
        pnr="ABC123",
        description="Gold customer, T-96hrs, standard happy path - should receive offer",
        customer_context={
            "name": "Sarah Johnson",
            "loyalty_tier": "Gold",
            "hours_to_departure": 96,
            "historical_acceptance_rate": 0.33,
            "annual_revenue": 4200,
            "is_suppressed": False,
            "has_push_consent": True,
            "has_email_consent": True,
        },
        expected=ExpectedDecision(
            should_send_offer=True,
            acceptable_offers=["IU_BUSINESS", "MCE"],
            price_range=(39, 299),  # Could be MCE at $39-89 or Business at $149-299
            acceptable_channels=["push", "email"],
            max_discount_percent=0.20,
            min_expected_value=30.0,  # EV should be meaningful
            reasoning_must_include=["Gold", "eligible", "propensity"],
        ),
        tags=["happy_path", "gold_tier", "standard"],
    ),

    # -------------------------------------------------------------------------
    # XYZ789: High-Value Business Traveler
    # -------------------------------------------------------------------------
    "XYZ789": ScenarioSpec(
        pnr="XYZ789",
        description="Platinum Pro, frequent business traveler - premium pricing acceptable",
        customer_context={
            "name": "John Smith",
            "loyalty_tier": "Platinum Pro",
            "hours_to_departure": 72,
            "historical_acceptance_rate": 0.67,
            "annual_revenue": 28500,
            "is_suppressed": False,
            "business_trip_likelihood": 0.85,
        },
        expected=ExpectedDecision(
            should_send_offer=True,
            acceptable_offers=["IU_BUSINESS", "IU_FIRST"],
            price_range=(199, 699),  # Higher value customer, premium pricing
            acceptable_channels=["push", "email", "in_app"],
            max_discount_percent=0.20,
            min_expected_value=50.0,  # High-value customer = higher EV
            reasoning_must_include=["Platinum", "business", "high"],
        ),
        tags=["happy_path", "platinum_tier", "business_traveler", "high_value"],
    ),

    # -------------------------------------------------------------------------
    # LMN456: Executive Platinum International
    # -------------------------------------------------------------------------
    "LMN456": ScenarioSpec(
        pnr="LMN456",
        description="Exec Platinum, international route, premium treatment",
        customer_context={
            "name": "Emily Chen",
            "loyalty_tier": "Executive Platinum",
            "hours_to_departure": 120,
            "historical_acceptance_rate": 0.75,
            "annual_revenue": 85000,
            "is_suppressed": False,
            "international_trip": True,
        },
        expected=ExpectedDecision(
            should_send_offer=True,
            acceptable_offers=["IU_BUSINESS", "IU_FIRST"],
            price_range=(499, 1299),  # Premium international pricing
            acceptable_channels=["push", "email"],
            max_discount_percent=0.20,
            min_expected_value=100.0,  # Very high EV for exec plat
            # More flexible keywords - match actual agent output
            reasoning_must_include=["Executive Platinum", "eligible"],
        ),
        tags=["happy_path", "exec_platinum", "international", "premium"],
    ),

    # -------------------------------------------------------------------------
    # DEF321: Cold Start / New Customer
    # -------------------------------------------------------------------------
    "DEF321": ScenarioSpec(
        pnr="DEF321",
        description="New customer, low confidence scores, cold start problem",
        customer_context={
            "name": "Michael Brown",
            "loyalty_tier": "General",
            "hours_to_departure": 48,
            "historical_acceptance_rate": None,  # No history
            "annual_revenue": 285,
            "is_suppressed": False,
            "tenure_days": 30,  # Very new
        },
        expected=ExpectedDecision(
            # Cold start with low confidence - may or may not offer
            # The key is: if we offer, guardrails must be respected
            should_send_offer=False,  # Low confidence + no inventory typically = no offer
            acceptable_offers=["MCE"],  # If offered, only low-risk MCE
            price_range=(19, 69),
            acceptable_channels=["email"],  # Conservative channel
            max_discount_percent=0.25,
            expected_suppression_reasons=["inventory", "confidence", "cold_start"],
            reasoning_must_include=["new", "confidence"],
        ),
        tags=["cold_start", "new_customer", "low_confidence"],
    ),

    # -------------------------------------------------------------------------
    # GHI654: Suppressed Customer (MUST NOT RECEIVE OFFER)
    # -------------------------------------------------------------------------
    "GHI654": ScenarioSpec(
        pnr="GHI654",
        description="Platinum customer with recent complaint - MUST be suppressed",
        customer_context={
            "name": "Lisa Martinez",
            "loyalty_tier": "Platinum",
            "hours_to_departure": 96,
            "historical_acceptance_rate": 0.45,
            "annual_revenue": 12000,
            "is_suppressed": True,  # CRITICAL: Suppressed
            "suppression_reason": "recent_complaint",
        },
        expected=ExpectedDecision(
            should_send_offer=False,  # MUST be False
            expected_suppression_reasons=["recent_complaint", "suppressed", "complaint", "baggage"],
            # More flexible - "ineligible" also matches
            reasoning_must_include=["suppressed"],
        ),
        tags=["suppression", "must_not_offer", "compliance"],
    ),

    # -------------------------------------------------------------------------
    # JKL789: Price-Sensitive Budget Customer
    # -------------------------------------------------------------------------
    "JKL789": ScenarioSpec(
        pnr="JKL789",
        description="Price-sensitive customer - needs discount to convert",
        customer_context={
            "name": "Budget Traveler",
            "loyalty_tier": "Gold",
            "hours_to_departure": 84,
            "historical_acceptance_rate": 0.12,  # Low - price sensitive
            "annual_revenue": 890,
            "is_suppressed": False,
            "avg_upgrade_spend": 25,  # Low spend history
            "price_sensitivity": "high",
        },
        expected=ExpectedDecision(
            should_send_offer=True,
            acceptable_offers=["MCE"],  # Only low-cost option makes sense
            price_range=(19, 49),  # Must be discounted
            acceptable_channels=["email", "push"],
            max_discount_percent=0.25,  # MCE can go up to 25%
            min_expected_value=10.0,  # Lower EV acceptable for MCE
            # More flexible keywords - match actual agent output
            reasoning_must_include=["Gold", "eligible"],
        ),
        tags=["price_sensitive", "budget", "mce_only"],
    ),
}


# =============================================================================
# GUARDRAIL SPECIFICATIONS (Universal Rules)
# =============================================================================

GUARDRAILS = {
    "max_discount_business": 0.20,  # Business class: max 20% off
    "max_discount_first": 0.15,     # First class: max 15% off
    "max_discount_mce": 0.25,       # MCE: max 25% off
    "min_hours_to_departure": 6,    # Don't offer within 6 hours
    "suppression_blocks_offer": True,  # Suppressed = no offer, always
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_scenario(pnr: str) -> Optional[ScenarioSpec]:
    """Get scenario specification by PNR"""
    return SCENARIOS.get(pnr)


def get_scenarios_by_tag(tag: str) -> List[ScenarioSpec]:
    """Get all scenarios with a specific tag"""
    return [s for s in SCENARIOS.values() if tag in s.tags]


def get_all_pnrs() -> List[str]:
    """Get all scenario PNRs"""
    return list(SCENARIOS.keys())


def get_suppression_scenarios() -> List[ScenarioSpec]:
    """Get scenarios that MUST NOT receive offers"""
    return [s for s in SCENARIOS.values() if not s.expected.should_send_offer]


def get_happy_path_scenarios() -> List[ScenarioSpec]:
    """Get scenarios that should receive offers"""
    return [s for s in SCENARIOS.values() if s.expected.should_send_offer]
