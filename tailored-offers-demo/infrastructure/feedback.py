"""
Outcome Capture + Feedback Loop System

The MOST CRITICAL component for production-ready agentic AI.
Without feedback loops, agents cannot learn and improve.

This module provides:
1. Outcome Capture: Record whether offers were accepted/rejected
2. Calibration: Compare expected probabilities vs actual outcomes
3. Confidence Adjustment: Update agent confidence based on real results
4. Learning Integration: Feed outcomes back to agents for improvement

The feedback loop closes the gap:
    Current: Data -> Agents -> Offer -> Customer -> ???
    New:     Data -> Agents -> Offer -> Customer -> OUTCOME -> Back to Agents

Usage:
    from infrastructure.feedback import get_feedback_manager, OutcomeType

    # Record an outcome
    feedback = get_feedback_manager()
    feedback.record_outcome(
        pnr="ABC123",
        customer_id="CUST456",
        offer_type="IU_BUSINESS",
        offer_price=299.00,
        expected_probability=0.25,
        expected_value=74.75,
        outcome=OutcomeType.ACCEPTED,
    )

    # Get calibration report
    report = feedback.get_calibration_report()
"""

import os
import json
import statistics
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict

from .logging import get_logger
from .metrics import metrics

logger = get_logger("feedback")


# =============================================================================
# OUTCOME TYPES
# =============================================================================

class OutcomeType(Enum):
    """Possible outcomes for an offer."""
    PENDING = "pending"      # Offer sent, waiting for response
    ACCEPTED = "accepted"    # Customer accepted the offer
    REJECTED = "rejected"    # Customer explicitly rejected
    EXPIRED = "expired"      # Offer expired without response
    CLICKED = "clicked"      # Customer clicked but didn't convert
    UNKNOWN = "unknown"      # Outcome not tracked


class FeedbackStatus(Enum):
    """Status of feedback processing."""
    RECEIVED = "received"
    PROCESSED = "processed"
    APPLIED = "applied"
    FAILED = "failed"


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class OfferOutcome:
    """
    Complete outcome record for an offer.

    This is the fundamental unit of feedback data.
    """
    outcome_id: str
    pnr: str
    customer_id: str
    offer_type: str
    offer_price: float
    discount_percent: float
    expected_probability: float  # P(accept) predicted by agent
    expected_value: float        # EV = P(accept) * revenue
    actual_outcome: OutcomeType
    channel: str

    # Timing
    offer_sent_at: datetime
    outcome_recorded_at: Optional[datetime] = None
    time_to_decision_hours: Optional[float] = None

    # Context
    customer_tier: Optional[str] = None
    flight_route: Optional[str] = None
    hours_to_departure: Optional[int] = None
    experiment_group: Optional[str] = None

    # Agent info
    agent_version: Optional[str] = None
    prompt_version: Optional[str] = None
    model_used: Optional[str] = None

    # Feedback
    customer_feedback: Optional[str] = None
    feedback_status: FeedbackStatus = FeedbackStatus.RECEIVED

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "actual_outcome": self.actual_outcome.value,
            "feedback_status": self.feedback_status.value,
            "offer_sent_at": self.offer_sent_at.isoformat(),
            "outcome_recorded_at": self.outcome_recorded_at.isoformat() if self.outcome_recorded_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OfferOutcome":
        return cls(
            outcome_id=data["outcome_id"],
            pnr=data["pnr"],
            customer_id=data["customer_id"],
            offer_type=data["offer_type"],
            offer_price=data["offer_price"],
            discount_percent=data["discount_percent"],
            expected_probability=data["expected_probability"],
            expected_value=data["expected_value"],
            actual_outcome=OutcomeType(data["actual_outcome"]),
            channel=data["channel"],
            offer_sent_at=datetime.fromisoformat(data["offer_sent_at"]),
            outcome_recorded_at=datetime.fromisoformat(data["outcome_recorded_at"]) if data.get("outcome_recorded_at") else None,
            time_to_decision_hours=data.get("time_to_decision_hours"),
            customer_tier=data.get("customer_tier"),
            flight_route=data.get("flight_route"),
            hours_to_departure=data.get("hours_to_departure"),
            experiment_group=data.get("experiment_group"),
            agent_version=data.get("agent_version"),
            prompt_version=data.get("prompt_version"),
            model_used=data.get("model_used"),
            customer_feedback=data.get("customer_feedback"),
            feedback_status=FeedbackStatus(data.get("feedback_status", "received")),
        )

    @property
    def was_successful(self) -> bool:
        return self.actual_outcome == OutcomeType.ACCEPTED

    @property
    def actual_value(self) -> float:
        """Actual revenue from this offer."""
        if self.was_successful:
            return self.offer_price
        return 0.0

    @property
    def prediction_error(self) -> float:
        """Error in expected value prediction."""
        return self.actual_value - self.expected_value


