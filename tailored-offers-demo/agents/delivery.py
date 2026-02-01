"""
Delivery: Workflow functions for post-decision delivery

These handle what happens AFTER the Offer Agent makes a decision:
1. Message Generation - Create personalized message (uses LLM)
2. Channel Selection - Pick email vs push vs SMS (rules-based)
3. Tracking Setup - Assign A/B test group and tracking ID (rules-based)
"""
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import random
import hashlib

from .llm_service import get_llm, is_llm_available


# System prompt for personalization (used by prompt editing UI)
PERSONALIZATION_SYSTEM_PROMPT = """You create personalized airline upgrade offer messages.
Output JSON only:
{
  "subject": "Email subject (max 60 chars)",
  "body": "Email body with \\n for line breaks",
  "push_notification": "Short push text (max 100 chars)"
}"""


# ============ MESSAGE GENERATION ============

OFFER_BENEFITS = {
    "IU_BUSINESS": [
        "Lie-flat seat for maximum comfort",
        "Priority boarding - skip the lines",
        "Premium dining experience",
        "Extra baggage allowance",
    ],
    "IU_PREMIUM_ECONOMY": [
        "Extra legroom and wider seat",
        "Enhanced meal service",
        "Priority boarding",
    ],
    "MCE": [
        "Extra legroom for a more comfortable flight",
        "Preferred boarding",
    ]
}

OFFER_DISPLAY_NAMES = {
    "IU_BUSINESS": "Business Class",
    "IU_PREMIUM_ECONOMY": "Premium Economy",
    "MCE": "Main Cabin Extra"
}


def generate_message(
    customer: Dict[str, Any],
    flight: Dict[str, Any],
    offer_type: str,
    price: float,
    use_llm: bool = True
) -> Dict[str, Any]:
    """
    Generate personalized offer message.

    Returns dict with subject, body, push_notification, and metadata.
    """
    customer_name = customer.get("first_name", "Valued Customer")
    loyalty_tier = customer.get("loyalty_tier", "Member")
    business_likelihood = customer.get("business_trip_likelihood", 0)

    flight_nbr = flight.get("operat_flight_nbr", "")
    origin = flight.get("schd_leg_dep_airprt_iata_cd", "")
    destination = flight.get("schd_leg_arvl_airprt_iata_cd", "")

    offer_name = OFFER_DISPLAY_NAMES.get(offer_type, offer_type)
    benefits = OFFER_BENEFITS.get(offer_type, ["Enhanced travel experience"])

    # Determine tone based on customer profile
    if business_likelihood > 0.7:
        tone = "professional"
    elif business_likelihood < 0.3:
        tone = "friendly"
    else:
        tone = "balanced"

    # Try LLM generation
    if use_llm and is_llm_available():
        try:
            result = _generate_with_llm(
                customer_name, loyalty_tier, tone,
                offer_name, price, benefits,
                origin, destination, flight_nbr
            )
            if result:
                return result
        except Exception as e:
            print(f"LLM generation failed: {e}")

    # Fallback to template
    return _generate_template_message(
        customer_name, loyalty_tier, tone,
        offer_name, price, benefits,
        origin, destination, flight_nbr
    )


def _generate_with_llm(
    customer_name: str, loyalty_tier: str, tone: str,
    offer_name: str, price: float, benefits: list,
    origin: str, destination: str, flight_nbr: str
) -> Optional[Dict[str, Any]]:
    """Generate message using LLM."""
    from langchain_core.messages import SystemMessage, HumanMessage
    import json

    llm = get_llm(temperature=0.7)

    system_prompt = """You create personalized airline upgrade offer messages.
Output JSON only:
{
  "subject": "Email subject (max 60 chars)",
  "body": "Email body with \\n for line breaks",
  "push_notification": "Short push text (max 100 chars)"
}"""

    user_prompt = f"""Create a {tone} upgrade offer message:
- Customer: {customer_name} ({loyalty_tier})
- Offer: {offer_name} for ${price:.0f}
- Flight: AA{flight_nbr} {origin} → {destination}
- Benefits: {', '.join(benefits[:3])}"""

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ])

    # Parse response
    content = response.content.strip()
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()

    result = json.loads(content)
    result["tone"] = tone
    result["personalization_elements"] = [
        f"name:{customer_name}",
        f"route:{origin}-{destination}",
        f"tone:{tone}"
    ]
    return result


