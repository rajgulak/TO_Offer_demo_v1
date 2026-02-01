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


def generate_customer_reasoning(
    customer: Dict[str, Any],
    eligible: bool,
    suppression_reason: Optional[str],
    segment: str,
    ml_scores: Dict[str, Any] = None
) -> str:
    """
    Generate rich MCP-style customer intelligence reasoning.
    Matches the old CustomerIntelligenceAgent.analyze() output format.
    """
    first_name = customer.get("first_name", "Customer")
    last_name = customer.get("last_name", "")
    loyalty_tier = customer.get("loyalty_tier", "General")
    tenure_days = customer.get("aadv_tenure_days", 0)
    tenure_years = round(tenure_days / 365, 1) if tenure_days else 0
    annual_revenue = customer.get("flight_revenue_amt_history", 0)
    upgrade_acceptance = customer.get("past_upgrade_acceptance_rate", 0)
    avg_upgrade_spend = customer.get("avg_upgrade_spend", 0)
    suppression = customer.get("suppression", {})
    is_suppressed = suppression.get("is_suppressed", False)
    complaint_reason = suppression.get("complaint_reason", "")
    consent = customer.get("marketing_consent", {})
    email_consent = consent.get("email", False)
    push_consent = consent.get("push", False)

    tier_names = {
        "E": "Executive Platinum",
        "C": "Concierge Key",
        "T": "AAdvantage Platinum Pro",
        "P": "AAdvantage Platinum",
        "G": "AAdvantage Gold",
        "General": "General Member"
    }
    tier_display = tier_names.get(loyalty_tier, loyalty_tier)

    lines = []
    divider = "─" * 50

    # Header
    lines.append("📊 DATA USED (from MCP Tools):")
    lines.append(divider)
    lines.append("")

    # Data source: customer profile
    lines.append("┌─ get_customer_profile() → AADV Database")
    lines.append(f"│   Customer: {first_name} {last_name}")
    lines.append(f"│   Loyalty Tier: {tier_display} ({loyalty_tier})")
    lines.append(f"│   Tenure: {tenure_years} years ({tenure_days} days)")
    lines.append(f"│   Annual Revenue: ${annual_revenue:,.0f}")
    lines.append(f"│   Past Upgrade Acceptance: {upgrade_acceptance:.0%}")
    lines.append(f"│   Avg Upgrade Spend: ${avg_upgrade_spend:,.0f}")
    lines.append("│")

    # Data source: suppression status
    lines.append("├─ get_suppression_status() → CRM System")
    lines.append(f"│   Is Suppressed: {is_suppressed}")
    if is_suppressed and complaint_reason:
        lines.append(f"│   Reason: {complaint_reason}")
    lines.append("│")

    # Data source: marketing consent
    lines.append("└─ Marketing Consent (from Profile)")
    lines.append(f"    Email Consent: {email_consent}")
    lines.append(f"    Push Consent: {push_consent}")
    lines.append("")

    # Analysis
    lines.append("🔍 ANALYSIS:")
    lines.append(divider)

    if is_suppressed:
        lines.append("")
        lines.append(f"1. Customer {first_name} {last_name} is a {tier_display} member")
        lines.append(f"2. Revenue history: ${annual_revenue:,.0f} annually")
        lines.append(f"3. ⚠️  Suppression flag ACTIVE — reason: {complaint_reason}")
        lines.append("")
        lines.append("🚨 STOP! FOUND A PROBLEM:")
        lines.append(divider)
        lines.append(f"   Customer has an active complaint: \"{complaint_reason}\"")
        lines.append("   Sending offers now would worsen the relationship.")
        lines.append("")
        lines.append("❌ DECISION: DO NOT SEND ANY OFFERS")
        lines.append("")
        lines.append("📍 IN SIMPLE TERMS:")
        lines.append(f"   {first_name} recently had a bad experience ({complaint_reason}).")
        lines.append("   Even though they're a valuable customer, reaching out with")
        lines.append("   a sales offer right now would feel tone-deaf. We need to")
        lines.append("   let the service recovery process complete first.")
        lines.append("")
        lines.append("💡 WHY THIS AGENT MATTERS:")
        lines.append("   Without this check, the system would have blindly sent")
        lines.append(f"   upgrade offers to an upset customer — damaging trust")
        lines.append("   and potentially losing a high-value relationship.")

    elif not (email_consent or push_consent):
        lines.append("")
        lines.append(f"1. Customer {first_name} {last_name} is a {tier_display} member")
        lines.append(f"2. Revenue history: ${annual_revenue:,.0f} annually")
        lines.append("3. ⚠️  No marketing consent on any channel")
        lines.append("")
        lines.append("❌ DECISION: NOT ELIGIBLE")
        lines.append("")
        lines.append("📍 WHY:")
        lines.append(f"   {first_name} has not opted in to email or push marketing.")
        lines.append("   We cannot legally send offers without consent.")

    else:
        channels = []
        if email_consent:
            channels.append("email")
        if push_consent:
            channels.append("push")
        channel_str = " and ".join(channels)

        lines.append("")
        lines.append(f"1. Customer {first_name} {last_name} is a {tier_display} member")
        lines.append(f"2. Revenue history: ${annual_revenue:,.0f} annually")
        lines.append(f"3. Upgrade acceptance rate: {upgrade_acceptance:.0%}")
        lines.append(f"4. No suppression flags — customer relationship is healthy")
        lines.append(f"5. Marketing consent active on: {channel_str}")
        lines.append(f"6. Customer segment: {segment}")
        lines.append("")
        lines.append("✅ DECISION: ELIGIBLE FOR OFFERS")
        lines.append("")
        lines.append("📍 IN SIMPLE TERMS:")
        lines.append(f"   {first_name} is a {tier_display} member with ${annual_revenue:,.0f}")
        lines.append(f"   in annual revenue. They have a {upgrade_acceptance:.0%} upgrade")
        lines.append(f"   acceptance rate and have opted in to {channel_str}.")
        lines.append("   No complaints or issues — safe to proceed with offers.")
        lines.append("")
        lines.append("💡 WHY THIS AGENT MATTERS:")
        lines.append("   This check ensures we only target customers who are in")
        lines.append("   good standing and have consented to marketing, protecting")
        lines.append("   both the customer experience and regulatory compliance.")

    return "\n".join(lines)