@dataclass
class CalibrationBucket:
    """
    A bucket for calibration analysis.

    Groups predictions by expected probability ranges.
    """
    bucket_range: Tuple[float, float]  # e.g., (0.2, 0.3)
    predictions: List[float] = field(default_factory=list)
    outcomes: List[bool] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.predictions)

    @property
    def avg_predicted(self) -> float:
        if not self.predictions:
            return 0.0
        return statistics.mean(self.predictions)

    @property
    def actual_rate(self) -> float:
        if not self.outcomes:
            return 0.0
        return sum(self.outcomes) / len(self.outcomes)

    @property
    def calibration_error(self) -> float:
        """Difference between predicted and actual rates."""
        return abs(self.avg_predicted - self.actual_rate)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bucket_range": list(self.bucket_range),
            "count": self.count,
            "avg_predicted": self.avg_predicted,
            "actual_rate": self.actual_rate,
            "calibration_error": self.calibration_error,
        }


@dataclass
class CalibrationReport:
    """
    Complete calibration report for agent predictions.

    Shows how well predicted probabilities match actual outcomes.
    """
    report_id: str
    generated_at: datetime
    period_start: datetime
    period_end: datetime

    # Overall metrics
    total_outcomes: int
    total_accepted: int
    total_rejected: int
    overall_acceptance_rate: float

    # Calibration buckets
    buckets: List[CalibrationBucket]

    # Error metrics
    mean_calibration_error: float  # Average error across buckets
    expected_calibration_error: float  # ECE
    brier_score: float  # Mean squared error

    # Value metrics
    total_expected_value: float
    total_actual_value: float
    value_capture_rate: float  # actual / expected

    # Segmented analysis
    by_offer_type: Dict[str, Dict[str, float]]
    by_customer_tier: Dict[str, Dict[str, float]]
    by_channel: Dict[str, Dict[str, float]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at.isoformat(),
            "period": {
                "start": self.period_start.isoformat(),
                "end": self.period_end.isoformat(),
            },
            "overall": {
                "total_outcomes": self.total_outcomes,
                "total_accepted": self.total_accepted,
                "total_rejected": self.total_rejected,
                "acceptance_rate": self.overall_acceptance_rate,
            },
            "calibration": {
                "buckets": [b.to_dict() for b in self.buckets],
                "mean_error": self.mean_calibration_error,
                "ece": self.expected_calibration_error,
                "brier_score": self.brier_score,
            },
            "value": {
                "total_expected": self.total_expected_value,
                "total_actual": self.total_actual_value,
                "capture_rate": self.value_capture_rate,
            },
            "segments": {
                "by_offer_type": self.by_offer_type,
                "by_customer_tier": self.by_customer_tier,
                "by_channel": self.by_channel,
            },
        }


