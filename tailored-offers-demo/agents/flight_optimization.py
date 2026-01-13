"""
Agent 2: Flight Optimization Agent

Purpose: Evaluates flight-level capacity and revenue optimization
Data Sources: Load factors, cabin availability, pricing, departure timing
Decisions: Which flights need proactive treatment, cabin prioritization
"""
from typing import Dict, Any, List
from .state import AgentState


class FlightOptimizationAgent:
    """
    Analyzes flight inventory to determine which cabins need proactive treatment.

    This agent answers: "Which upgrade products should we push for this flight?"
    """

    # Thresholds for treatment decisions
    LF_NEEDS_TREATMENT = 0.85  # Load factor below this needs proactive offers
    LF_URGENT = 0.70  # Below this is high priority
    MIN_SEATS_FOR_OFFER = 2  # Need at least this many seats to offer

    def __init__(self):
        self.name = "Flight Optimization Agent"

    def analyze(self, state: AgentState) -> Dict[str, Any]:
        """
        Analyze flight inventory and determine treatment priorities.

        Returns updated state with flight optimization outputs.
        """
        flight = state.get("flight_data", {})
        reservation = state.get("reservation_data", {})

        reasoning_parts = []

        if not flight:
            return {
                "flight_priority": "unknown",
                "recommended_cabins": [],
                "inventory_status": {},
                "flight_reasoning": "❌ Cannot evaluate - flight data not found in DCSID",
                "reasoning_trace": [f"{self.name}: Flight data not found - cannot evaluate"]
            }

        flight_id = flight.get("flight_id", "Unknown")
        origin = flight.get("origin", "")
        destination = flight.get("destination", "")
        departure_date = flight.get("departure_date", "")
        cabins = flight.get("cabins", {})
        pricing = flight.get("pricing", {})
        current_cabin = reservation.get("current_cabin", "main_cabin")

        # ========== DATA USED SECTION ==========
        reasoning_parts.append("📊 DATA USED (from MCP Tools):")
        reasoning_parts.append("")
        reasoning_parts.append("┌─ get_flight_inventory() → DCSID (Departure Control)")
        reasoning_parts.append(f"│  • Flight: {flight_id}")
        reasoning_parts.append(f"│  • Route: {origin} → {destination}")
        reasoning_parts.append(f"│  • Date: {departure_date}")
        reasoning_parts.append(f"│  • Customer's Current Cabin: {current_cabin.replace('_', ' ').title()}")
        reasoning_parts.append("│")
        reasoning_parts.append("│  Cabin Inventory:")

        # Show all cabin data
        for cabin_name, cabin_data in cabins.items():
            total = cabin_data.get("total_seats", 0)
            available = cabin_data.get("available_seats", 0)
            lf = cabin_data.get("load_factor", 1.0)
            sold = total - available
            reasoning_parts.append(f"│  • {cabin_name.replace('_', ' ').title()}: {sold}/{total} sold ({lf:.0%} full), {available} available")

        reasoning_parts.append("│")
        reasoning_parts.append("├─ get_pricing() → Revenue Management Engine")
        reasoning_parts.append(f"│  • Business Upgrade Base: ${pricing.get('business_upgrade_base', 199)}")
        reasoning_parts.append(f"│  • Premium Economy Base: ${pricing.get('premium_economy_upgrade_base', 129)}")
        reasoning_parts.append(f"│  • MCE Base: ${pricing.get('mce_upgrade_base', 39)}")

        # ========== ANALYSIS SECTION ==========
        reasoning_parts.append("")
        reasoning_parts.append("─" * 50)
        reasoning_parts.append("")
        reasoning_parts.append("🔍 ANALYSIS:")
        reasoning_parts.append("")
        reasoning_parts.append("   Evaluating each cabin for upgrade potential:")
        reasoning_parts.append(f"   (Thresholds: <{self.LF_URGENT:.0%} = HIGH priority, <{self.LF_NEEDS_TREATMENT:.0%} = MEDIUM)")
        reasoning_parts.append("")

        # Analyze each cabin
        inventory_status = {}
        recommended_cabins = []
        cabin_priorities = []

        for cabin_name, cabin_data in cabins.items():
            # Skip if this is the customer's current cabin or lower
            if cabin_name == current_cabin:
                continue
            if cabin_name == "main_cabin":
                continue

            total = cabin_data.get("total_seats", 0)
            if total == 0:
                continue

            available = cabin_data.get("available_seats", 0)
            lf = cabin_data.get("load_factor", 1.0)
            needs_treatment = cabin_data.get("needs_treatment", False)

            status = {
                "available_seats": available,
                "load_factor": lf,
                "needs_treatment": needs_treatment,
                "priority": "none"
            }

            cabin_display = cabin_name.replace('_', ' ').title()

            # Determine priority with clear explanation
            if available < self.MIN_SEATS_FOR_OFFER:
                status["priority"] = "sold_out"
                reasoning_parts.append(f"   ❌ {cabin_display}: SKIP")
                reasoning_parts.append(f"      → Only {available} seats left (need ≥{self.MIN_SEATS_FOR_OFFER} for offers)")
                reasoning_parts.append(f"      → High load factor ({lf:.0%}) means cabin is selling well organically")
            elif lf < self.LF_URGENT:
                status["priority"] = "high"
                recommended_cabins.append(cabin_name)
                cabin_priorities.append((cabin_name, "high", available))
                reasoning_parts.append(f"   🔴 {cabin_display}: HIGH PRIORITY")
                reasoning_parts.append(f"      → Only {lf:.0%} full with {available} seats to sell")
                reasoning_parts.append(f"      → Revenue at risk if cabin doesn't fill before departure")
            elif lf < self.LF_NEEDS_TREATMENT or needs_treatment:
                status["priority"] = "medium"
                recommended_cabins.append(cabin_name)
                cabin_priorities.append((cabin_name, "medium", available))
                reasoning_parts.append(f"   🟡 {cabin_display}: MEDIUM PRIORITY")
                reasoning_parts.append(f"      → {lf:.0%} full, {available} seats available")
                reasoning_parts.append(f"      → Proactive offers can help optimize revenue")
            else:
                status["priority"] = "low"
                reasoning_parts.append(f"   🟢 {cabin_display}: LOW PRIORITY (skip)")
                reasoning_parts.append(f"      → {lf:.0%} full - selling well, no urgent need")

            reasoning_parts.append("")
            inventory_status[cabin_name] = status

        # Determine overall flight priority
        if any(p[1] == "high" for p in cabin_priorities):
            flight_priority = "high"
        elif any(p[1] == "medium" for p in cabin_priorities):
            flight_priority = "medium"
        else:
            flight_priority = "low"

        # Sort recommended cabins by priority and revenue potential
        cabin_order = {"business": 1, "premium_economy": 2, "main_cabin_extra": 3}
        recommended_cabins.sort(key=lambda x: cabin_order.get(x, 99))

        # ========== DECISION SECTION ==========
        reasoning_parts.append("─" * 50)
        reasoning_parts.append("")

        if recommended_cabins:
            reasoning_parts.append(f"✅ DECISION: OFFER UPGRADES FOR THESE CABINS")
            reasoning_parts.append("")
            reasoning_parts.append("📍 IN SIMPLE TERMS:")
            reasoning_parts.append("   This flight has empty premium seats that probably won't sell.")
            reasoning_parts.append("   Instead of flying with empty seats (= $0 revenue), we can")
            reasoning_parts.append("   offer upgrades to economy passengers and make extra money!")
            reasoning_parts.append("")
            reasoning_parts.append("📍 WHAT WE FOUND:")
            for cabin in recommended_cabins:
                status = inventory_status[cabin]
                cabin_display = cabin.replace('_', ' ').title()
                upgrade_price = {"business": 199, "premium_economy": 129, "main_cabin_extra": 39}.get(cabin, 50)
                potential = status['available_seats'] * upgrade_price
                if status["priority"] == "high":
                    reasoning_parts.append(f"   • {cabin_display}: {status['available_seats']} empty seats (only {status['load_factor']:.0%} full!)")
                    reasoning_parts.append(f"     If we sell upgrades: Could make ${potential:,} extra")
                    reasoning_parts.append(f"     If we do nothing: These seats fly empty = $0")
                else:
                    reasoning_parts.append(f"   • {cabin_display}: {status['available_seats']} seats we could fill")
                    reasoning_parts.append(f"     Potential extra revenue: ${potential:,}")
            reasoning_parts.append("")
            reasoning_parts.append("💡 WHY THIS AGENT MATTERS:")
            reasoning_parts.append("   An ML model just predicts: \"Will this customer buy?\"")
            reasoning_parts.append("   It doesn't know if we SHOULD make an offer.")
            reasoning_parts.append("")
            reasoning_parts.append("   This agent checked the ACTUAL FLIGHT INVENTORY and found:")
            reasoning_parts.append("   • Which cabins have unsold seats")
            reasoning_parts.append("   • Which ones need help selling")
            reasoning_parts.append("   • Where we can make the most money")
            reasoning_parts.append("")
            reasoning_parts.append("   Without this, we might offer upgrades to a sold-out cabin! 🤦")
        else:
            reasoning_parts.append(f"❌ DECISION: DON'T OFFER UPGRADES")
            reasoning_parts.append("")
            reasoning_parts.append("📍 IN SIMPLE TERMS:")
            reasoning_parts.append("   All premium cabins are selling great at full price!")
            reasoning_parts.append("   If we offer discounts now, we'd lose money.")
            reasoning_parts.append("")
            reasoning_parts.append("💡 WHY THIS AGENT MATTERS:")
            reasoning_parts.append("   An ML model might say: \"This customer will probably buy!\"")
            reasoning_parts.append("   But this agent says: \"Wait - we don't NEED to sell upgrades.\"")
            reasoning_parts.append("")
            reasoning_parts.append("   The agent PROTECTED our revenue by checking inventory first.")

        full_reasoning = "\n".join(reasoning_parts)

        # Create trace entry
        cabin_summary = ", ".join([f"{c}({s['priority']})" for c, s in inventory_status.items()])
        trace_entry = (
            f"{self.name}: Flight {flight_id} {origin}→{destination} | "
            f"Priority: {flight_priority.upper()} | "
            f"Cabins: {cabin_summary}"
        )

        return {
            "flight_priority": flight_priority,
            "recommended_cabins": recommended_cabins,
            "inventory_status": inventory_status,
            "flight_reasoning": full_reasoning,
            "reasoning_trace": [trace_entry]
        }
