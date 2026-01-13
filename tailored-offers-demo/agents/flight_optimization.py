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
        reasoning_parts.append(f"=== {self.name} ===")

        if not flight:
            return {
                "flight_priority": "unknown",
                "recommended_cabins": [],
                "inventory_status": {},
                "flight_reasoning": "Flight data not found",
                "reasoning_trace": [f"{self.name}: Flight data not found - cannot evaluate"]
            }

        flight_id = flight.get("flight_id", "Unknown")
        origin = flight.get("origin", "")
        destination = flight.get("destination", "")
        departure_date = flight.get("departure_date", "")
        cabins = flight.get("cabins", {})

        reasoning_parts.append(f"Analyzing flight: {flight_id} ({origin} → {destination})")
        reasoning_parts.append(f"Departure: {departure_date}")

        # Analyze each cabin
        inventory_status = {}
        recommended_cabins = []
        cabin_priorities = []

        current_cabin = reservation.get("current_cabin", "main_cabin")
        reasoning_parts.append(f"Customer's current cabin: {current_cabin}")
        reasoning_parts.append("\nCabin Analysis:")

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

            # Determine priority
            if available < self.MIN_SEATS_FOR_OFFER:
                status["priority"] = "sold_out"
                reasoning_parts.append(
                    f"  - {cabin_name}: {lf:.0%} LF, {available} seats - SOLD OUT (skip)"
                )
            elif lf < self.LF_URGENT:
                status["priority"] = "high"
                recommended_cabins.append(cabin_name)
                cabin_priorities.append((cabin_name, "high", available))
                reasoning_parts.append(
                    f"  - {cabin_name}: {lf:.0%} LF, {available} seats - HIGH PRIORITY (needs filling)"
                )
            elif lf < self.LF_NEEDS_TREATMENT or needs_treatment:
                status["priority"] = "medium"
                recommended_cabins.append(cabin_name)
                cabin_priorities.append((cabin_name, "medium", available))
                reasoning_parts.append(
                    f"  - {cabin_name}: {lf:.0%} LF, {available} seats - MEDIUM PRIORITY"
                )
            else:
                status["priority"] = "low"
                reasoning_parts.append(
                    f"  - {cabin_name}: {lf:.0%} LF, {available} seats - LOW PRIORITY (selling well)"
                )

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

        reasoning_parts.append(f"\nOverall flight priority: {flight_priority.upper()}")
        if recommended_cabins:
            reasoning_parts.append(f"Recommended cabins to offer: {', '.join(recommended_cabins)}")
        else:
            reasoning_parts.append("No cabins recommended for upgrade offers")

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