@dataclass
class AgentFeedback:
    """
    Aggregated feedback for an agent to improve.

    This is what gets fed back to agents for learning.
    """
    agent_name: str
    prompt_version: str

    # Performance metrics
    total_decisions: int
    successful_decisions: int
    success_rate: float

    # Calibration
    avg_calibration_error: float
    overconfident: bool  # Predicts higher than actual
    underconfident: bool  # Predicts lower than actual

    # Recommendations
    confidence_adjustment: float  # How much to adjust confidence
    recommendations: List[str]

    # Specific insights
    best_performing_segments: List[str]
    worst_performing_segments: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =============================================================================
# FEEDBACK STORE
# =============================================================================

class FeedbackStore:
    """
    Storage backend for outcomes and feedback.

    Supports in-memory (dev) or external storage (production).
    """

    def __init__(self):
        self._outcomes: Dict[str, OfferOutcome] = {}
        self._outcomes_by_pnr: Dict[str, str] = {}  # pnr -> outcome_id
        self._outcomes_by_customer: Dict[str, List[str]] = defaultdict(list)

    def save_outcome(self, outcome: OfferOutcome) -> None:
        """Save an outcome record."""
        self._outcomes[outcome.outcome_id] = outcome
        self._outcomes_by_pnr[outcome.pnr] = outcome.outcome_id
        self._outcomes_by_customer[outcome.customer_id].append(outcome.outcome_id)

    def get_outcome(self, outcome_id: str) -> Optional[OfferOutcome]:
        """Get outcome by ID."""
        return self._outcomes.get(outcome_id)

    def get_outcome_by_pnr(self, pnr: str) -> Optional[OfferOutcome]:
        """Get outcome by PNR."""
        outcome_id = self._outcomes_by_pnr.get(pnr)
        if outcome_id:
            return self._outcomes.get(outcome_id)
        return None

    def get_customer_outcomes(self, customer_id: str) -> List[OfferOutcome]:
        """Get all outcomes for a customer."""
        outcome_ids = self._outcomes_by_customer.get(customer_id, [])
        return [self._outcomes[oid] for oid in outcome_ids if oid in self._outcomes]

    def get_outcomes_in_range(
        self,
        start: datetime,
        end: datetime,
    ) -> List[OfferOutcome]:
        """Get all outcomes in a date range."""
        return [
            o for o in self._outcomes.values()
            if o.offer_sent_at >= start and o.offer_sent_at <= end
        ]

    def get_all_outcomes(self) -> List[OfferOutcome]:
        """Get all recorded outcomes."""
        return list(self._outcomes.values())

    def update_outcome(self, outcome_id: str, **updates) -> Optional[OfferOutcome]:
        """Update an existing outcome."""
        outcome = self._outcomes.get(outcome_id)
        if outcome:
            for key, value in updates.items():
                if hasattr(outcome, key):
                    setattr(outcome, key, value)
        return outcome


# =============================================================================
# FEEDBACK MANAGER
# =============================================================================