def _generate_template_message(
    customer_name: str, loyalty_tier: str, tone: str,
    offer_name: str, price: float, benefits: list,
    origin: str, destination: str, flight_nbr: str
) -> Dict[str, Any]:
    """Generate message using templates."""
    tier_greeting = {
        "E": "As an Executive Platinum member",
        "C": "As a Concierge Key member",
        "T": "As a Platinum Pro member",
        "P": "As a Platinum member",
        "G": "As a Gold member",
    }.get(loyalty_tier, "As a valued member")

    if tone == "professional":
        subject = f"{customer_name}, upgrade available on AA{flight_nbr}"
        body = f"""Dear {customer_name},

{tier_greeting}, you have an exclusive upgrade opportunity.

Upgrade to {offer_name} on your upcoming flight AA{flight_nbr} ({origin} → {destination}) for ${price:.0f}.

Benefits include:
{chr(10).join('  - ' + b for b in benefits[:3])}

This offer is available for a limited time.

Best regards,
American Airlines"""
    else:
        subject = f"{customer_name}, make your {destination} trip even better!"
        body = f"""Hi {customer_name}!

Your {destination} trip just got an upgrade opportunity!

Upgrade to {offer_name} on AA{flight_nbr} ({origin} → {destination}) for just ${price:.0f}.

Your upgrade includes:
{chr(10).join('  - ' + b for b in benefits[:3])}

Ready to upgrade? Tap below to claim your seat!

See you on board!"""

    push = f"Upgrade to {offer_name} on your {origin} to {destination} flight for ${price:.0f}, {customer_name}!"

    return {
        "subject": subject,
        "body": body,
        "push_notification": push[:100],
        "tone": tone,
        "personalization_elements": [
            f"name:{customer_name}",
            f"route:{origin}-{destination}",
            f"tone:{tone}"
        ]
    }


# ============ CHANNEL SELECTION ============

def select_channel(
    customer: Dict[str, Any],
    hours_to_departure: int = 72
) -> Dict[str, Any]:
    """
    Select optimal delivery channel based on consent and preferences.

    Returns dict with channel, send_time, and reasoning.
    """
    consent = customer.get("marketing_consent", {})
    engagement = customer.get("engagement", {})
    timezone = customer.get("home_timezone", "America/Chicago")

    has_push = consent.get("push", False) and engagement.get("app_installed", False)
    has_email = consent.get("email", False)

    # Score channels
    channels = []

    if has_push:
        push_rate = engagement.get("push_open_rate", 0.45)
        urgency_bonus = 0.2 if hours_to_departure < 24 else 0
        channels.append(("push", push_rate + urgency_bonus, "Push notification"))

    if has_email:
        email_rate = engagement.get("email_open_rate", 0.22)
        channels.append(("email", email_rate, "Email"))

    if not channels:
        return {
            "channel": None,
            "send_time": None,
            "reasoning": "No available channels - customer has no consent"
        }

    # Pick best channel
    channels.sort(key=lambda x: x[1], reverse=True)
    selected, score, display_name = channels[0]

    # Determine send time
    preferred_hours = engagement.get("preferred_engagement_hours", [9, 12, 18])
    now = datetime.now()
    send_hour = preferred_hours[0] if preferred_hours else 9

    # Find next available slot
    if now.hour < send_hour:
        send_time = now.replace(hour=send_hour, minute=0, second=0)
    else:
        send_time = (now + timedelta(days=1)).replace(hour=send_hour, minute=0, second=0)

    return {
        "channel": selected,
        "send_time": f"{send_time.strftime('%Y-%m-%d %H:%M')} {timezone.split('/')[-1]}",
        "backup_channel": channels[1][0] if len(channels) > 1 else None,
        "reasoning": f"Selected {display_name} (score: {score:.2f})"
    }