def generate_flight_reasoning(
    flight: Dict[str, Any],
    current_cabin: str,
    recommended_cabins: list,
    inventory_status: Dict[str, Any],
    flight_priority: str = "normal"
) -> str:
    """
    Generate rich MCP-style flight optimization reasoning.
    Matches the old FlightOptimizationAgent.analyze() output format.
    """
    flight_number = flight.get("flight_number", "Unknown")
    origin = flight.get("origin", "")
    destination = flight.get("destination", "")
    departure_date = flight.get("departure_date", "")
    cabins = flight.get("cabins", {})

    cabin_names = {
        "F": "Business/First",
        "W": "Premium Economy",
        "MCE": "Main Cabin Extra",
        "Y": "Main Cabin"
    }

    lines = []
    divider = "─" * 50

    # Header
    lines.append("📊 DATA USED (from MCP Tools):")
    lines.append(divider)
    lines.append("")

    # Data source: flight inventory
    lines.append("┌─ get_flight_inventory() → DCSID")
    lines.append(f"│   Flight: AA{flight_number}")
    lines.append(f"│   Route: {origin} → {destination}")
    lines.append(f"│   Date: {departure_date}")
    lines.append(f"│   Current Cabin: {cabin_names.get(current_cabin, current_cabin)} ({current_cabin})")
    lines.append("│")

    # Show cabin inventory
    for cabin_code, cabin_data in cabins.items():
        total = cabin_data.get("cabin_capacity", 0)
        available = cabin_data.get("cabin_available", 0)
        sold = cabin_data.get("cabin_total_pax", 0)
        lf = cabin_data.get("expected_load_factor", sold / total if total > 0 else 1.0)
        lines.append(f"│   {cabin_names.get(cabin_code, cabin_code)} ({cabin_code}): "
                      f"{sold}/{total} sold, {available} available, LF={lf:.0%}")

    lines.append("│")

    # Data source: pricing
    lines.append("├─ get_pricing() → Revenue Management Engine")
    lines.append("│   (Pricing data used for offer generation)")
    lines.append("│")
    lines.append("└─ Thresholds Applied:")
    lines.append("    Load Factor < 80% = 🔴 HIGH priority (need to fill seats)")
    lines.append("    Load Factor < 95% = 🟡 MEDIUM priority (room to sell)")
    lines.append("    Load Factor ≥ 95% = 🟢 LOW priority (nearly full)")
    lines.append("")

    # Analysis
    lines.append("🔍 ANALYSIS:")
    lines.append(divider)
    lines.append("")

    analysis_num = 1

    for cabin_code, status in inventory_status.items():
        available = status.get("available_seats", 0)
        lf = status.get("load_factor", 1.0)
        priority = status.get("priority", "none")
        cabin_display = cabin_names.get(cabin_code, cabin_code)

        icon = {
            "high": "🔴 HIGH",
            "medium": "🟡 MEDIUM",
            "low": "🟢 LOW",
            "sold_out": "❌ SKIP"
        }.get(priority, "⚪ NONE")

        lines.append(f"{analysis_num}. {cabin_display} ({cabin_code}): {icon}")
        lines.append(f"   Load Factor: {lf:.0%} | Available: {available} seats")

        if priority == "sold_out":
            lines.append("   → Not enough seats to offer (below minimum threshold)")
        elif priority == "high":
            lines.append("   → Under 80% full — strong need to sell these seats")
        elif priority == "medium":
            lines.append("   → Under 95% full — good opportunity to upsell")
        elif priority == "low":
            lines.append("   → Nearly full — low priority for offers")
        else:
            lines.append("   → No action needed")

        lines.append("")
        analysis_num += 1

    # Decision
    if recommended_cabins:
        cabin_list = ", ".join(
            f"{cabin_names.get(c, c)} ({c})" for c in recommended_cabins
        )
        lines.append("✅ DECISION: OFFER UPGRADES")
        lines.append(f"   Recommended cabins: {cabin_list}")
        lines.append("")
        lines.append("📍 IN SIMPLE TERMS:")
        if len(recommended_cabins) == 1:
            c = recommended_cabins[0]
            lines.append(f"   AA{flight_number} {origin}→{destination} has open seats in")
            lines.append(f"   {cabin_names.get(c, c)}. The airline benefits from filling")
            lines.append("   these seats with paid upgrades rather than flying empty.")
        else:
            lines.append(f"   AA{flight_number} {origin}→{destination} has open seats in")
            lines.append(f"   multiple premium cabins ({', '.join(recommended_cabins)}).")
            lines.append("   Offering upgrades helps fill these seats with revenue")
            lines.append("   that would otherwise be lost.")
        lines.append("")
        lines.append("💡 WHY THIS AGENT MATTERS:")
        lines.append("   Without inventory analysis, the system might offer upgrades")
        lines.append("   to cabins that are already full, creating a bad customer")
        lines.append("   experience, or miss opportunities to fill empty premium seats.")
    else:
        lines.append("❌ DECISION: DON'T OFFER UPGRADES")
        lines.append("   No cabins have sufficient inventory for upgrade offers.")
        lines.append("")
        lines.append("📍 IN SIMPLE TERMS:")
        lines.append(f"   AA{flight_number} {origin}→{destination} premium cabins are")
        lines.append("   either sold out or nearly full. There's no inventory to")
        lines.append("   offer upgrades without overselling.")
        lines.append("")
        lines.append("💡 WHY THIS AGENT MATTERS:")
        lines.append("   This check prevents the system from offering upgrades")
        lines.append("   when no seats are actually available, avoiding customer")
        lines.append("   disappointment and operational issues.")

    return "\n".join(lines)
