"""
Pre-checks: Workflow functions for eligibility and inventory validation

These are NOT agents - they are deterministic workflow steps that run
BEFORE the Offer Agent to validate that we should proceed.

Pre-checks:
1. Customer Eligibility - Is customer suppressed? Has consent?
2. Inventory Availability - Are seats available to sell?
"""
from typing import Dict, Any, Tuple, Optional


def check_customer_eligibility(
    customer: Dict[str, Any],
    reservation: Dict[str, Any] = None,
    ml_scores: Dict[str, Any] = None
) -> Tuple[bool, Optional[str], str, Dict[str, Any]]:
    """
    Check if customer is eligible for offers.

    Returns:
        Tuple of (is_eligible, suppression_reason, segment, details)
    """
    if not customer:
        return False, "Customer data not found", "unknown", {}

    first_name = customer.get("first_name", "Customer")
    loyalty_tier = customer.get("loyalty_tier", "General")
    suppression = customer.get("suppression", {})
    consent = customer.get("marketing_consent", {})

    # Check suppression
    if suppression.get("is_suppressed", False):
        reason = suppression.get("complaint_reason", "Unknown")
        return False, f"Customer suppressed: {reason}", _determine_segment(customer), {
            "customer_name": first_name,
            "loyalty_tier": loyalty_tier,
            "suppression_reason": reason
        }

    # Check consent
    has_any_channel = consent.get("push", False) or consent.get("email", False)
    if not has_any_channel:
        return False, "No marketing consent", _determine_segment(customer), {
            "customer_name": first_name,
            "loyalty_tier": loyalty_tier,
            "consent": consent
        }

    # Eligible
    segment = _determine_segment(customer)
    return True, None, segment, {
        "customer_name": first_name,
        "loyalty_tier": loyalty_tier,
        "segment": segment,
        "consent": consent
    }


def check_inventory_availability(
    flight: Dict[str, Any],
    current_cabin: str = "Y"
) -> Tuple[bool, list, Dict[str, Any]]:
    """
    Check if upgrade inventory is available.

    Returns:
        Tuple of (has_inventory, recommended_cabins, inventory_status)
    """
    MIN_SEATS_FOR_OFFER = 2
    LF_URGENT = 0.80
    LF_NEEDS_TREATMENT = 0.95

    if not flight:
        return False, [], {}

    cabins = flight.get("cabins", {})
    cabin_hierarchy = {"Y": 0, "MCE": 1, "W": 2, "F": 3}

    inventory_status = {}
    recommended_cabins = []

    for cabin_code, cabin_data in cabins.items():
        # Skip if this is the customer's current cabin or lower
        if cabin_hierarchy.get(cabin_code, 0) <= cabin_hierarchy.get(current_cabin, 0):
            continue

        total = cabin_data.get("cabin_capacity", 0)
        if total == 0:
            continue

        available = cabin_data.get("cabin_available", 0)
        sold = cabin_data.get("cabin_total_pax", 0)
        lf = cabin_data.get("expected_load_factor", sold / total if total > 0 else 1.0)

        status = {
            "available_seats": available,
            "load_factor": lf,
            "priority": "none"
        }

        if available < MIN_SEATS_FOR_OFFER:
            status["priority"] = "sold_out"
        elif lf < LF_URGENT:
            status["priority"] = "high"
            recommended_cabins.append(cabin_code)
        elif lf < LF_NEEDS_TREATMENT:
            status["priority"] = "medium"
            recommended_cabins.append(cabin_code)
        else:
            status["priority"] = "low"

        inventory_status[cabin_code] = status

    # Sort by revenue potential
    cabin_order = {"F": 1, "W": 2, "MCE": 3}
    recommended_cabins.sort(key=lambda x: cabin_order.get(x, 99))

    has_inventory = len(recommended_cabins) > 0
    return has_inventory, recommended_cabins, inventory_status


def _determine_segment(customer: Dict[str, Any]) -> str:
    """Determine customer segment based on attributes."""
    loyalty_tier = customer.get("loyalty_tier", "General")
    flight_revenue = customer.get("flight_revenue_amt_history", 0)
    business_likelihood = customer.get("business_trip_likelihood", 0)
    tenure_days = customer.get("aadv_tenure_days", 0)

    if loyalty_tier in ["E", "C", "T"]:
        if flight_revenue > 50000:
            return "elite_business"
        return "frequent_business"

    if loyalty_tier in ["P", "G"]:
        if business_likelihood > 0.5:
            return "mid_value_business"
        elif flight_revenue > 10000:
            return "high_value_leisure"
        return "mid_value_leisure"

    if tenure_days < 90:
        return "new_customer"

    return "general"


def generate_precheck_reasoning(
    customer_eligible: bool,
    suppression_reason: Optional[str],
    segment: str,
    has_inventory: bool,
    recommended_cabins: list,
    inventory_status: Dict[str, Any],
    customer_details: Dict[str, Any],
    flight_details: Dict[str, Any]
) -> str:
    """
    Generate human-readable reasoning for pre-checks.
    """
    lines = []
    lines.append("=" * 50)
    lines.append("PRE-FLIGHT CHECKS")
    lines.append("=" * 50)
    lines.append("")

    # Customer check
    customer_name = customer_details.get("customer_name", "Customer")
    loyalty_tier = customer_details.get("loyalty_tier", "Unknown")

    lines.append("1️⃣ CUSTOMER ELIGIBILITY")
    lines.append(f"   Customer: {customer_name} ({loyalty_tier})")

    if customer_eligible:
        lines.append(f"   Segment: {segment}")
        lines.append("   ✅ ELIGIBLE - No suppression, has consent")
    else:
        lines.append(f"   ❌ NOT ELIGIBLE - {suppression_reason}")
        lines.append("")
        lines.append("   ⏹️ STOPPING HERE - Cannot proceed without eligible customer")
        return "\n".join(lines)

    lines.append("")

    # Inventory check
    flight_nbr = flight_details.get("flight_number", "Unknown")
    route = flight_details.get("route", "Unknown")

    lines.append("2️⃣ INVENTORY AVAILABILITY")
    lines.append(f"   Flight: AA{flight_nbr} ({route})")

    cabin_names = {"F": "Business", "W": "Premium Economy", "MCE": "Main Cabin Extra"}

    if inventory_status:
        for cabin, status in inventory_status.items():
            seats = status.get("available_seats", 0)
            priority = status.get("priority", "none")
            icon = {"high": "🔴", "medium": "🟡", "low": "🟢", "sold_out": "❌"}.get(priority, "⚪")
            lines.append(f"   {icon} {cabin_names.get(cabin, cabin)}: {seats} seats ({priority})")

    if has_inventory:
        lines.append(f"   ✅ AVAILABLE - Can offer: {', '.join(recommended_cabins)}")
    else:
        lines.append("   ❌ NO INVENTORY - All cabins sold out or below minimum")
        lines.append("")
        lines.append("   ⏹️ STOPPING HERE - No seats to sell")
        return "\n".join(lines)

    lines.append("")
    lines.append("=" * 50)
    lines.append("✅ PRE-CHECKS PASSED - Proceeding to Offer Agent")
    lines.append("=" * 50)

    return "\n".join(lines)