# ============ TRACKING SETUP ============

def setup_tracking(
    pnr: str,
    offer_type: str,
    experiment_allocation: float = 0.5
) -> Dict[str, Any]:
    """
    Set up A/B test group and tracking ID.

    Returns dict with experiment_group and tracking_id.
    """
    # Deterministic A/B assignment based on PNR hash
    hash_val = int(hashlib.md5(pnr.encode()).hexdigest()[:8], 16)
    in_test = (hash_val % 100) < (experiment_allocation * 100)

    experiment_group = "test_model_v2" if in_test else "control"

    # Generate tracking ID (include random component for uniqueness)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_suffix = hashlib.md5(f"{pnr}{timestamp}{random.random()}".encode()).hexdigest()[:8]
    tracking_id = f"TO_{pnr}_{offer_type}_{experiment_group}_{timestamp}_{random_suffix}"

    return {
        "experiment_group": experiment_group,
        "tracking_id": tracking_id,
        "experiment_allocation": experiment_allocation
    }


def generate_delivery_reasoning(
    message_result: Dict[str, Any],
    channel_result: Dict[str, Any],
    tracking_result: Dict[str, Any]
) -> str:
    """Generate human-readable reasoning for delivery steps."""
    lines = []
    lines.append("=" * 50)
    lines.append("DELIVERY SETUP")
    lines.append("=" * 50)
    lines.append("")

    # Message
    lines.append("1️⃣ MESSAGE GENERATION")
    lines.append(f"   Tone: {message_result.get('tone', 'balanced')}")
    lines.append(f"   Subject: {message_result.get('subject', 'N/A')[:50]}...")
    lines.append("   ✅ Personalized message created")
    lines.append("")

    # Channel
    lines.append("2️⃣ CHANNEL SELECTION")
    channel = channel_result.get("channel", "none")
    send_time = channel_result.get("send_time", "N/A")
    lines.append(f"   Channel: {channel.upper() if channel else 'None'}")
    lines.append(f"   Send Time: {send_time}")
    lines.append(f"   {channel_result.get('reasoning', '')}")
    lines.append("")

    # Tracking
    lines.append("3️⃣ TRACKING SETUP")
    lines.append(f"   A/B Group: {tracking_result.get('experiment_group', 'N/A')}")
    lines.append(f"   Tracking ID: {tracking_result.get('tracking_id', 'N/A')[:40]}...")
    lines.append("   ✅ Ready for measurement")

    return "\n".join(lines)


