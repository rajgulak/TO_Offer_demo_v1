"""
Agent 4: Personalization Agent (LLM-Powered GenAI)

Purpose: Generates tailored messaging based on customer context
Data Sources: Customer attributes, brand guidelines, past interactions
Decisions: Message tone, content, personalization level

This agent demonstrates GENERATIVE AI:
- Uses LLM to create truly personalized messages
- Adapts tone based on customer profile
- Goes beyond template fill-in-the-blank

Architecture:
- LangGraph: Workflow orchestration
- LLM: Creative generation within this agent
- Can fall back to templates if LLM unavailable
"""
from typing import Dict, Any, List
import os
import sys

from .state import AgentState
from .llm_service import get_llm, is_llm_available

# Import prompt service for dynamic prompt loading
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.prompt_service import get_personalization_prompt


# System prompt for personalized message generation
PERSONALIZATION_SYSTEM_PROMPT = """You are a Personalization Agent for American Airlines' Tailored Offers system.

Your job is to create personalized upgrade offer messages that resonate with each customer.

Brand Guidelines:
- American Airlines tone: Professional, warm, trustworthy
- For business travelers: Emphasize productivity, efficiency, status
- For leisure travelers: Emphasize comfort, experience, value
- Always be respectful and never pushy

You must generate:
1. A compelling subject line (max 60 chars)
2. A personalized message body

Output in this exact JSON format:
```json
{
  "subject": "Your subject line here",
  "body": "Your message body here with proper line breaks using \\n",
  "tone_used": "professional" or "friendly" or "balanced",
  "personalization_elements": ["element1", "element2"],
  "key_benefit_highlighted": "The main benefit you emphasized"
}
```

Make the customer feel valued, not targeted. Write like a helpful travel advisor, not a marketing bot."""


class PersonalizationAgent:
    """
    Generates personalized offer messaging using LLM.

    This agent demonstrates HOW GENAI DIFFERS FROM TEMPLATES:
    - Template: "Dear {name}, upgrade to {cabin} for ${price}!"
    - GenAI: Creates contextually relevant, emotionally resonant messages
             that adapt to the customer's unique profile

    Architecture shows:
    - LangGraph: orchestrates the workflow (agent sequence)
    - LLM: provides creative generation WITHIN this agent
    - Temporal: could provide durable execution
    """

    # Offer-specific messaging elements (used for both LLM context and template fallback)
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

    def __init__(self, use_llm: bool = True):
        self.name = "Personalization Agent"
        self.use_llm = use_llm
        self._llm = None

    @property
    def llm(self):
        if self._llm is None:
            self._llm = get_llm(temperature=0.7)  # Higher temp for creative generation
        return self._llm

    def analyze(self, state: AgentState) -> Dict[str, Any]:
        """
        Generate personalized messaging using LLM (or template fallback).

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

        # Gather context
        context = self._build_context(state)
        reasoning_parts.append(f"Personalizing for: {context['customer_name']}")
        reasoning_parts.append(f"Travel pattern: {context['travel_pattern']}")
        reasoning_parts.append(f"Offer: {context['offer_name']} @ ${context['offer_price']:.0f}")

        # Use LLM if available, otherwise fall back to templates
        if self.use_llm and is_llm_available():
            result = self._llm_generation(context, reasoning_parts)
            result["generation_mode"] = "LLM"
        else:
            result = self._template_generation(context, reasoning_parts)
            result["generation_mode"] = "TEMPLATE"

        return result

    def _build_context(self, state: AgentState) -> Dict[str, Any]:
        """Build context dictionary for personalization."""
        customer = state.get("customer_data", {})
        flight = state.get("flight_data", {})
        reservation = state.get("reservation_data", {})
        selected_offer = state.get("selected_offer", "")
        offer_price = state.get("offer_price", 0)
        fallback = state.get("fallback_offer")

        # Map offer type to display name
        offer_names = {
            "IU_BUSINESS": "Business Class",
            "IU_PREMIUM_ECONOMY": "Premium Economy",
            "MCE": "Main Cabin Extra"
        }

        # Get urgency level
        hours_to_departure = reservation.get("hours_to_departure", 72)
        if hours_to_departure <= 24:
            urgency = "high"
        elif hours_to_departure <= 48:
            urgency = "medium"
        else:
            urgency = "low"

        return {
            "customer_name": customer.get("first_name", "Valued Customer"),
            "full_name": f"{customer.get('first_name', '')} {customer.get('last_name', '')}",
            "loyalty_tier": customer.get("loyalty_tier", "General"),
            "travel_pattern": "business" if customer.get("business_trip_likelihood", 0) > 0.5 else "leisure",
            "annual_revenue": customer.get("flight_revenue_amt_history", 0),
            "historical_acceptance_rate": customer.get("historical_upgrades", {}).get("acceptance_rate", 0),
            "origin": flight.get("schd_leg_dep_airprt_iata_cd", ""),
            "destination": flight.get("schd_leg_arvl_airprt_iata_cd", ""),
            "flight_id": f"AA{flight.get('operat_flight_nbr', '')}",
            "departure_date": flight.get("leg_dep_dt", ""),
            "hours_to_departure": hours_to_departure,
            "urgency": urgency,
            "selected_offer": selected_offer,
            "offer_name": offer_names.get(selected_offer, selected_offer),
            "offer_price": offer_price,
            "offer_benefits": self.OFFER_BENEFITS.get(selected_offer, []),
            "fallback_offer": fallback
        }

    def _llm_generation(self, context: Dict[str, Any], reasoning_parts: List[str]) -> Dict[str, Any]:
        """Use LLM for creative message generation."""
        reasoning_parts.append("\n[LLM GENERATION MODE]")

        # Build prompt
        user_prompt = f"""Create a personalized upgrade offer message for this customer:

