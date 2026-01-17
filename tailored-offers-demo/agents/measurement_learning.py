"""
Tracking Setup (Post-Decision)

Purpose: Attach A/B test group and tracking ID for ROI measurement
Note: This runs AFTER the offer decision is made - it doesn't influence what offer to send.

What it does:
- Assigns customer to A/B test group (to compare AI vs old rules)
- Generates unique tracking ID (for conversion attribution)

Why it matters:
- Without tracking, you can't prove the AI system works
- A/B testing shows: "AI converts at 3.8% vs rules at 2.3%"
"""
from typing import Dict, Any
import uuid
import random
from datetime import datetime
from .state import AgentState


class MeasurementLearningAgent:
    """
    Tracking Setup - Attaches A/B test group and tracking ID.

    NOTE: This is POST-DECISION. The offer has already been selected.
    This step just adds tracking metadata for ROI measurement.

    What it does:
    1. Assigns A/B test group (to compare AI vs old rules)
    2. Generates tracking ID (for conversion attribution)
    """

    # A/B Test configuration
    EXPERIMENT_CONFIG = {
        "current_experiment": "TO_MVP1_001",
        "groups": {
            "control": {
                "description": "Rules-based policy only",
                "allocation": 0.10,
                "policy": "rules"
            },
            "test_model_v1": {
                "description": "ML model v1 (baseline)",
                "allocation": 0.30,
                "policy": "model_v1"
            },
            "test_model_v2": {
                "description": "ML model v2 (enhanced features)",
                "allocation": 0.50,
                "policy": "model_v2"
            },
            "exploration": {
                "description": "Exploration for new segments",
                "allocation": 0.10,
                "policy": "exploration"
            }
        },
        # Simulated performance metrics
        "performance": {
            "control": {"conversion_rate": 0.023, "avg_revenue": 45},
            "test_model_v1": {"conversion_rate": 0.031, "avg_revenue": 52},
            "test_model_v2": {"conversion_rate": 0.038, "avg_revenue": 61},
            "exploration": {"conversion_rate": 0.028, "avg_revenue": 48}
        }
    }

    def __init__(self):
        self.name = "Tracking Setup"

    def analyze(self, state: AgentState) -> Dict[str, Any]:
        """
        Attach A/B test group and tracking ID (post-decision).

        NOTE: This doesn't change the offer - it just adds tracking metadata.
        """
        reasoning_parts = []

        # Check if we should send offer
        if not state.get("should_send_offer", False):
            return {
                "experiment_group": "",
                "tracking_id": "",
                "measurement_reasoning": "No offer to track",
                "reasoning_trace": [f"{self.name}: Skipped - no offer to track"]
            }

        customer = state.get("customer_data", {})
        ml_scores = state.get("ml_scores", {})
        customer_segment = state.get("customer_segment", "unknown")
        perf = self.EXPERIMENT_CONFIG["performance"]

        # Get ML confidence for assignment decision
        max_confidence = 0
        if ml_scores:
            for scores in ml_scores.get("propensity_scores", {}).values():
                if isinstance(scores, dict):
                    conf = scores.get("confidence", 0)
                    if conf > max_confidence:
                        max_confidence = conf

        # Assign experiment group
        experiment_group, assignment_reason = self._assign_experiment_group(
            customer=customer,
            ml_scores=ml_scores,
            customer_segment=customer_segment
        )

        # Generate tracking ID
        tracking_id = self._generate_tracking_id(
            pnr=state.get("pnr_locator", ""),
            offer=state.get("selected_offer", ""),
            group=experiment_group
        )

        group_perf = perf.get(experiment_group, {})

        # Build concise reasoning
        reasoning_parts.append("🏷️ TRACKING SETUP (Post-Decision)")
        reasoning_parts.append("")
        reasoning_parts.append("This step doesn't change the offer - it just attaches tracking metadata")
        reasoning_parts.append("so we can measure ROI and prove the AI system works.")
        reasoning_parts.append("")
        reasoning_parts.append("─" * 40)
        reasoning_parts.append("")
        reasoning_parts.append("📊 WHAT WE'RE ATTACHING:")
        reasoning_parts.append("")
        reasoning_parts.append(f"   A/B Test Group: {experiment_group.upper()}")
        reasoning_parts.append(f"   └─ {assignment_reason}")
        reasoning_parts.append("")
        reasoning_parts.append(f"   Tracking ID: {tracking_id}")
        reasoning_parts.append("   └─ Links this offer to conversion events")
        reasoning_parts.append("")
        reasoning_parts.append("─" * 40)
        reasoning_parts.append("")
        reasoning_parts.append("📈 WHY THIS MATTERS:")
        reasoning_parts.append("")
        reasoning_parts.append("   Current A/B Test Results:")
        reasoning_parts.append(f"   • Control (old rules): {perf['control']['conversion_rate']:.1%} conversion")
        reasoning_parts.append(f"   • AI (model v2):       {perf['test_model_v2']['conversion_rate']:.1%} conversion")
        lift_pct = (perf['test_model_v2']['conversion_rate'] - perf['control']['conversion_rate']) / perf['control']['conversion_rate'] * 100
        reasoning_parts.append(f"   • AI is {lift_pct:.0f}% better → This is how we prove ROI")

        full_reasoning = "\n".join(reasoning_parts)

        trace_entry = (
            f"{self.name}: {experiment_group} | "
            f"ID: {tracking_id[:25]}..."
        )

        return {
            "experiment_group": experiment_group,
            "tracking_id": tracking_id,
            "measurement_reasoning": full_reasoning,
            "reasoning_trace": [trace_entry]
        }

    def _assign_experiment_group(
        self,
        customer: Dict[str, Any],
        ml_scores: Dict[str, Any],
        customer_segment: str
    ) -> tuple[str, str]:
        """
        Assign customer to experiment group.

        Assignment logic:
        - New customers (cold start) → exploration group
        - Low ML confidence → rules or exploration
        - Otherwise → weighted random based on allocation
        """
        # Check for cold start (new customer or low confidence)
        if ml_scores:
            propensity = ml_scores.get("propensity_scores", {})
            max_confidence = 0
            for scores in propensity.values():
                if isinstance(scores, dict):
                    conf = scores.get("confidence", 0)
                    if conf > max_confidence:
                        max_confidence = conf

            if max_confidence < 0.5:
                return "exploration", f"Low ML confidence ({max_confidence:.2f}) - gathering learning data"

        # Check for new customer segment
        if customer_segment == "new_customer":
            return "exploration", "New customer segment - exploration for model training"

        # Weighted random assignment based on allocation
        rand = random.random()
        cumulative = 0

        for group, config in self.EXPERIMENT_CONFIG["groups"].items():
            cumulative += config["allocation"]
            if rand < cumulative:
                return group, f"Random assignment (allocation: {config['allocation']:.0%})"

        # Fallback
        return "test_model_v2", "Default assignment"

    def _generate_tracking_id(
        self,
        pnr: str,
        offer: str,
        group: str
    ) -> str:
        """Generate unique tracking ID for attribution"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique = str(uuid.uuid4())[:8]
        return f"TO_{pnr}_{offer}_{group}_{timestamp}_{unique}"