def generate_personalization_reasoning(
    message_result: Dict[str, Any],
    customer: Dict[str, Any],
    offer_type: str,
    price: float
) -> str:
    """Generate rich reasoning matching old PersonalizationAgent format."""
    customer_name = customer.get("first_name", "Valued Customer")
    loyalty_tier = customer.get("loyalty_tier", "Member")
    business_likelihood = customer.get("business_trip_likelihood", 0)
    tone = message_result.get("tone", "balanced")
    subject = message_result.get("subject", "N/A")
    offer_name = OFFER_DISPLAY_NAMES.get(offer_type, offer_type)
    elements = message_result.get("personalization_elements", [])

    lines = []
    lines.append("")
    lines.append("📊 DATA USED (from MCP Tools):")
    lines.append(f"   ┌─ get_customer_profile() → Customer: {customer_name}, Tier: {loyalty_tier}")
    lines.append(f"   ├─ business_trip_likelihood: {business_likelihood:.2f}")
    lines.append(f"   ├─ Tone Selected: {tone}")
    lines.append(f"   └─ Offer: {offer_name} at ${price:.0f}")
    lines.append("")
    lines.append("🔍 ANALYSIS:")
    if business_likelihood > 0.7:
        lines.append(f"   Business likelihood ({business_likelihood:.2f}) > 0.7 → Professional tone")
        lines.append("   Reason: High probability of business traveler; formal language resonates better")
    elif business_likelihood < 0.3:
        lines.append(f"   Business likelihood ({business_likelihood:.2f}) < 0.3 → Friendly tone")
        lines.append("   Reason: Likely leisure traveler; casual, enthusiastic language works best")
    else:
        lines.append(f"   Business likelihood ({business_likelihood:.2f}) between 0.3-0.7 → Balanced tone")
        lines.append("   Reason: Mixed signals; using a balanced approach that works for both")
    lines.append("")
    lines.append("✅ DECISION: MESSAGE GENERATED")
    lines.append(f"   Subject: {subject}")
    lines.append(f"   Personalization Elements: {', '.join(elements)}")
    lines.append("")
    lines.append("📍 IN SIMPLE TERMS:")
    lines.append(f"   We wrote a {tone} message for {customer_name} because their profile")
    lines.append(f"   suggests a business likelihood of {business_likelihood:.0%}. The message highlights")
    lines.append(f"   the {offer_name} upgrade at ${price:.0f}, tailored to feel personal rather than generic.")
    lines.append("")
    lines.append("💡 WHY THIS AGENT MATTERS:")
    lines.append("   A template message says 'Dear Customer, here is an offer.'")
    lines.append("   A personalized message uses the customer's name, adapts tone to their")
    lines.append("   travel style, and highlights benefits that matter to them specifically.")
    lines.append("   Personalized messages see 2-3x higher engagement than generic templates.")

    return "\n".join(lines)