## Customer Profile
- Name: {context['customer_name']}
- Loyalty Tier: {context['loyalty_tier']}
- Travel Pattern: {context['travel_pattern']}
- Annual Revenue: ${context['annual_revenue']:,}
- Historical Upgrade Acceptance: {context['historical_acceptance_rate']:.0%}

## Trip Details
- Route: {context['origin']} → {context['destination']}
- Flight: {context['flight_id']}
- Departure: {context['departure_date']}
- Time to Departure: {context['hours_to_departure']} hours
- Urgency Level: {context['urgency']}

## Offer Details
- Upgrade To: {context['offer_name']}
- Price: ${context['offer_price']:.0f}
- Key Benefits:
{chr(10).join(f'  - {b}' for b in context['offer_benefits'][:4])}
"""

        if context['fallback_offer']:
            user_prompt += f"""
## Alternative Option
- {context['fallback_offer']['display_name']} also available at ${context['fallback_offer']['price']:.0f}
"""

        user_prompt += """
## Your Task
Create a message that:
1. Feels personal, not mass-marketed
2. Highlights benefits relevant to their travel pattern
3. Includes appropriate urgency without being pushy
4. Makes them feel valued as an American Airlines customer

Output the JSON format specified in your instructions.
"""

        try:
            from langchain_core.messages import SystemMessage, HumanMessage

            # Get the active personalization prompt (custom if set, otherwise default)
            active_prompt = get_personalization_prompt()

            response = self.llm.invoke([
                SystemMessage(content=active_prompt),
                HumanMessage(content=user_prompt)
            ])

            llm_output = response.content
            reasoning_parts.append(f"\n{llm_output}")

            # Parse the response
            message = self._parse_llm_message(llm_output, context)

            trace_entry = (
                f"{self.name} [LLM]: Generated {message['tone_used']} message | "
                f"Personalization: {len(message['personalization_elements'])} elements | "
                f"Key benefit: {message['key_benefit_highlighted'][:30]}..."
            )

            return {
                "message_subject": message["subject"],
                "message_body": message["body"],
                "message_tone": message["tone_used"],
                "personalization_elements": message["personalization_elements"],
                "key_benefit": message["key_benefit_highlighted"],
                "personalization_reasoning": "\n".join(reasoning_parts),
                "reasoning_trace": [trace_entry]
            }

        except Exception as e:
            reasoning_parts.append(f"\n[LLM Error: {str(e)} - falling back to templates]")
            return self._template_generation(context, reasoning_parts)

    def _parse_llm_message(self, llm_output: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Parse the LLM's JSON message from its response."""
        import json
        import re

        # Try to find JSON in the response
        json_match = re.search(r'```json\s*(.*?)\s*```', llm_output, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find raw JSON
        try:
            start = llm_output.find('{')
            end = llm_output.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(llm_output[start:end])
        except json.JSONDecodeError:
            pass

        # Default fallback
        return {
            "subject": f"{context['customer_name']}, upgrade to {context['offer_name']} for your trip!",
            "body": f"Hi {context['customer_name']},\n\nUpgrade to {context['offer_name']} on your upcoming flight to {context['destination']} for just ${context['offer_price']:.0f}.\n\nThank you for choosing American Airlines.",
            "tone_used": "balanced",
            "personalization_elements": ["name", "destination", "offer"],
            "key_benefit_highlighted": "Upgrade experience"
        }

    def _template_generation(self, context: Dict[str, Any], reasoning_parts: List[str]) -> Dict[str, Any]:
        """
        Fallback template-based generation when LLM unavailable.

        This shows the CONTRAST with LLM generation - rigid templates.
        """
        # ========== DATA USED SECTION ==========
        reasoning_parts.append("📊 DATA USED (from MCP Tools):")
        reasoning_parts.append("")
        reasoning_parts.append("┌─ get_customer_profile() → AADV Database")
        reasoning_parts.append(f"│  • Customer Name: {context['customer_name']}")
        reasoning_parts.append(f"│  • Loyalty Tier: {context['loyalty_tier']}")
        reasoning_parts.append(f"│  • Travel Pattern: {context['travel_pattern']}")
        reasoning_parts.append(f"│  • Historical Acceptance: {context['historical_acceptance_rate']:.0%}")
        reasoning_parts.append("│")
        reasoning_parts.append("├─ Trip Context (from Reservation)")
        reasoning_parts.append(f"│  • Route: {context['origin']} → {context['destination']}")
        reasoning_parts.append(f"│  • Flight: {context['flight_id']}")
        reasoning_parts.append(f"│  • Departure: {context['departure_date']}")
        reasoning_parts.append(f"│  • Time to Departure: {context['hours_to_departure']} hours")
        reasoning_parts.append("│")
        reasoning_parts.append("└─ Offer Details (from Orchestration Agent)")
        reasoning_parts.append(f"   • Offer: {context['offer_name']}")
        reasoning_parts.append(f"   • Price: ${context['offer_price']:.0f}")

        # ========== ANALYSIS SECTION ==========
        reasoning_parts.append("")
        reasoning_parts.append("─" * 50)
        reasoning_parts.append("")
        reasoning_parts.append("🔍 ANALYSIS:")
        reasoning_parts.append("")

        # Determine tone from travel pattern
        if context['travel_pattern'] == 'business':
            tone = "professional"
            reasoning_parts.append("   1. Tone Selection: PROFESSIONAL")
            reasoning_parts.append(f"      → Travel pattern is '{context['travel_pattern']}'")
            reasoning_parts.append("      → Business travelers prefer efficient, status-aware messaging")
        elif context['travel_pattern'] == 'leisure':
            tone = "friendly"
            reasoning_parts.append("   1. Tone Selection: FRIENDLY")
            reasoning_parts.append(f"      → Travel pattern is '{context['travel_pattern']}'")
            reasoning_parts.append("      → Leisure travelers respond to experience-focused messaging")
        else:
            tone = "balanced"
            reasoning_parts.append("   1. Tone Selection: BALANCED")
            reasoning_parts.append(f"      → Travel pattern is '{context['travel_pattern']}'")
            reasoning_parts.append("      → Mixed travelers get neutral, benefit-focused messaging")

        reasoning_parts.append("")
        if context['urgency'] == 'high':
            reasoning_parts.append("   2. Urgency Level: HIGH")
            reasoning_parts.append(f"      → Only {context['hours_to_departure']} hours to departure")
            reasoning_parts.append("      → Message emphasizes limited-time opportunity")
        elif context['urgency'] == 'medium':
            reasoning_parts.append("   2. Urgency Level: MEDIUM")
            reasoning_parts.append(f"      → {context['hours_to_departure']} hours to departure")
            reasoning_parts.append("      → Include soft urgency cues")
        else:
            reasoning_parts.append("   2. Urgency Level: LOW")
            reasoning_parts.append(f"      → {context['hours_to_departure']} hours to departure")
            reasoning_parts.append("      → Focus on value proposition, no pressure")

        reasoning_parts.append("")
        reasoning_parts.append("   3. Personalization Elements:")
        reasoning_parts.append(f"      • Name: {context['customer_name']}")
        reasoning_parts.append(f"      • Destination: {context['destination']}")
        reasoning_parts.append(f"      • Tone: {tone}")
        reasoning_parts.append(f"      • Benefits: Matched to {context['offer_name']}")

        # Generate subject based on urgency
        if context['urgency'] == 'high':
            if tone == "professional":
                subject = f"{context['customer_name']}, final opportunity to upgrade to {context['offer_name']}"
            else:
                subject = f"{context['customer_name']}, last chance to upgrade your {context['destination']} trip!"
        elif context['urgency'] == 'medium':
            if tone == "professional":
                subject = f"{context['customer_name']}, {context['offer_name']} upgrade available"
            else:
                subject = f"{context['customer_name']}, treat yourself to {context['offer_name']}!"
        else:
            if tone == "professional":
                subject = f"{context['customer_name']}, upgrade available for your upcoming travel"
            else:
                subject = f"{context['customer_name']}, make your {context['destination']} trip even better!"

        # Generate body
        if tone == "professional":
            opening = f"Dear {context['customer_name']},\n\nWe have a {context['offer_name']} upgrade available for your upcoming flight."
            cta = "\n\nTo secure your upgrade, click below or visit aa.com."
            closing = "\n\nThank you for choosing American Airlines."
        else:
            opening = f"Hi {context['customer_name']}!\n\nYour {context['destination']} trip just got an upgrade opportunity!"
            cta = "\n\nReady to upgrade? Tap below to claim your seat!"
            closing = "\n\nSee you on board!"

        details = f"\n\nUpgrade to {context['offer_name']} on {context['flight_id']} ({context['origin']} → {context['destination']}) for just ${context['offer_price']:.0f}."

        benefits_text = "\n\nYour upgrade includes:"
        for benefit in context['offer_benefits'][:3]:
            benefits_text += f"\n  - {benefit}"

        fallback_text = ""
        if context['fallback_offer']:
            fallback_text = f"\n\nNot quite right? {context['fallback_offer']['display_name']} is also available from ${context['fallback_offer']['price']:.0f}."

        body = opening + details + benefits_text + cta + fallback_text + closing

        personalization_elements = [
            f"name:{context['customer_name']}",
            f"route:{context['origin']}-{context['destination']}",
            f"tone:{tone}",
            f"urgency:{context['urgency']}"
        ]

        # ========== DECISION SECTION ==========
        reasoning_parts.append("")
        reasoning_parts.append("─" * 50)
        reasoning_parts.append("")
        reasoning_parts.append("✅ DECISION: PERSONALIZED MESSAGE CREATED")
        reasoning_parts.append("")
        reasoning_parts.append("📍 IN SIMPLE TERMS:")
        reasoning_parts.append(f"   We wrote a message specifically for {context['customer_name']}:")
        reasoning_parts.append(f"   • Used their name (not \"Dear Customer\")")
        reasoning_parts.append(f"   • Matched the tone to their travel style ({context['travel_pattern']})")
        if context['travel_pattern'] == 'business':
            reasoning_parts.append("     → Business travelers want efficiency, not fluff")
        elif context['travel_pattern'] == 'leisure':
            reasoning_parts.append("     → Leisure travelers respond to excitement and experience")
        reasoning_parts.append(f"   • Mentioned their actual destination ({context['destination']})")
        if context['urgency'] == 'high':
            reasoning_parts.append("   • Added urgency because their flight is SOON")
        reasoning_parts.append("")
        reasoning_parts.append(f"   Subject line: \"{subject[:45]}...\"")
        reasoning_parts.append("")
        reasoning_parts.append("💡 WHY THIS AGENT MATTERS:")
        reasoning_parts.append("   A template would just say:")
        reasoning_parts.append("   \"Dear {NAME}, upgrade to {CABIN} for ${PRICE}\"")
        reasoning_parts.append("")
        reasoning_parts.append("   This agent created a message that FEELS personal:")
        reasoning_parts.append(f"   • Knows {context['customer_name']} is a {context['travel_pattern']} traveler")
        reasoning_parts.append(f"   • Knows they're going to {context['destination']}")
        reasoning_parts.append(f"   • Speaks to them in the right tone")
        reasoning_parts.append("")
        reasoning_parts.append("   Personal messages get 2-3x higher response rates! 📈")

        trace_entry = (
            f"{self.name} [TEMPLATE]: Generated {tone} message | "
            f"Elements: {len(personalization_elements)}"
        )

        return {
            "message_subject": subject,
            "message_body": body,
            "message_tone": tone,
            "personalization_elements": personalization_elements,
            "key_benefit": context['offer_benefits'][0] if context['offer_benefits'] else "Upgrade experience",
            "personalization_reasoning": "\n".join(reasoning_parts),
            "reasoning_trace": [trace_entry]
        }
