"""
Agent 5: Channel & Timing Agent

Purpose: Determines optimal communication channel and timing
Data Sources: Opt-in status, home city timezone, engagement history
Decisions: Push vs email vs in-app, time of day, campaign cadence
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from .state import AgentState


class ChannelTimingAgent:
    """
    Determines the optimal channel and timing for offer delivery.

    This agent answers: "How and when should we send this offer?"
    """

    # Channel effectiveness benchmarks
    CHANNEL_BENCHMARKS = {
        "push": {
            "avg_open_rate": 0.45,
            "avg_conversion_rate": 0.08,
            "best_for": ["urgent", "app_users", "high_engagement"]
        },
        "email": {
            "avg_open_rate": 0.22,
            "avg_conversion_rate": 0.03,
            "best_for": ["detailed_offers", "price_comparison", "fallback"]
        },
        "in_app": {
            "avg_open_rate": 0.65,
            "avg_conversion_rate": 0.12,
            "best_for": ["active_users", "real_time", "high_value"]
        }
    }

    def __init__(self):
        self.name = "Channel & Timing Agent"

    def analyze(self, state: AgentState) -> Dict[str, Any]:
        """
        Select optimal channel and timing for offer delivery.

        Returns updated state with channel and timing decisions.
        """
        reasoning_parts = []

        # Check if we should send offer
        if not state.get("should_send_offer", False):
            return {
                "selected_channel": "",
                "send_time": "",
                "backup_channel": None,
                "channel_reasoning": "No offer to send",
                "reasoning_trace": [f"{self.name}: Skipped - no offer to send"]
            }

        customer = state.get("customer_data", {})
        reservation = state.get("reservation_data", {})

        # Extract relevant data
        consent = customer.get("marketing_consent", {})
        engagement = customer.get("engagement", {})
        timezone = customer.get("home_timezone", "America/Chicago")
        hours_to_departure = reservation.get("hours_to_departure", 72)

        # ========== DATA USED SECTION ==========
        reasoning_parts.append("📊 DATA USED (from MCP Tools):")
        reasoning_parts.append("")
        reasoning_parts.append("┌─ get_consent_status() → Preferences Database")
        reasoning_parts.append(f"│  • Email Consent: {'✓ Yes' if consent.get('email') else '✗ No'}")
        reasoning_parts.append(f"│  • Push Consent: {'✓ Yes' if consent.get('push') else '✗ No'}")
        reasoning_parts.append("│")
        reasoning_parts.append("├─ get_engagement_history() → Analytics Platform")
        reasoning_parts.append(f"│  • App Installed: {'✓ Yes' if engagement.get('app_installed') else '✗ No'}")
        reasoning_parts.append(f"│  • Email Open Rate: {engagement.get('email_open_rate', 0.22):.0%}")
        reasoning_parts.append(f"│  • Push Open Rate: {engagement.get('push_open_rate', 0.45):.0%}")
        reasoning_parts.append(f"│  • Preferred Hours: {engagement.get('preferred_engagement_hours', [9, 12, 18])}")
        reasoning_parts.append(f"│  • Last App Open: {engagement.get('last_app_open', 'N/A')}")
        reasoning_parts.append("│")
        reasoning_parts.append("└─ Trip Context")
        reasoning_parts.append(f"   • Hours to Departure: {hours_to_departure}")
        reasoning_parts.append(f"   • Customer Timezone: {timezone}")

        # ========== ANALYSIS SECTION ==========
        reasoning_parts.append("")
        reasoning_parts.append("─" * 50)
        reasoning_parts.append("")
        reasoning_parts.append("🔍 ANALYSIS:")
        reasoning_parts.append("")
        reasoning_parts.append("   Scoring each available channel:")

        # Evaluate each channel
        channel_scores = {}

        reasoning_parts.append("")

        # Push notification
        if consent.get("push", False) and engagement.get("app_installed", False):
            push_open_rate = engagement.get("push_open_rate", 0.45)
            push_score = self._calculate_channel_score(
                base_rate=push_open_rate,
                customer_rate=push_open_rate,
                urgency_bonus=0.2 if hours_to_departure <= 48 else 0.1,
                engagement_bonus=0.1 if push_open_rate > 0.5 else 0
            )
            channel_scores["push"] = push_score
            reasoning_parts.append(f"   📱 Push Notification: AVAILABLE")
            reasoning_parts.append(f"      • Customer open rate: {push_open_rate:.0%}")
            reasoning_parts.append(f"      • Urgency bonus: {'HIGH' if hours_to_departure <= 48 else 'MEDIUM'} (departure in {hours_to_departure}h)")
            reasoning_parts.append(f"      • Score: {push_score:.2f}")
        else:
            reason = "no app installed" if not engagement.get("app_installed") else "no push consent"
            reasoning_parts.append(f"   📱 Push Notification: NOT AVAILABLE")
            reasoning_parts.append(f"      • Reason: {reason}")

        reasoning_parts.append("")

        # Email
        if consent.get("email", False):
            email_open_rate = engagement.get("email_open_rate", 0.22)
            email_score = self._calculate_channel_score(
                base_rate=email_open_rate,
                customer_rate=email_open_rate,
                urgency_bonus=0.05,  # Email less effective for urgent
                engagement_bonus=0.1 if email_open_rate > 0.3 else 0
            )
            channel_scores["email"] = email_score
            reasoning_parts.append(f"   📧 Email: AVAILABLE")
            reasoning_parts.append(f"      • Customer open rate: {email_open_rate:.0%}")
            reasoning_parts.append(f"      • Note: Email less effective for urgent offers")
            reasoning_parts.append(f"      • Score: {email_score:.2f}")
        else:
            reasoning_parts.append(f"   📧 Email: NOT AVAILABLE")
            reasoning_parts.append(f"      • Reason: no email consent")

        reasoning_parts.append("")

        # In-app (only if app recently used)
        last_app_open = engagement.get("last_app_open")
        if last_app_open and engagement.get("app_installed", False):
            # Check if app was opened recently (within 24 hours)
            # For demo, we'll assume recent if present
            in_app_score = self._calculate_channel_score(
                base_rate=0.65,
                customer_rate=0.65,
                urgency_bonus=0.15,
                engagement_bonus=0.2
            )
            channel_scores["in_app"] = in_app_score
            reasoning_parts.append(f"   📲 In-App Banner: AVAILABLE")
            reasoning_parts.append(f"      • Last app open: {last_app_open}")
            reasoning_parts.append(f"      • Highest engagement rate (~65% visibility)")
            reasoning_parts.append(f"      • Score: {in_app_score:.2f}")

        if not channel_scores:
            reasoning_parts.append("")
            reasoning_parts.append("─" * 50)
            reasoning_parts.append("")
            reasoning_parts.append("❌ DECISION: NO CHANNELS AVAILABLE")
            reasoning_parts.append("")
            reasoning_parts.append("📍 WHY: Customer has not consented to any marketing channel")
            reasoning_parts.append("   or does not have the app installed.")
            return {
                "selected_channel": "",
                "send_time": "",
                "backup_channel": None,
                "channel_reasoning": "\n".join(reasoning_parts),
                "should_send_offer": False,
                "reasoning_trace": [f"{self.name}: No channels available for this customer"]
            }

        # Select primary channel (highest score)
        primary_channel = max(channel_scores, key=channel_scores.get)

        # Select backup channel (second highest, if available)
        backup_channel = None
        sorted_channels = sorted(channel_scores.items(), key=lambda x: x[1], reverse=True)
        if len(sorted_channels) > 1:
            backup_channel = sorted_channels[1][0]

        # Determine optimal send time
        preferred_hours = engagement.get("preferred_engagement_hours", [9, 12, 18])
        send_time, time_reasoning = self._calculate_send_time(
            preferred_hours=preferred_hours,
            hours_to_departure=hours_to_departure,
            timezone=timezone
        )

        # ========== DECISION SECTION ==========
        reasoning_parts.append("")
        reasoning_parts.append("─" * 50)
        reasoning_parts.append("")

        channel_names = {"push": "Push Notification", "email": "Email", "in_app": "In-App Banner"}
        reasoning_parts.append(f"✅ DECISION: SEND VIA {channel_names.get(primary_channel, primary_channel).upper()}")
        reasoning_parts.append(f"   When: {send_time}")
        reasoning_parts.append("")
        reasoning_parts.append("📍 IN SIMPLE TERMS:")
        if primary_channel == "push":
            reasoning_parts.append(f"   We're sending a push notification because:")
            reasoning_parts.append(f"   • This customer opens {engagement.get('push_open_rate', 0.45):.0%} of push messages (good!)")
            if hours_to_departure <= 48:
                reasoning_parts.append("   • The flight is soon - push gets attention FAST")
            reasoning_parts.append("   • They have the app and notifications enabled")
        elif primary_channel == "email":
            reasoning_parts.append(f"   We're sending an email because:")
            reasoning_parts.append(f"   • This customer opens {engagement.get('email_open_rate', 0.22):.0%} of emails")
            reasoning_parts.append("   • Email lets us show all the upgrade details")
            reasoning_parts.append("   • They can read it when convenient")
        elif primary_channel == "in_app":
            reasoning_parts.append(f"   We're showing an in-app banner because:")
            reasoning_parts.append("   • Customer uses the app regularly")
            reasoning_parts.append("   • In-app messages have the highest response rate")
            reasoning_parts.append("   • They'll see it next time they check their trip")

        reasoning_parts.append("")
        reasoning_parts.append(f"📍 TIMING: {send_time}")
        if "NOW" in send_time:
            reasoning_parts.append("   Sending immediately - flight is coming up soon!")
        else:
            reasoning_parts.append(f"   This customer is most active around: {preferred_hours}")
            reasoning_parts.append("   We'll send when they're likely to see it.")

        if backup_channel:
            reasoning_parts.append("")
            reasoning_parts.append(f"📍 BACKUP PLAN: {channel_names.get(backup_channel, backup_channel)}")
            reasoning_parts.append("   If the first message doesn't get through, try this channel.")

        reasoning_parts.append("")
        reasoning_parts.append("💡 WHY THIS AGENT MATTERS:")
        reasoning_parts.append("   A simple system would just blast everyone with email.")
        reasoning_parts.append("")
        reasoning_parts.append("   This agent figured out the BEST way to reach this person:")
        reasoning_parts.append("   • Checked what channels they've opted into")
        reasoning_parts.append("   • Looked at their past behavior (what do they respond to?)")
        reasoning_parts.append("   • Picked the time when they're most likely to engage")
        reasoning_parts.append("")
        reasoning_parts.append("   Right message + Right channel + Right time = More sales! 🎯")

        full_reasoning = "\n".join(reasoning_parts)

        trace_entry = (
            f"{self.name}: Channel={primary_channel.upper()} | "
            f"Send at {send_time} | "
            f"Backup={backup_channel or 'none'}"
        )

        return {
            "selected_channel": primary_channel,
            "send_time": send_time,
            "backup_channel": backup_channel,
            "channel_reasoning": full_reasoning,
            "reasoning_trace": [trace_entry]
        }

    def _calculate_channel_score(
        self,
        base_rate: float,
        customer_rate: float,
        urgency_bonus: float,
        engagement_bonus: float
    ) -> float:
        """Calculate overall channel effectiveness score"""
        # Weighted combination
        score = (
            customer_rate * 0.5 +  # Customer's historical rate
            base_rate * 0.2 +       # Baseline rate
            urgency_bonus * 0.2 +   # Urgency factor
            engagement_bonus * 0.1   # Engagement factor
        )
        return min(score, 1.0)

    def _calculate_send_time(
        self,
        preferred_hours: List[int],
        hours_to_departure: int,
        timezone: str
    ) -> tuple[str, str]:
        """Calculate optimal send time"""
        now = datetime.now()

        # If urgent (< 24 hours), send now
        if hours_to_departure <= 24:
            return "NOW", "Urgent - sending immediately"

        # Find next preferred hour
        current_hour = now.hour
        next_preferred = None

        for hour in sorted(preferred_hours):
            if hour > current_hour:
                next_preferred = hour
                break

        if next_preferred is None:
            # Next day, first preferred hour
            next_preferred = preferred_hours[0] if preferred_hours else 9
            send_date = now + timedelta(days=1)
        else:
            send_date = now

        send_time = f"{send_date.strftime('%Y-%m-%d')} {next_preferred:02d}:00 {timezone.split('/')[-1]}"
        reasoning = f"Scheduling for customer's preferred engagement window ({next_preferred}:00)"

        return send_time, reasoning