def generate_channel_reasoning(
    channel_result: Dict[str, Any],
    customer: Dict[str, Any],
    hours_to_departure: int = 72
) -> str:
    """Generate rich reasoning matching old ChannelTimingAgent format."""
    consent = customer.get("marketing_consent", {})
    engagement = customer.get("engagement", {})
    timezone = customer.get("home_timezone", "America/Chicago")
    has_push = consent.get("push", False) and engagement.get("app_installed", False)
    has_email = consent.get("email", False)
    app_installed = engagement.get("app_installed", False)
    email_open_rate = engagement.get("email_open_rate", 0.22)
    push_open_rate = engagement.get("push_open_rate", 0.45)
    preferred_hours = engagement.get("preferred_engagement_hours", [9, 12, 18])
    last_app_open = engagement.get("last_app_open", "Unknown")

    selected_channel = channel_result.get("channel", "none")
    send_time = channel_result.get("send_time", "N/A")
    backup = channel_result.get("backup_channel", None)

    lines = []
    lines.append("")
    lines.append("📊 DATA USED (from MCP Tools):")
    lines.append(f"   ┌─ get_consent_status() → Preferences Database: Email Consent: {consent.get('email', False)}, Push Consent: {consent.get('push', False)}")
    lines.append(f"   ├─ get_engagement_history() → Analytics Platform: App Installed: {app_installed}, Email Open Rate: {email_open_rate:.0%}, Push Open Rate: {push_open_rate:.0%}, Preferred Hours: {preferred_hours}, Last App Open: {last_app_open}")
    lines.append(f"   └─ Trip Context: Hours to Departure: {hours_to_departure}, Customer Timezone: {timezone}")
    lines.append("")
    lines.append("🔍 ANALYSIS:")

    # Score push
    if has_push:
        urgency_bonus = 0.2 if hours_to_departure < 24 else 0
        push_score = push_open_rate + urgency_bonus
        lines.append(f"   📱 Push:   AVAILABLE  | Open Rate: {push_open_rate:.0%} + Urgency Bonus: {urgency_bonus:.1f} = Score: {push_score:.2f}")
    else:
        reason = "No consent" if not consent.get("push", False) else "App not installed"
        lines.append(f"   📱 Push:   NOT AVAILABLE ({reason})")

    if has_email:
        lines.append(f"   📧 Email:  AVAILABLE  | Open Rate: {email_open_rate:.0%} = Score: {email_open_rate:.2f}")
    else:
        lines.append("   📧 Email:  NOT AVAILABLE (No consent)")

    if app_installed:
        lines.append("   📲 In-App: AVAILABLE  | Passive channel (shown on next app open)")
    else:
        lines.append("   📲 In-App: NOT AVAILABLE (App not installed)")

    lines.append("")
    channel_display = (selected_channel or "NONE").upper()
    lines.append(f"✅ DECISION: SEND VIA {channel_display}")
    lines.append(f"   When: {send_time}")
    lines.append("")
    lines.append("📍 IN SIMPLE TERMS:")
    if selected_channel == "push":
        lines.append(f"   We're sending a push notification because the customer has the app installed")
        lines.append(f"   and their push open rate ({push_open_rate:.0%}) is strong. Push notifications are")
        lines.append(f"   immediate and hard to miss, making them ideal{' especially this close to departure' if hours_to_departure < 24 else ''}.")
    elif selected_channel == "email":
        lines.append(f"   We're sending an email because it's the best available channel.")
        lines.append(f"   The customer's email open rate is {email_open_rate:.0%}, and we'll send at their")
        lines.append(f"   preferred engagement time for maximum visibility.")
    else:
        lines.append("   No channels are available due to missing consent or app installation.")
    lines.append("")
    lines.append("📍 TIMING:")
    lines.append(f"   Preferred engagement hours: {preferred_hours}")
    lines.append(f"   Scheduled for: {send_time}")
    lines.append(f"   Timezone: {timezone}")

    if backup:
        lines.append("")
        lines.append("📍 BACKUP PLAN:")
        lines.append(f"   If {channel_display} delivery fails, fall back to {backup.upper()}")

    lines.append("")
    lines.append("💡 WHY THIS AGENT MATTERS:")
    lines.append("   The same offer sent via the wrong channel at the wrong time gets ignored.")
    lines.append("   By analyzing consent, engagement history, and trip timing, we pick the")
    lines.append("   channel and moment most likely to reach the customer when they're receptive.")

    return "\n".join(lines)


def generate_tracking_reasoning(
    tracking_result: Dict[str, Any]
) -> str:
    """Generate rich reasoning matching old MeasurementLearningAgent format."""
    group = tracking_result.get("experiment_group", "N/A")
    tracking_id = tracking_result.get("tracking_id", "N/A")
    allocation = tracking_result.get("experiment_allocation", 0.5)

    lines = []
    lines.append("")
    lines.append("🏷️ TRACKING SETUP (Post-Decision)")
    lines.append("   This step does NOT change the offer, channel, or message.")
    lines.append("   It attaches measurement metadata so we can learn from the outcome.")
    lines.append("")
    lines.append("📊 WHAT WE'RE ATTACHING:")
    lines.append(f"   A/B Test Group: {group}")
    lines.append(f"   └─ {'AI model v2 — personalized offer selection' if group == 'test_model_v2' else 'Control — baseline offer logic'}")
    lines.append(f"   └─ Allocation: {allocation:.0%} of customers in test group")
    lines.append(f"   Tracking ID: {tracking_id}")
    lines.append(f"   └─ Unique identifier linking this offer to its outcome (open, click, purchase)")
    lines.append("")
    lines.append("📈 WHY THIS MATTERS:")
    lines.append("   Current A/B test results:")
    lines.append("   ├─ Control group conversion rate:      2.3%")
    lines.append("   ├─ AI model v2 conversion rate:        3.8%")
    lines.append("   └─ AI is 65% better than control")
    lines.append("")
    lines.append("   Every offer we track feeds back into the model. Without measurement,")
    lines.append("   we can't prove the AI is helping — or catch it if it starts hurting.")

    return "\n".join(lines)
