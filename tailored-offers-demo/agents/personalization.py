"""
Agent 4: Personalization Agent (GenAI)

Purpose: Generates tailored messaging based on customer context
Data Sources: Customer attributes, brand guidelines, past interactions
Decisions: Message tone, content, personalization level
"""
from typing import Dict, Any, List
from .state import AgentState


class PersonalizationAgent:
    """
    Generates personalized offer messaging using customer context.

    This agent answers: "What message should we send?"

    Note: In production, this would use an LLM for dynamic generation.
    For the demo, we use template-based generation with clear reasoning.
    """

    # Brand tone guidelines
    TONE_GUIDELINES = {
        "business": {
            "style": "professional",
            "emphasis": ["productivity", "efficiency", "status"],
            "avoid": ["casual language", "excessive emojis"]
        },
        "leisure": {
            "style": "friendly",
            "emphasis": ["comfort", "experience", "value"],
            "avoid": ["overly formal language"]
        },
        "mixed": {
            "style": "balanced",
            "emphasis": ["flexibility", "convenience"],
            "avoid": ["extremes in tone"]
        }
    }

    # Offer-specific messaging elements
    OFFER_BENEFITS = {
        "IU_BUSINESS": [
            "Lie-flat seat for maximum comfort",
            "Priority boarding - skip the lines",
            "Premium dining experience",
            "Extra baggage allowance",
            "Flagship Lounge access (where available)"
        ],
        "IU_PREMIUM_ECONOMY": [
            "Extra legroom and wider seat",
            "Enhanced meal service",
            "Priority boarding",
            "Dedicated cabin experience"
        ],
        "MCE": [
            "Extra legroom for a more comfortable flight",
            "Preferred boarding",
            "Located near the front of Main Cabin"
        ]
    }

    def __init__(self):
        self.name = "Personalization Agent"

    def analyze(self, state: AgentState) -> Dict[str, Any]:
        """
        Generate personalized messaging for the offer.

        Returns updated state with message content.
        """
        reasoning_parts = []
        reasoning_parts.append(f"=== {self.name} ===")

        # Check if we should send offer
        if not state.get("should_send_offer", False):
            return {
                "message_subject": "",
                "message_body": "",
                "message_tone": "",
                "personalization_elements": [],
                "personalization_reasoning": "No offer to personalize",
                "reasoning_trace": [f"{self.name}: Skipped - no offer selected"]
            }

        customer = state.get("customer_data", {})
        flight = state.get("flight_data", {})
        reservation = state.get("reservation_data", {})
        selected_offer = state.get("selected_offer", "")
        offer_price = state.get("offer_price", 0)
        fallback = state.get("fallback_offer")

        # Extract personalization inputs
        first_name = customer.get("first_name", "Valued Customer")
        travel_pattern = customer.get("travel_pattern", "mixed")
        loyalty_tier = customer.get("loyalty_tier", "General")

        origin = flight.get("origin_city", flight.get("origin", ""))
        destination = flight.get("destination_city", flight.get("destination", ""))
        flight_id = flight.get("flight_id", "")
        departure_date = reservation.get("departure_date", "")
        hours_to_departure = reservation.get("hours_to_departure", 72)

        reasoning_parts.append(f"Personalizing for: {first_name}")
        reasoning_parts.append(f"Travel pattern: {travel_pattern}")
        reasoning_parts.append(f"Route: {origin} → {destination}")

        # Determine tone
        tone_config = self.TONE_GUIDELINES.get(travel_pattern, self.TONE_GUIDELINES["mixed"])
        tone = tone_config["style"]
        emphasis = tone_config["emphasis"]

        reasoning_parts.append(f"Selected tone: {tone}")
        reasoning_parts.append(f"Emphasis points: {', '.join(emphasis)}")

        # Get offer display name and benefits
        offer_names = {
            "IU_BUSINESS": "Business Class",
            "IU_PREMIUM_ECONOMY": "Premium Economy",
            "MCE": "Main Cabin Extra"
        }
        offer_name = offer_names.get(selected_offer, selected_offer)
        benefits = self.OFFER_BENEFITS.get(selected_offer, [])

        # Select top 3 benefits based on travel pattern
        selected_benefits = self._select_benefits(benefits, travel_pattern, emphasis)
        reasoning_parts.append(f"Selected benefits: {selected_benefits}")

        # Determine urgency level
        if hours_to_departure <= 24:
            urgency = "high"
            urgency_text = "Last chance! "
        elif hours_to_departure <= 48:
            urgency = "medium"
            urgency_text = "Don't miss out - "
        else:
            urgency = "low"
            urgency_text = ""

        reasoning_parts.append(f"Urgency level: {urgency}")

        # Generate subject line
        subject = self._generate_subject(
            first_name=first_name,
            offer_name=offer_name,
            destination=destination,
            urgency=urgency,
            tone=tone
        )

        # Generate message body
        body = self._generate_body(
            first_name=first_name,
            offer_name=offer_name,
            price=offer_price,
            origin=origin,
            destination=destination,
            flight_id=flight_id,
            departure_date=departure_date,
            benefits=selected_benefits,
            urgency_text=urgency_text,
            tone=tone,
            fallback=fallback
        )

        # Track personalization elements used
        personalization_elements = [
            f"name:{first_name}",
            f"route:{origin}-{destination}",
            f"tone:{tone}",
            f"urgency:{urgency}",
            f"benefits:{len(selected_benefits)}"
        ]

        reasoning_parts.append(f"\nGenerated subject: {subject}")
        reasoning_parts.append(f"Message tone: {tone}")
        reasoning_parts.append(f"Personalization elements: {len(personalization_elements)}")

        full_reasoning = "\n".join(reasoning_parts)

        trace_entry = (
            f"{self.name}: Generated {tone} message for {first_name} | "
            f"Offer: {offer_name} @ ${offer_price:.0f} | "
            f"Urgency: {urgency}"
        )

        return {
            "message_subject": subject,
            "message_body": body,
            "message_tone": tone,
            "personalization_elements": personalization_elements,
            "personalization_reasoning": full_reasoning,
            "reasoning_trace": [trace_entry]
        }

    def _select_benefits(
        self,
        benefits: List[str],
        travel_pattern: str,
        emphasis: List[str]
    ) -> List[str]:
        """Select most relevant benefits based on travel pattern"""
        # For demo, just take top 3
        # In production, would use semantic matching with emphasis keywords
        return benefits[:3]

    def _generate_subject(
        self,
        first_name: str,
        offer_name: str,
        destination: str,
        urgency: str,
        tone: str
    ) -> str:
        """Generate email/push subject line"""
        if urgency == "high":
            if tone == "professional":
                return f"{first_name}, final opportunity to upgrade to {offer_name}"
            else:
                return f"{first_name}, last chance to upgrade your {destination} trip!"
        elif urgency == "medium":
            if tone == "professional":
                return f"{first_name}, {offer_name} upgrade available for your upcoming flight"
            else:
                return f"{first_name}, treat yourself to {offer_name} on your {destination} trip!"
        else:
            if tone == "professional":
                return f"{first_name}, upgrade to {offer_name} for your upcoming travel"
            else:
                return f"{first_name}, make your {destination} trip even better!"

    def _generate_body(
        self,
        first_name: str,
        offer_name: str,
        price: float,
        origin: str,
        destination: str,
        flight_id: str,
        departure_date: str,
        benefits: List[str],
        urgency_text: str,
        tone: str,
        fallback: Dict[str, Any] = None
    ) -> str:
        """Generate message body"""
        # Opening
        if tone == "professional":
            opening = f"Dear {first_name},\n\n{urgency_text}We have a {offer_name} upgrade available for your upcoming flight."
        else:
            opening = f"Hi {first_name}!\n\n{urgency_text}Your {destination} trip just got an upgrade opportunity!"

        # Offer details
        details = f"\n\nUpgrade to {offer_name} on {flight_id} ({origin} → {destination}) for just ${price:.0f}."

        # Benefits
        benefits_text = "\n\nYour upgrade includes:"
        for benefit in benefits:
            benefits_text += f"\n  - {benefit}"

        # Call to action
        if tone == "professional":
            cta = "\n\nTo secure your upgrade, click below or visit aa.com."
        else:
            cta = "\n\nReady to upgrade? Tap below to claim your seat!"

        # Fallback mention (if applicable)
        fallback_text = ""
        if fallback:
            fallback_text = f"\n\nNot quite right? {fallback['display_name']} is also available from ${fallback['price']:.0f}."

        # Closing
        if tone == "professional":
            closing = "\n\nThank you for choosing American Airlines."
        else:
            closing = "\n\nSee you on board!"

        return opening + details + benefits_text + cta + fallback_text + closing