class FeedbackManager:
    """
    Main interface for the feedback loop system.

    Responsibilities:
    1. Record outcomes from customer actions
    2. Calculate calibration metrics
    3. Generate feedback for agents
    4. Update learning memory with patterns
    """

    def __init__(self, store: Optional[FeedbackStore] = None):
        self.store = store or FeedbackStore()

        # Lazy import to avoid circular dependency
        self._memory = None

    @property
    def memory(self):
        if self._memory is None:
            from .memory import get_memory
            self._memory = get_memory()
        return self._memory

    # =========================================================================
    # OUTCOME RECORDING
    # =========================================================================

    def record_outcome(
        self,
        pnr: str,
        customer_id: str,
        offer_type: str,
        offer_price: float,
        expected_probability: float,
        expected_value: float,
        outcome: OutcomeType,
        channel: str = "unknown",
        discount_percent: float = 0.0,
        **kwargs,
    ) -> OfferOutcome:
        """
        Record the outcome of an offer.

        This is the primary entry point for closing the feedback loop.

        Args:
            pnr: PNR locator for the offer
            customer_id: Customer who received the offer
            offer_type: Type of offer (IU_BUSINESS, MCE, etc.)
            offer_price: Price of the offer
            expected_probability: Agent's predicted P(accept)
            expected_value: Agent's calculated EV
            outcome: Actual outcome (ACCEPTED, REJECTED, etc.)
            channel: Delivery channel
            discount_percent: Discount applied
            **kwargs: Additional context (tier, route, etc.)

        Returns:
            The recorded OfferOutcome
        """
        import uuid

        outcome_record = OfferOutcome(
            outcome_id=f"out_{uuid.uuid4().hex[:12]}",
            pnr=pnr,
            customer_id=customer_id,
            offer_type=offer_type,
            offer_price=offer_price,
            discount_percent=discount_percent,
            expected_probability=expected_probability,
            expected_value=expected_value,
            actual_outcome=outcome,
            channel=channel,
            offer_sent_at=kwargs.get("offer_sent_at", datetime.now()),
            outcome_recorded_at=datetime.now(),
            customer_tier=kwargs.get("customer_tier"),
            flight_route=kwargs.get("flight_route"),
            hours_to_departure=kwargs.get("hours_to_departure"),
            experiment_group=kwargs.get("experiment_group"),
            agent_version=kwargs.get("agent_version"),
            prompt_version=kwargs.get("prompt_version"),
            model_used=kwargs.get("model_used"),
            customer_feedback=kwargs.get("customer_feedback"),
        )

        # Calculate time to decision
        if outcome_record.offer_sent_at and outcome_record.outcome_recorded_at:
            delta = outcome_record.outcome_recorded_at - outcome_record.offer_sent_at
            outcome_record.time_to_decision_hours = delta.total_seconds() / 3600

        # Save to store
        self.store.save_outcome(outcome_record)

        # Record metrics
        self._record_outcome_metrics(outcome_record)

        # Update memory with outcome
        self._update_memory(outcome_record)

        # Process feedback
        self._process_feedback(outcome_record)

        logger.info(
            "outcome_recorded",
            pnr=pnr,
            offer_type=offer_type,
            outcome=outcome.value,
            expected_prob=expected_probability,
            actual_value=outcome_record.actual_value,
        )

        return outcome_record

    def update_outcome(
        self,
        pnr: str,
        outcome: OutcomeType,
        customer_feedback: Optional[str] = None,
    ) -> Optional[OfferOutcome]:
        """
        Update the outcome for a pending offer.

        Used when outcome information arrives later.
        """
        existing = self.store.get_outcome_by_pnr(pnr)
        if not existing:
            logger.warning("outcome_not_found", pnr=pnr)
            return None

        # Update the outcome
        existing.actual_outcome = outcome
        existing.outcome_recorded_at = datetime.now()
        if customer_feedback:
            existing.customer_feedback = customer_feedback

        if existing.offer_sent_at:
            delta = existing.outcome_recorded_at - existing.offer_sent_at
            existing.time_to_decision_hours = delta.total_seconds() / 3600

        # Re-process feedback with new outcome
        self._record_outcome_metrics(existing)
        self._update_memory(existing)
        self._process_feedback(existing)

        logger.info(
            "outcome_updated",
            pnr=pnr,
            outcome=outcome.value,
        )

        return existing

    def _record_outcome_metrics(self, outcome: OfferOutcome) -> None:
        """Record outcome in Prometheus metrics."""
        metrics.record_offer_outcome(
            offer_type=outcome.offer_type,
            outcome=outcome.actual_outcome.value,
            channel=outcome.channel,
        )

        if outcome.was_successful:
            metrics.record_offer_revenue(
                outcome.offer_price,
                outcome.offer_type,
            )

    def _update_memory(self, outcome: OfferOutcome) -> None:
        """Update memory with outcome data."""
        # Record in offer memory
        self.memory.record_outcome(
            pnr=outcome.pnr,
            customer_id=outcome.customer_id,
            offer_type=outcome.offer_type,
            offer_price=outcome.offer_price,
            expected_value=outcome.expected_value,
            actual_outcome=outcome.actual_outcome.value,
        )

        # Record patterns in learning memory
        self.memory.learning.record_pattern(
            pattern_type="outcome",
            pattern_key=f"{outcome.offer_type}_{outcome.channel}",
            success=outcome.was_successful,
            context={
                "price": outcome.offer_price,
                "discount": outcome.discount_percent,
                "tier": outcome.customer_tier,
                "expected_prob": outcome.expected_probability,
            },
        )

        # Record time-based patterns
        hour = outcome.offer_sent_at.hour
        time_key = "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
        self.memory.learning.record_pattern(
            pattern_type="time_of_day",
            pattern_key=time_key,
            success=outcome.was_successful,
            context={"offer_type": outcome.offer_type},
        )

    def _process_feedback(self, outcome: OfferOutcome) -> None:
        """Process outcome and generate feedback for agents."""
        outcome.feedback_status = FeedbackStatus.PROCESSED

        # Check if prediction was significantly off
        if outcome.expected_probability > 0:
            actual_result = 1.0 if outcome.was_successful else 0.0
            prediction_error = abs(actual_result - outcome.expected_probability)

            if prediction_error > 0.3:
                # Large prediction error - log for analysis
                logger.warning(
                    "large_prediction_error",
                    pnr=outcome.pnr,
                    expected=outcome.expected_probability,
                    actual=actual_result,
                    error=prediction_error,
                )

        outcome.feedback_status = FeedbackStatus.APPLIED

    # =========================================================================
    # CALIBRATION ANALYSIS
    # =========================================================================

    def get_calibration_report(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        num_buckets: int = 10,
    ) -> CalibrationReport:
        """
        Generate a calibration report for a time period.

        Calibration measures how well predicted probabilities match actual outcomes.
        A well-calibrated model predicting 30% acceptance should see ~30% actual.

        Args:
            start: Start of analysis period (default: 30 days ago)
            end: End of analysis period (default: now)
            num_buckets: Number of probability buckets

        Returns:
            CalibrationReport with detailed metrics
        """
        import uuid

        if end is None:
            end = datetime.now()
        if start is None:
            start = end - timedelta(days=30)

        # Get outcomes in range
        outcomes = self.store.get_outcomes_in_range(start, end)

        # Filter to completed outcomes
        completed = [
            o for o in outcomes
            if o.actual_outcome in [OutcomeType.ACCEPTED, OutcomeType.REJECTED]
        ]

        if not completed:
            return self._empty_calibration_report(start, end)

        # Build calibration buckets
        bucket_width = 1.0 / num_buckets
        buckets = []

        for i in range(num_buckets):
            bucket_start = i * bucket_width
            bucket_end = (i + 1) * bucket_width
            bucket = CalibrationBucket(bucket_range=(bucket_start, bucket_end))

            for o in completed:
                if bucket_start <= o.expected_probability < bucket_end:
                    bucket.predictions.append(o.expected_probability)
                    bucket.outcomes.append(o.was_successful)

            if bucket.count > 0:
                buckets.append(bucket)

        # Calculate overall metrics
        total_accepted = sum(1 for o in completed if o.was_successful)
        total_rejected = len(completed) - total_accepted
        overall_rate = total_accepted / len(completed) if completed else 0.0

        # Calculate calibration metrics
        predictions = [o.expected_probability for o in completed]
        actuals = [1.0 if o.was_successful else 0.0 for o in completed]

        # Brier score (mean squared error)
        brier = sum((p - a) ** 2 for p, a in zip(predictions, actuals)) / len(completed)

        # Expected Calibration Error
        ece = sum(b.calibration_error * b.count for b in buckets) / len(completed) if buckets else 0.0

        # Mean calibration error
        mce = statistics.mean([b.calibration_error for b in buckets]) if buckets else 0.0

        # Value metrics
        total_ev = sum(o.expected_value for o in completed)
        total_av = sum(o.actual_value for o in completed)
        capture_rate = total_av / total_ev if total_ev > 0 else 0.0

        # Segmented analysis
        by_offer_type = self._analyze_by_segment(completed, "offer_type")
        by_tier = self._analyze_by_segment(completed, "customer_tier")
        by_channel = self._analyze_by_segment(completed, "channel")

        return CalibrationReport(
            report_id=f"cal_{uuid.uuid4().hex[:8]}",
            generated_at=datetime.now(),
            period_start=start,
            period_end=end,
            total_outcomes=len(completed),
            total_accepted=total_accepted,
            total_rejected=total_rejected,
            overall_acceptance_rate=overall_rate,
            buckets=buckets,
            mean_calibration_error=mce,
            expected_calibration_error=ece,
            brier_score=brier,
            total_expected_value=total_ev,
            total_actual_value=total_av,
            value_capture_rate=capture_rate,
            by_offer_type=by_offer_type,
            by_customer_tier=by_tier,
            by_channel=by_channel,
        )

    def _empty_calibration_report(
        self,
        start: datetime,
        end: datetime,
    ) -> CalibrationReport:
        """Return an empty calibration report."""
        import uuid
        return CalibrationReport(
            report_id=f"cal_{uuid.uuid4().hex[:8]}",
            generated_at=datetime.now(),
            period_start=start,
            period_end=end,
            total_outcomes=0,
            total_accepted=0,
            total_rejected=0,
            overall_acceptance_rate=0.0,
            buckets=[],
            mean_calibration_error=0.0,
            expected_calibration_error=0.0,
            brier_score=0.0,
            total_expected_value=0.0,
            total_actual_value=0.0,
            value_capture_rate=0.0,
            by_offer_type={},
            by_customer_tier={},
            by_channel={},
        )

    def _analyze_by_segment(
        self,
        outcomes: List[OfferOutcome],
        segment_field: str,
    ) -> Dict[str, Dict[str, float]]:
        """Analyze calibration by a specific segment."""
        by_segment: Dict[str, List[OfferOutcome]] = defaultdict(list)

        for o in outcomes:
            segment_value = getattr(o, segment_field, None) or "unknown"
            by_segment[segment_value].append(o)

        result = {}
        for segment, segment_outcomes in by_segment.items():
            accepted = sum(1 for o in segment_outcomes if o.was_successful)
            total = len(segment_outcomes)
            avg_pred = statistics.mean([o.expected_probability for o in segment_outcomes])
            actual_rate = accepted / total if total > 0 else 0.0

            result[segment] = {
                "total": total,
                "accepted": accepted,
                "acceptance_rate": actual_rate,
                "avg_predicted": avg_pred,
                "calibration_error": abs(avg_pred - actual_rate),
            }

        return result

    # =========================================================================
    # AGENT FEEDBACK GENERATION
    # =========================================================================

    def get_agent_feedback(
        self,
        agent_name: str,
        prompt_version: Optional[str] = None,
        days: int = 30,
    ) -> AgentFeedback:
        """
        Generate feedback for a specific agent to improve.

        This is what gets fed back into the agent for learning.

        Args:
            agent_name: Name of the agent
            prompt_version: Specific prompt version to analyze
            days: Number of days to analyze

        Returns:
            AgentFeedback with improvement recommendations
        """
        end = datetime.now()
        start = end - timedelta(days=days)

        outcomes = self.store.get_outcomes_in_range(start, end)

        # Filter by agent/prompt version if specified
        if prompt_version:
            outcomes = [o for o in outcomes if o.prompt_version == prompt_version]

        completed = [
            o for o in outcomes
            if o.actual_outcome in [OutcomeType.ACCEPTED, OutcomeType.REJECTED]
        ]

        if not completed:
            return self._empty_agent_feedback(agent_name, prompt_version or "unknown")

        # Calculate metrics
        total = len(completed)
        successful = sum(1 for o in completed if o.was_successful)
        success_rate = successful / total

        # Calibration analysis
        predictions = [o.expected_probability for o in completed]
        actuals = [1.0 if o.was_successful else 0.0 for o in completed]

        avg_predicted = statistics.mean(predictions)
        actual_rate = statistics.mean(actuals)
        calibration_error = abs(avg_predicted - actual_rate)

        overconfident = avg_predicted > actual_rate + 0.05
        underconfident = avg_predicted < actual_rate - 0.05

        # Calculate confidence adjustment
        if overconfident:
            adjustment = -(avg_predicted - actual_rate)
        elif underconfident:
            adjustment = actual_rate - avg_predicted
        else:
            adjustment = 0.0

        # Generate recommendations
        recommendations = self._generate_recommendations(
            outcomes=completed,
            calibration_error=calibration_error,
            overconfident=overconfident,
            underconfident=underconfident,
        )

        # Find best/worst segments
        by_offer = self._analyze_by_segment(completed, "offer_type")
        sorted_offers = sorted(
            by_offer.items(),
            key=lambda x: x[1]["acceptance_rate"],
            reverse=True,
        )

        best = [k for k, v in sorted_offers[:2] if v["acceptance_rate"] > 0.3]
        worst = [k for k, v in sorted_offers[-2:] if v["acceptance_rate"] < 0.2]

        return AgentFeedback(
            agent_name=agent_name,
            prompt_version=prompt_version or "unknown",
            total_decisions=total,
            successful_decisions=successful,
            success_rate=success_rate,
            avg_calibration_error=calibration_error,
            overconfident=overconfident,
            underconfident=underconfident,
            confidence_adjustment=adjustment,
            recommendations=recommendations,
            best_performing_segments=best,
            worst_performing_segments=worst,
        )

    def _empty_agent_feedback(
        self,
        agent_name: str,
        prompt_version: str,
    ) -> AgentFeedback:
        """Return empty feedback for an agent with no data."""
        return AgentFeedback(
            agent_name=agent_name,
            prompt_version=prompt_version,
            total_decisions=0,
            successful_decisions=0,
            success_rate=0.0,
            avg_calibration_error=0.0,
            overconfident=False,
            underconfident=False,
            confidence_adjustment=0.0,
            recommendations=["Insufficient data for feedback"],
            best_performing_segments=[],
            worst_performing_segments=[],
        )

    def _generate_recommendations(
        self,
        outcomes: List[OfferOutcome],
        calibration_error: float,
        overconfident: bool,
        underconfident: bool,
    ) -> List[str]:
        """Generate improvement recommendations based on outcomes."""
        recommendations = []

        # Calibration recommendations
        if calibration_error > 0.15:
            recommendations.append(
                f"HIGH PRIORITY: Calibration error is {calibration_error:.1%} - "
                "predictions are significantly off from actual outcomes"
            )

        if overconfident:
            recommendations.append(
                "Predictions are overconfident - lower expected probabilities by "
                "being more conservative in acceptance rate estimates"
            )

        if underconfident:
            recommendations.append(
                "Predictions are underconfident - consider raising acceptance "
                "probability estimates as customers are converting better than expected"
            )

        # Segment-specific recommendations
        by_discount = defaultdict(list)
        for o in outcomes:
            bucket = "high" if o.discount_percent > 15 else "low" if o.discount_percent < 10 else "medium"
            by_discount[bucket].append(o)

        for bucket, bucket_outcomes in by_discount.items():
            accepted = sum(1 for o in bucket_outcomes if o.was_successful)
            rate = accepted / len(bucket_outcomes) if bucket_outcomes else 0

            if bucket == "high" and rate < 0.2:
                recommendations.append(
                    "High discounts (>15%) not improving conversion - consider "
                    "whether price is the primary barrier"
                )

            if bucket == "low" and rate > 0.4:
                recommendations.append(
                    "Low discounts (<10%) performing well - may not need to "
                    "offer higher discounts for this segment"
                )

        # Time-based recommendations
        by_time = defaultdict(list)
        for o in outcomes:
            hour = o.offer_sent_at.hour
            period = "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
            by_time[period].append(o)

        best_time = max(
            by_time.items(),
            key=lambda x: sum(1 for o in x[1] if o.was_successful) / len(x[1]) if x[1] else 0,
            default=("", []),
        )

        if best_time[0] and len(best_time[1]) > 5:
            rate = sum(1 for o in best_time[1] if o.was_successful) / len(best_time[1])
            if rate > 0.3:
                recommendations.append(
                    f"Best conversion during {best_time[0]} ({rate:.1%}) - "
                    "consider prioritizing this time window"
                )

        if not recommendations:
            recommendations.append("Performance is within expected parameters - continue monitoring")

        return recommendations

    # =========================================================================
    # STATISTICS & REPORTING
    # =========================================================================

    def get_summary_stats(
        self,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get summary statistics for the feedback system."""
        end = datetime.now()
        start = end - timedelta(days=days)

        outcomes = self.store.get_outcomes_in_range(start, end)

        if not outcomes:
            return {
                "period_days": days,
                "total_offers": 0,
                "outcomes_recorded": 0,
                "pending": 0,
                "acceptance_rate": 0.0,
                "avg_expected_value": 0.0,
                "avg_actual_value": 0.0,
            }

        completed = [
            o for o in outcomes
            if o.actual_outcome in [OutcomeType.ACCEPTED, OutcomeType.REJECTED]
        ]
        pending = [o for o in outcomes if o.actual_outcome == OutcomeType.PENDING]

        accepted = sum(1 for o in completed if o.was_successful)

        return {
            "period_days": days,
            "total_offers": len(outcomes),
            "outcomes_recorded": len(completed),
            "pending": len(pending),
            "acceptance_rate": accepted / len(completed) if completed else 0.0,
            "avg_expected_value": statistics.mean([o.expected_value for o in outcomes]),
            "avg_actual_value": statistics.mean([o.actual_value for o in completed]) if completed else 0.0,
            "total_revenue": sum(o.actual_value for o in completed),
            "value_capture_rate": (
                sum(o.actual_value for o in completed) / sum(o.expected_value for o in completed)
                if sum(o.expected_value for o in completed) > 0 else 0.0
            ),
        }

    def get_outcome(self, pnr: str) -> Optional[OfferOutcome]:
        """Get the outcome for a specific PNR."""
        return self.store.get_outcome_by_pnr(pnr)

    def get_customer_history(self, customer_id: str) -> List[OfferOutcome]:
        """Get all outcomes for a customer."""
        return self.store.get_customer_outcomes(customer_id)


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

_feedback_manager: Optional[FeedbackManager] = None


def get_feedback_manager() -> FeedbackManager:
    """Get the global feedback manager instance."""
    global _feedback_manager
    if _feedback_manager is None:
        _feedback_manager = FeedbackManager()
    return _feedback_manager


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def record_offer_outcome(
    pnr: str,
    customer_id: str,
    offer_type: str,
    offer_price: float,
    expected_probability: float,
    expected_value: float,
    outcome: str,
    **kwargs,
) -> OfferOutcome:
    """
    Convenience function to record an outcome.

    Args:
        outcome: String value ("accepted", "rejected", "expired")
    """
    outcome_type = OutcomeType(outcome)
    return get_feedback_manager().record_outcome(
        pnr=pnr,
        customer_id=customer_id,
        offer_type=offer_type,
        offer_price=offer_price,
        expected_probability=expected_probability,
        expected_value=expected_value,
        outcome=outcome_type,
        **kwargs,
    )


def get_calibration_report(days: int = 30) -> CalibrationReport:
    """Convenience function to get calibration report."""
    end = datetime.now()
    start = end - timedelta(days=days)
    return get_feedback_manager().get_calibration_report(start, end)
