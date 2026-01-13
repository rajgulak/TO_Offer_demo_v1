"""
Agent 6: Measurement & Learning Agent

Purpose: Tracks performance, runs A/B tests, provides feedback loop
Data Sources: Offer interactions, conversion rates, revenue impact
Decisions: A/B test cell assignment, model refinement, strategy adjustments
"""
from typing import Dict, Any, Optional
import uuid
import random
from datetime import datetime
from .state import AgentState


class MeasurementLearningAgent:
    """
    Manages experiment assignment and learning feedback loop.

    This agent answers: "How do we measure and improve?"

    Key responsibilities:
    - Assign customers to A/B test groups
    - Generate tracking IDs for attribution
    - Recommend policy adjustments based on performance
    - Identify opportunities for model improvement
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
        self.name = "Measurement & Learning Agent"

    def analyze(self, state: AgentState) -> Dict[str, Any]:
        """
        Assign experiment group and generate tracking.

        Returns updated state with measurement configuration.
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

        # ========== THE BUSINESS PROBLEM ==========
        reasoning_parts.append("🤔 THE BUSINESS PROBLEM:")
        reasoning_parts.append("")
        reasoning_parts.append("   How do we PROVE this AI system actually works?")
        reasoning_parts.append("")
        reasoning_parts.append("   Without measurement:")
        reasoning_parts.append("   • Boss: \"Is the AI worth the investment?\"")
        reasoning_parts.append("   • You: \"Uh... we think so?\"")
        reasoning_parts.append("")
        reasoning_parts.append("   With measurement:")
        reasoning_parts.append("   • Boss: \"Is the AI worth the investment?\"")
        reasoning_parts.append("   • You: \"Yes! AI converts at 3.8% vs old rules at 2.3% = 65% better!\"")
        reasoning_parts.append("")
        reasoning_parts.append("─" * 50)
        reasoning_parts.append("")

        # ========== DATA USED SECTION ==========
        reasoning_parts.append("📊 DATA USED (from MCP Tools):")
        reasoning_parts.append("")
        reasoning_parts.append("┌─ assign_experiment() → Experiment Platform")
        reasoning_parts.append(f"│  • Active Experiment: {self.EXPERIMENT_CONFIG['current_experiment']}")
        reasoning_parts.append("│")
        reasoning_parts.append("├─ Current Results (why this matters!):")
        perf = self.EXPERIMENT_CONFIG["performance"]
        reasoning_parts.append(f"│  • Old way (rules only): {perf['control']['conversion_rate']:.1%} conversion")
        reasoning_parts.append(f"│  • AI way (model v2):    {perf['test_model_v2']['conversion_rate']:.1%} conversion")
        lift = (perf['test_model_v2']['conversion_rate'] - perf['control']['conversion_rate']) / perf['control']['conversion_rate'] * 100
        reasoning_parts.append(f"│  • AI is {lift:.0f}% BETTER! ← This is how we prove ROI")
        reasoning_parts.append("│")
        reasoning_parts.append("└─ Customer Context")
        reasoning_parts.append(f"   • Segment: {customer_segment}")

        # Get ML confidence
        max_confidence = 0
        if ml_scores:
            for scores in ml_scores.get("propensity_scores", {}).values():
                if isinstance(scores, dict):
                    conf = scores.get("confidence", 0)
                    if conf > max_confidence:
                        max_confidence = conf
        reasoning_parts.append(f"│  • ML Model Confidence: {max_confidence:.0%}")
        reasoning_parts.append("│")
        reasoning_parts.append("└─ Current Experiment Performance")
        for group, metrics in self.EXPERIMENT_CONFIG["performance"].items():
            reasoning_parts.append(f"   • {group}: {metrics['conversion_rate']:.1%} conversion, ${metrics['avg_revenue']} avg revenue")

        # ========== ANALYSIS SECTION ==========
        reasoning_parts.append("")
        reasoning_parts.append("─" * 50)
        reasoning_parts.append("")
        reasoning_parts.append("🔍 HOW A/B TESTING WORKS:")
        reasoning_parts.append("")
        reasoning_parts.append("   Think of it like a taste test:")
        reasoning_parts.append("")
        reasoning_parts.append("   ┌──────────────────────────────────────────────────┐")
        reasoning_parts.append("   │  10% of customers → Old way (rules only)         │")
        reasoning_parts.append("   │  90% of customers → New AI way                   │")
        reasoning_parts.append("   │                                                  │")
        reasoning_parts.append("   │  Then we compare: Which group bought more?       │")
        reasoning_parts.append("   │  That's how we PROVE the AI is worth it.         │")
        reasoning_parts.append("   └──────────────────────────────────────────────────┘")
        reasoning_parts.append("")

        # Determine experiment assignment
        experiment_group, assignment_reason = self._assign_experiment_group(
            customer=customer,
            ml_scores=ml_scores,
            customer_segment=customer_segment
        )

        reasoning_parts.append(f"   Assignment Decision:")
        if max_confidence < 0.5:
            reasoning_parts.append(f"   • ML confidence is LOW ({max_confidence:.0%})")
            reasoning_parts.append("   • → Assigning to EXPLORATION to gather learning data")
        elif customer_segment == "new_customer":
            reasoning_parts.append("   • Customer is in NEW segment")
            reasoning_parts.append("   • → Assigning to EXPLORATION to build model for this segment")
        else:
            reasoning_parts.append(f"   • Good ML confidence ({max_confidence:.0%})")
            reasoning_parts.append(f"   • → Random assignment based on configured allocations")

        # Generate tracking ID
        tracking_id = self._generate_tracking_id(
            pnr=state.get("pnr_locator", ""),
            offer=state.get("selected_offer", ""),
            group=experiment_group
        )

        # ========== DECISION SECTION ==========
        reasoning_parts.append("")
        reasoning_parts.append("─" * 50)
        reasoning_parts.append("")

        perf = self.EXPERIMENT_CONFIG["performance"].get(experiment_group, {})
        reasoning_parts.append(f"✅ DECISION: PUT IN '{experiment_group.upper()}' TEST GROUP")
        reasoning_parts.append("")
        reasoning_parts.append("📍 IN SIMPLE TERMS:")
        reasoning_parts.append(f"   We're testing different strategies to find what works best.")
        reasoning_parts.append(f"   This customer goes into the '{experiment_group}' group.")
        reasoning_parts.append("")
        if experiment_group == "exploration":
            reasoning_parts.append("   Why exploration? We don't have enough data on customers like this.")
            reasoning_parts.append("   By trying different offers, we'll LEARN what works for them.")
        elif experiment_group == "test_model_v2":
            reasoning_parts.append("   Why v2? Our new ML model is performing better.")
            reasoning_parts.append("   We're testing it on more customers to confirm.")
        elif experiment_group == "control":
            reasoning_parts.append("   Why control? We need a baseline to compare against.")
            reasoning_parts.append("   This helps us prove the AI is actually better.")

        reasoning_parts.append("")
        reasoning_parts.append("📍 HOW WE'LL MEASURE SUCCESS:")
        reasoning_parts.append(f"   Tracking ID: {tracking_id}")
        reasoning_parts.append("")
        reasoning_parts.append("   When the customer gets this offer, we'll track:")
        reasoning_parts.append("   • Did they open the message?")
        reasoning_parts.append("   • Did they click to learn more?")
        reasoning_parts.append("   • Did they actually BUY the upgrade?")
        reasoning_parts.append("   • How much revenue did we make?")
        reasoning_parts.append("")
        reasoning_parts.append(f"   Expected results for this group:")
        reasoning_parts.append(f"   • ~{perf.get('conversion_rate', 0):.1%} will buy (based on past data)")
        reasoning_parts.append(f"   • ~${perf.get('avg_revenue', 0)} average revenue per customer")

        # Add learning recommendations
        recommendations = self._generate_recommendations(
            ml_scores=ml_scores,
            customer_segment=customer_segment,
            experiment_group=experiment_group
        )

        if recommendations:
            reasoning_parts.append("")
            reasoning_parts.append("📍 WHAT WE'RE LEARNING:")
            for rec in recommendations:
                reasoning_parts.append(f"   • {rec}")

        reasoning_parts.append("")
        reasoning_parts.append("💡 WHY THIS AGENT MATTERS:")
        reasoning_parts.append("")
        reasoning_parts.append("   Without this agent:")
        reasoning_parts.append("   • Send offers → hope they work → no idea if AI is helping")
        reasoning_parts.append("")
        reasoning_parts.append("   With this agent:")
        reasoning_parts.append("   • Send offers → track everything → PROVE ROI to leadership")
        reasoning_parts.append("")
        reasoning_parts.append("   Real example from our data:")
        reasoning_parts.append(f"   • Old rules: {perf['control']['conversion_rate']:.1%} buy rate × ${perf['control']['avg_revenue']} = ${perf['control']['conversion_rate'] * perf['control']['avg_revenue'] * 1000:.0f} per 1000 offers")
        reasoning_parts.append(f"   • AI system: {perf['test_model_v2']['conversion_rate']:.1%} buy rate × ${perf['test_model_v2']['avg_revenue']} = ${perf['test_model_v2']['conversion_rate'] * perf['test_model_v2']['avg_revenue'] * 1000:.0f} per 1000 offers")
        reasoning_parts.append("")
        reasoning_parts.append(f"   That's ${(perf['test_model_v2']['conversion_rate'] * perf['test_model_v2']['avg_revenue'] - perf['control']['conversion_rate'] * perf['control']['avg_revenue']) * 1000:.0f} MORE revenue per 1000 offers!")
        reasoning_parts.append("   NOW you can justify the AI investment. 📈")

        full_reasoning = "\n".join(reasoning_parts)

        trace_entry = (
            f"{self.name}: Assigned to {experiment_group} | "
            f"Tracking: {tracking_id} | "
            f"Expected conversion: {perf.get('conversion_rate', 0):.1%}"
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

    def _generate_recommendations(
        self,
        ml_scores: Dict[str, Any],
        customer_segment: str,
        experiment_group: str
    ) -> list:
        """Generate learning recommendations based on current state"""
        recommendations = []

        # Check model performance
        perf = self.EXPERIMENT_CONFIG["performance"]
        if perf["test_model_v2"]["conversion_rate"] > perf["test_model_v1"]["conversion_rate"] * 1.15:
            recommendations.append(
                "Model v2 showing 15%+ lift over v1 - consider graduating to production"
            )

        # Check for cold start issues
        if ml_scores:
            for offer_type, scores in ml_scores.get("propensity_scores", {}).items():
                if isinstance(scores, dict) and scores.get("error") == "cold_start_insufficient_history":
                    recommendations.append(
                        f"Cold start detected for {offer_type} - flagging for model retraining"
                    )

        # Segment-specific recommendations
        if customer_segment == "new_customer":
            recommendations.append(
                "New customer data being collected for model improvement"
            )

        if experiment_group == "exploration":
            recommendations.append(
                "Exploration assignment - results will inform segment strategy"
            )

        return recommendations
