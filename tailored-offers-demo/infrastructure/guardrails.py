"""
3-Layer Guardrail Architecture for Tailored Offers

This module implements a latency-optimized guardrail system with three layers:

Layer 1: SYNCHRONOUS PRE-FLIGHT (~40-70ms)
  - Fast checks that MUST pass before LLM/heavy processing
  - Runs inline, blocks workflow if failed
  - Examples: input validation, suppression, consent, rate limits

Layer 2: ASYNCHRONOUS BACKGROUND (~200-500ms)
  - Runs in parallel with the workflow
  - Results checked before final delivery
  - Examples: compliance audit, value validation, fairness monitoring

Layer 3: TRIGGERED ESCALATION (human-in-loop)
  - Activated for exceptional cases
  - Human review for high-risk decisions
  - Examples: high-value offers, anomalies, regulatory flags

Architecture Benefits:
- Fail fast on obvious violations (Layer 1 blocks immediately)
- Don't block on slow checks (Layer 2 runs async)
- Human oversight for edge cases (Layer 3 escalates)
- Latency optimized: ~60ms pre-flight vs ~500ms if all inline
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable, Tuple
from enum import Enum
import asyncio
import time
import re
from datetime import datetime
import threading
import queue


# =============================================================================
# GUARDRAIL RESULT TYPES
# =============================================================================

class GuardrailVerdict(Enum):
    """Outcome of a guardrail check"""
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"  # Passed but flagged for review
    PENDING = "pending"  # Async check still running
    ESCALATE = "escalate"  # Needs human review


@dataclass
class GuardrailResult:
    """Result from a single guardrail check"""
    name: str
    verdict: GuardrailVerdict
    message: str
    latency_ms: float
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LayerResult:
    """Aggregated result from a guardrail layer"""
    layer: str
    passed: bool
    results: List[GuardrailResult] = field(default_factory=list)
    total_latency_ms: float = 0.0
    escalation_required: bool = False
    escalation_reasons: List[str] = field(default_factory=list)


# =============================================================================
# LAYER 1: SYNCHRONOUS PRE-FLIGHT GUARDRAILS (~40-70ms)
# =============================================================================

class SyncGuardrails:
    """
    Fast, synchronous checks that run before any LLM processing.

    These are "pre-flight" checks - if they fail, we abort immediately.
    Target latency: 40-70ms total for all checks.

    Checks:
    1. Input validation (PNR format, required fields)
    2. Customer suppression (is_suppressed flag)
    3. Marketing consent (at least one channel)
    4. Rate limiting (daily offer quota)
    5. Time-to-departure (>6 hours cutoff)
    6. Budget check (has allocation remaining)
    """

    # Configuration
    MIN_HOURS_TO_DEPARTURE = 6
    MAX_DAILY_OFFERS_PER_CUSTOMER = 3
    PNR_PATTERN = re.compile(r'^[A-Z0-9]{6}$')

    def __init__(self):
        self.name = "Sync Pre-flight Guardrails"
        # In production, this would be Redis/cache
        self._rate_limit_cache: Dict[str, int] = {}
        self._budget_remaining: Dict[str, float] = {
            "elite_business": 10000.0,
            "frequent_business": 5000.0,
            "mid_value_business": 3000.0,
            "high_value_leisure": 2000.0,
            "mid_value_leisure": 1500.0,
            "new_customer": 500.0,
            "general": 1000.0,
        }

    def check_all(self, state: Dict[str, Any]) -> LayerResult:
        """
        Run all synchronous guardrails.
        Returns immediately - these checks are fast (~10ms each).
        """
        start_time = time.time()
        results = []

        # Run each check
        results.append(self._check_input_validation(state))
        results.append(self._check_suppression(state))
        results.append(self._check_consent(state))
        results.append(self._check_rate_limit(state))
        results.append(self._check_time_to_departure(state))
        results.append(self._check_budget(state))

        total_latency = (time.time() - start_time) * 1000

        # Aggregate results
        # Only FAIL verdict blocks pre-flight; WARN and ESCALATE are flagged but don't block
        passed = all(r.verdict != GuardrailVerdict.FAIL for r in results)
        escalate = any(r.verdict == GuardrailVerdict.ESCALATE for r in results)
        escalation_reasons = [
            r.message for r in results
            if r.verdict == GuardrailVerdict.ESCALATE
        ]

        return LayerResult(
            layer="sync_preflight",
            passed=passed,
            results=results,
            total_latency_ms=total_latency,
            escalation_required=escalate,
            escalation_reasons=escalation_reasons
        )

    def _check_input_validation(self, state: Dict[str, Any]) -> GuardrailResult:
        """Validate input data format"""
        start = time.time()
        pnr = state.get("pnr_locator", "") or state.get("pnr", "")

        if not pnr:
            return GuardrailResult(
                name="input_validation",
                verdict=GuardrailVerdict.FAIL,
                message="Missing PNR",
                latency_ms=(time.time() - start) * 1000
            )

        if not self.PNR_PATTERN.match(pnr):
            return GuardrailResult(
                name="input_validation",
                verdict=GuardrailVerdict.FAIL,
                message=f"Invalid PNR format: {pnr}",
                latency_ms=(time.time() - start) * 1000
            )

        # Check required state fields
        required = ["customer_data", "flight_data", "reservation_data"]
        missing = [f for f in required if not state.get(f)]

        if missing:
            return GuardrailResult(
                name="input_validation",
                verdict=GuardrailVerdict.FAIL,
                message=f"Missing required data: {missing}",
                latency_ms=(time.time() - start) * 1000
            )

        return GuardrailResult(
            name="input_validation",
            verdict=GuardrailVerdict.PASS,
            message="Input validation passed",
            latency_ms=(time.time() - start) * 1000
        )

    def _check_suppression(self, state: Dict[str, Any]) -> GuardrailResult:
        """Check if customer is suppressed (do not contact)"""
        start = time.time()
        customer = state.get("customer_data", {})
        suppression = customer.get("suppression", {})

        if suppression.get("is_suppressed", False):
            reason = suppression.get("complaint_reason", "Unknown reason")
            return GuardrailResult(
                name="suppression_check",
                verdict=GuardrailVerdict.FAIL,
                message=f"Customer suppressed: {reason}",
                latency_ms=(time.time() - start) * 1000,
                details={"suppression_reason": reason}
            )

        return GuardrailResult(
            name="suppression_check",
            verdict=GuardrailVerdict.PASS,
            message="Customer not suppressed",
            latency_ms=(time.time() - start) * 1000
        )

    def _check_consent(self, state: Dict[str, Any]) -> GuardrailResult:
        """Check marketing consent for at least one channel"""
        start = time.time()
        customer = state.get("customer_data", {})
        consent = customer.get("marketing_consent", {})

        has_any_consent = (
            consent.get("push", False) or
            consent.get("email", False) or
            consent.get("sms", False)
        )

        if not has_any_consent:
            return GuardrailResult(
                name="consent_check",
                verdict=GuardrailVerdict.FAIL,
                message="No marketing consent for any channel",
                latency_ms=(time.time() - start) * 1000
            )

        return GuardrailResult(
            name="consent_check",
            verdict=GuardrailVerdict.PASS,
            message=f"Consent available: push={consent.get('push')}, email={consent.get('email')}",
            latency_ms=(time.time() - start) * 1000,
            details={"consent": consent}
        )

    def _check_rate_limit(self, state: Dict[str, Any]) -> GuardrailResult:
        """Check daily offer quota for customer"""
        start = time.time()
        customer = state.get("customer_data", {})
        customer_id = customer.get("aadvantage_number", "unknown")

        # In production: Redis INCR with TTL
        today = datetime.now().strftime("%Y-%m-%d")
        cache_key = f"{customer_id}:{today}"

        current_count = self._rate_limit_cache.get(cache_key, 0)

        if current_count >= self.MAX_DAILY_OFFERS_PER_CUSTOMER:
            return GuardrailResult(
                name="rate_limit",
                verdict=GuardrailVerdict.FAIL,
                message=f"Daily offer limit reached ({current_count}/{self.MAX_DAILY_OFFERS_PER_CUSTOMER})",
                latency_ms=(time.time() - start) * 1000,
                details={"offers_today": current_count}
            )

        return GuardrailResult(
            name="rate_limit",
            verdict=GuardrailVerdict.PASS,
            message=f"Rate limit OK ({current_count}/{self.MAX_DAILY_OFFERS_PER_CUSTOMER})",
            latency_ms=(time.time() - start) * 1000
        )

    def _check_time_to_departure(self, state: Dict[str, Any]) -> GuardrailResult:
        """Check if enough time before departure"""
        start = time.time()
        reservation = state.get("reservation_data", {})
        hours_to_departure = reservation.get("hours_to_departure", 0)

        if hours_to_departure < self.MIN_HOURS_TO_DEPARTURE:
            return GuardrailResult(
                name="time_to_departure",
                verdict=GuardrailVerdict.FAIL,
                message=f"Too close to departure: {hours_to_departure}h (min: {self.MIN_HOURS_TO_DEPARTURE}h)",
                latency_ms=(time.time() - start) * 1000,
                details={"hours_to_departure": hours_to_departure}
            )

        return GuardrailResult(
            name="time_to_departure",
            verdict=GuardrailVerdict.PASS,
            message=f"Time to departure OK: {hours_to_departure}h",
            latency_ms=(time.time() - start) * 1000
        )

    def _check_budget(self, state: Dict[str, Any]) -> GuardrailResult:
        """Check if budget remains for this customer segment"""
        start = time.time()
        segment = state.get("customer_segment", "general")

        remaining = self._budget_remaining.get(segment, 0)

        if remaining <= 0:
            return GuardrailResult(
                name="budget_check",
                verdict=GuardrailVerdict.WARN,
                message=f"Budget exhausted for segment: {segment}",
                latency_ms=(time.time() - start) * 1000,
                details={"segment": segment, "remaining": remaining}
            )

        return GuardrailResult(
            name="budget_check",
            verdict=GuardrailVerdict.PASS,
            message=f"Budget available: ${remaining:.2f} for {segment}",
            latency_ms=(time.time() - start) * 1000
        )

    def increment_rate_limit(self, customer_id: str):
        """Call this after successfully sending an offer"""
        today = datetime.now().strftime("%Y-%m-%d")
        cache_key = f"{customer_id}:{today}"
        self._rate_limit_cache[cache_key] = self._rate_limit_cache.get(cache_key, 0) + 1

    def deduct_budget(self, segment: str, amount: float):
        """Deduct from segment budget after offer sent"""
        if segment in self._budget_remaining:
            self._budget_remaining[segment] -= amount


# =============================================================================
# LAYER 2: ASYNCHRONOUS BACKGROUND GUARDRAILS (~200-500ms)
# =============================================================================

class AsyncGuardrails:
    """
    Background checks that run in parallel with the workflow.

    These are NOT blocking - workflow continues while they run.
    Results are checked before final delivery.
    Target latency: 200-500ms (runs in parallel, so doesn't add to total).

    Checks:
    1. Compliance audit trail (log decision factors)
    2. Offer value validation (verify EV/discount calculations)
    3. Fairness monitoring (log for bias analysis)
    4. Historical frequency check (avoid over-messaging)
    5. PII handling verification
    """

    def __init__(self):
        self.name = "Async Background Guardrails"
        self._audit_queue: queue.Queue = queue.Queue()
        self._fairness_log: List[Dict] = []

    def start_background_checks(
        self,
        state: Dict[str, Any]
    ) -> "AsyncGuardrailTask":
        """
        Start background checks and return a task handle.

        Usage:
            task = async_guardrails.start_background_checks(state)
            # ... do main processing ...
            result = task.wait_for_completion()  # Check before delivery
        """
        task = AsyncGuardrailTask(self, state)
        task.start()
        return task

    def check_compliance_audit(self, state: Dict[str, Any]) -> GuardrailResult:
        """
        Log all decision factors for compliance audit trail.
        This doesn't block but ensures we have records.
        """
        start = time.time()

        audit_record = {
            "timestamp": datetime.now().isoformat(),
            "pnr": state.get("pnr_locator") or state.get("pnr"),
            "customer_id": state.get("customer_data", {}).get("aadvantage_number"),
            "customer_segment": state.get("customer_segment"),
            "should_send_offer": state.get("should_send_offer"),
            "selected_offer": state.get("selected_offer"),
            "offer_price": state.get("offer_price"),
            "expected_value": state.get("expected_value"),
            "discount_applied": state.get("discount_applied"),
            "suppression_reason": state.get("suppression_reason"),
            "reasoning_trace": state.get("reasoning_trace", []),
        }

        # In production: send to audit log service (Kafka, CloudWatch, etc.)
        self._audit_queue.put(audit_record)

        return GuardrailResult(
            name="compliance_audit",
            verdict=GuardrailVerdict.PASS,
            message="Audit trail logged",
            latency_ms=(time.time() - start) * 1000,
            details={"record_id": audit_record["timestamp"]}
        )

    def check_offer_value_validation(self, state: Dict[str, Any]) -> GuardrailResult:
        """
        Verify offer calculations are within acceptable bounds.
        Double-check EV, discount limits, pricing.
        """
        start = time.time()

        if not state.get("should_send_offer"):
            return GuardrailResult(
                name="offer_value_validation",
                verdict=GuardrailVerdict.PASS,
                message="No offer to validate",
                latency_ms=(time.time() - start) * 1000
            )

        # Check discount limits
        discount = state.get("discount_applied", 0)
        offer_type = state.get("selected_offer", "")

        max_discounts = {
            "IU_BUSINESS": 0.20,
            "IU_FIRST": 0.15,
            "IU_PREMIUM_ECONOMY": 0.15,
            "MCE": 0.25,
        }

        max_allowed = max_discounts.get(offer_type, 0.25)

        if discount > max_allowed:
            return GuardrailResult(
                name="offer_value_validation",
                verdict=GuardrailVerdict.FAIL,
                message=f"Discount {discount:.0%} exceeds max {max_allowed:.0%} for {offer_type}",
                latency_ms=(time.time() - start) * 1000,
                details={"discount": discount, "max_allowed": max_allowed}
            )

        # Check EV is positive
        ev = state.get("expected_value", 0)
        if ev <= 0:
            return GuardrailResult(
                name="offer_value_validation",
                verdict=GuardrailVerdict.WARN,
                message=f"Expected value is non-positive: ${ev:.2f}",
                latency_ms=(time.time() - start) * 1000,
                details={"expected_value": ev}
            )

        # Check price is reasonable
        price = state.get("offer_price", 0)
        if price < 10 or price > 5000:
            return GuardrailResult(
                name="offer_value_validation",
                verdict=GuardrailVerdict.ESCALATE,
                message=f"Unusual price: ${price} (expected $10-$5000)",
                latency_ms=(time.time() - start) * 1000,
                details={"offer_price": price}
            )

        return GuardrailResult(
            name="offer_value_validation",
            verdict=GuardrailVerdict.PASS,
            message=f"Offer validated: {offer_type} @ ${price:.0f} ({discount:.0%} off)",
            latency_ms=(time.time() - start) * 1000
        )

    def check_fairness_monitoring(self, state: Dict[str, Any]) -> GuardrailResult:
        """
        Log data for fairness/bias analysis.
        Tracks offer distribution across segments.
        """
        start = time.time()

        fairness_record = {
            "timestamp": datetime.now().isoformat(),
            "customer_segment": state.get("customer_segment"),
            "loyalty_tier": state.get("customer_data", {}).get("loyalty_tier"),
            "annual_revenue": state.get("customer_data", {}).get("flight_revenue_amt_history", 0),
            "should_send_offer": state.get("should_send_offer"),
            "selected_offer": state.get("selected_offer"),
            "offer_price": state.get("offer_price"),
            "discount_applied": state.get("discount_applied"),
        }

        self._fairness_log.append(fairness_record)

        # In production: periodic analysis job would check for bias
        # e.g., are Gold members getting worse offers than Platinum?

        return GuardrailResult(
            name="fairness_monitoring",
            verdict=GuardrailVerdict.PASS,
            message="Fairness data logged",
            latency_ms=(time.time() - start) * 1000
        )

    def check_historical_frequency(self, state: Dict[str, Any]) -> GuardrailResult:
        """
        Check if customer has been over-contacted recently.
        Prevents offer fatigue.
        """
        start = time.time()
        customer_id = state.get("customer_data", {}).get("aadvantage_number")

        # In production: query historical offer database
        # For demo: simulate check
        recent_offers = 2  # Simulated
        max_weekly = 5

        if recent_offers >= max_weekly:
            return GuardrailResult(
                name="historical_frequency",
                verdict=GuardrailVerdict.WARN,
                message=f"Customer received {recent_offers} offers this week (max: {max_weekly})",
                latency_ms=(time.time() - start) * 1000,
                details={"recent_offers": recent_offers}
            )

        return GuardrailResult(
            name="historical_frequency",
            verdict=GuardrailVerdict.PASS,
            message=f"Frequency OK: {recent_offers}/{max_weekly} this week",
            latency_ms=(time.time() - start) * 1000
        )

    def check_pii_handling(self, state: Dict[str, Any]) -> GuardrailResult:
        """
        Verify no PII in message templates or logs.
        """
        start = time.time()

        message_body = state.get("message_body", "")

        # Check for potential PII patterns
        pii_patterns = [
            (r'\b\d{3}-\d{2}-\d{4}\b', "SSN"),
            (r'\b\d{16}\b', "Credit card"),
            (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', "Email"),
        ]

        found_pii = []
        for pattern, pii_type in pii_patterns:
            if re.search(pattern, message_body):
                found_pii.append(pii_type)

        if found_pii:
            return GuardrailResult(
                name="pii_handling",
                verdict=GuardrailVerdict.FAIL,
                message=f"Potential PII detected in message: {found_pii}",
                latency_ms=(time.time() - start) * 1000,
                details={"pii_types": found_pii}
            )

        return GuardrailResult(
            name="pii_handling",
            verdict=GuardrailVerdict.PASS,
            message="No PII detected in message",
            latency_ms=(time.time() - start) * 1000
        )


class AsyncGuardrailTask:
    """
    Background task handle for async guardrail checks.
    Runs checks in a separate thread, results checked before delivery.
    """

    def __init__(self, guardrails: AsyncGuardrails, state: Dict[str, Any]):
        self.guardrails = guardrails
        self.state = state
        self._thread: Optional[threading.Thread] = None
        self._result: Optional[LayerResult] = None
        self._completed = threading.Event()

    def start(self):
        """Start background checks in a separate thread"""
        self._thread = threading.Thread(target=self._run_checks)
        self._thread.start()

    def _run_checks(self):
        """Run all async checks"""
        start_time = time.time()
        results = []

        results.append(self.guardrails.check_compliance_audit(self.state))
        results.append(self.guardrails.check_offer_value_validation(self.state))
        results.append(self.guardrails.check_fairness_monitoring(self.state))
        results.append(self.guardrails.check_historical_frequency(self.state))
        results.append(self.guardrails.check_pii_handling(self.state))

        total_latency = (time.time() - start_time) * 1000

        # Determine pass/fail
        failures = [r for r in results if r.verdict == GuardrailVerdict.FAIL]
        escalations = [r for r in results if r.verdict == GuardrailVerdict.ESCALATE]

        self._result = LayerResult(
            layer="async_background",
            passed=len(failures) == 0,
            results=results,
            total_latency_ms=total_latency,
            escalation_required=len(escalations) > 0,
            escalation_reasons=[r.message for r in escalations]
        )

        self._completed.set()

    def wait_for_completion(self, timeout_seconds: float = 1.0) -> LayerResult:
        """
        Wait for background checks to complete.
        Call this before final offer delivery.
        """
        completed = self._completed.wait(timeout=timeout_seconds)

        if not completed:
            # Timeout - return pending result
            return LayerResult(
                layer="async_background",
                passed=True,  # Don't block on timeout
                results=[GuardrailResult(
                    name="timeout",
                    verdict=GuardrailVerdict.WARN,
                    message="Async checks timed out",
                    latency_ms=timeout_seconds * 1000
                )],
                total_latency_ms=timeout_seconds * 1000
            )

        return self._result

    def is_complete(self) -> bool:
        """Check if background checks are done without blocking"""
        return self._completed.is_set()


# =============================================================================
# LAYER 3: TRIGGERED ESCALATION GUARDRAILS (Human-in-Loop)
# =============================================================================

class TriggeredGuardrails:
    """
    Human-in-loop escalation for exceptional cases.

    These don't run automatically - they're triggered by specific conditions
    detected in Layer 1 or Layer 2.

    Triggers:
    1. High-value offer (>$500)
    2. Anomaly detection (unusual patterns)
    3. Regulatory flags (sensitive routes/customers)
    4. Override requests
    5. Batch campaign approval
    """

    # Thresholds
    HIGH_VALUE_THRESHOLD = 500.0
    ANOMALY_DEVIATION_THRESHOLD = 3.0  # Standard deviations

    def __init__(self):
        self.name = "Triggered Escalation Guardrails"
        self._escalation_queue: List[Dict] = []
        self._approved_overrides: Dict[str, bool] = {}

    def check_triggers(self, state: Dict[str, Any]) -> LayerResult:
        """
        Check all escalation triggers.
        Returns whether human review is needed.
        """
        start_time = time.time()
        results = []
        escalation_reasons = []

        # Check high-value offers
        high_value_result = self._check_high_value_offer(state)
        results.append(high_value_result)
        if high_value_result.verdict == GuardrailVerdict.ESCALATE:
            escalation_reasons.append(high_value_result.message)

        # Check anomalies
        anomaly_result = self._check_anomaly(state)
        results.append(anomaly_result)
        if anomaly_result.verdict == GuardrailVerdict.ESCALATE:
            escalation_reasons.append(anomaly_result.message)

        # Check regulatory flags
        regulatory_result = self._check_regulatory_flags(state)
        results.append(regulatory_result)
        if regulatory_result.verdict == GuardrailVerdict.ESCALATE:
            escalation_reasons.append(regulatory_result.message)

        total_latency = (time.time() - start_time) * 1000

        return LayerResult(
            layer="triggered_escalation",
            passed=len(escalation_reasons) == 0,
            results=results,
            total_latency_ms=total_latency,
            escalation_required=len(escalation_reasons) > 0,
            escalation_reasons=escalation_reasons
        )

    def _check_high_value_offer(self, state: Dict[str, Any]) -> GuardrailResult:
        """Check if offer exceeds high-value threshold"""
        start = time.time()
        offer_price = state.get("offer_price", 0)

        if offer_price > self.HIGH_VALUE_THRESHOLD:
            return GuardrailResult(
                name="high_value_offer",
                verdict=GuardrailVerdict.ESCALATE,
                message=f"High-value offer: ${offer_price:.0f} (threshold: ${self.HIGH_VALUE_THRESHOLD})",
                latency_ms=(time.time() - start) * 1000,
                details={"offer_price": offer_price, "threshold": self.HIGH_VALUE_THRESHOLD}
            )

        return GuardrailResult(
            name="high_value_offer",
            verdict=GuardrailVerdict.PASS,
            message=f"Offer value OK: ${offer_price:.0f}",
            latency_ms=(time.time() - start) * 1000
        )

    def _check_anomaly(self, state: Dict[str, Any]) -> GuardrailResult:
        """Detect unusual offer patterns"""
        start = time.time()

        # In production: compare to historical distributions
        # For demo: check for obvious anomalies

        discount = state.get("discount_applied", 0)
        ev = state.get("expected_value", 0)

        # Anomaly: Very high discount with low EV
        if discount > 0.15 and ev < 20:
            return GuardrailResult(
                name="anomaly_detection",
                verdict=GuardrailVerdict.ESCALATE,
                message=f"Anomaly: High discount ({discount:.0%}) with low EV (${ev:.2f})",
                latency_ms=(time.time() - start) * 1000,
                details={"discount": discount, "expected_value": ev}
            )

        return GuardrailResult(
            name="anomaly_detection",
            verdict=GuardrailVerdict.PASS,
            message="No anomalies detected",
            latency_ms=(time.time() - start) * 1000
        )

    def _check_regulatory_flags(self, state: Dict[str, Any]) -> GuardrailResult:
        """Check for regulatory/compliance flags"""
        start = time.time()

        flight = state.get("flight_data", {})
        origin = flight.get("schd_leg_dep_airprt_iata_cd", "")
        destination = flight.get("schd_leg_arvl_airprt_iata_cd", "")

        # Sensitive international routes (GDPR, etc.)
        gdpr_countries = ["LHR", "CDG", "FRA", "AMS", "MAD", "FCO"]

        is_gdpr_route = origin in gdpr_countries or destination in gdpr_countries

        if is_gdpr_route:
            return GuardrailResult(
                name="regulatory_flags",
                verdict=GuardrailVerdict.WARN,  # Flag but don't block
                message=f"GDPR-covered route: {origin} → {destination}",
                latency_ms=(time.time() - start) * 1000,
                details={"origin": origin, "destination": destination, "gdpr": True}
            )

        return GuardrailResult(
            name="regulatory_flags",
            verdict=GuardrailVerdict.PASS,
            message="No regulatory flags",
            latency_ms=(time.time() - start) * 1000
        )

    def queue_for_review(
        self,
        state: Dict[str, Any],
        reasons: List[str]
    ) -> str:
        """
        Queue an offer for human review.
        Returns a ticket ID for tracking.
        """
        pnr = state.get('pnr_locator') or state.get('pnr', 'UNKNOWN')
        ticket_id = f"ESC-{datetime.now().strftime('%Y%m%d%H%M%S')}-{pnr}"

        escalation_record = {
            "ticket_id": ticket_id,
            "created_at": datetime.now().isoformat(),
            "pnr": pnr,
            "customer_id": state.get("customer_data", {}).get("aadvantage_number"),
            "offer_type": state.get("selected_offer"),
            "offer_price": state.get("offer_price"),
            "escalation_reasons": reasons,
            "status": "pending_review",
            "state_snapshot": state,
        }

        self._escalation_queue.append(escalation_record)

        # In production: send to ticketing system (ServiceNow, Jira, etc.)

        return ticket_id

    def approve_override(self, ticket_id: str, approved: bool, reviewer: str):
        """Process human review decision"""
        self._approved_overrides[ticket_id] = approved

        # In production: update ticket, notify systems

        return {
            "ticket_id": ticket_id,
            "approved": approved,
            "reviewer": reviewer,
            "processed_at": datetime.now().isoformat()
        }

    def is_approved(self, ticket_id: str) -> Optional[bool]:
        """Check if a ticket has been approved"""
        return self._approved_overrides.get(ticket_id)


# =============================================================================
# GUARDRAIL COORDINATOR
# =============================================================================

class GuardrailCoordinator:
    """
    Orchestrates all three guardrail layers.

    Flow:
    1. Run sync pre-flight checks (blocking, ~60ms)
    2. Start async background checks (non-blocking)
    3. Execute main workflow
    4. Wait for async results before delivery
    5. Check triggered escalations
    6. Either deliver or queue for review
    """

    def __init__(self):
        self.sync = SyncGuardrails()
        self.async_guardrails = AsyncGuardrails()
        self.triggered = TriggeredGuardrails()

    def pre_flight_check(self, state: Dict[str, Any]) -> Tuple[bool, LayerResult]:
        """
        Run Layer 1 sync checks. Call this BEFORE main processing.
        Returns (should_continue, result)
        """
        result = self.sync.check_all(state)
        return (result.passed, result)

    def start_background_checks(self, state: Dict[str, Any]) -> AsyncGuardrailTask:
        """
        Start Layer 2 async checks. Call this DURING main processing.
        Returns task handle to check later.
        """
        return self.async_guardrails.start_background_checks(state)

    def pre_delivery_check(
        self,
        state: Dict[str, Any],
        async_task: AsyncGuardrailTask
    ) -> Tuple[bool, Optional[str], Dict[str, LayerResult]]:
        """
        Final checks before delivery. Call this AFTER main processing.

        Returns:
        - can_deliver: bool - whether to send the offer
        - escalation_ticket: Optional[str] - ticket ID if escalated
        - all_results: Dict[str, LayerResult] - results from all layers
        """
        all_results = {}

        # Wait for async results
        async_result = async_task.wait_for_completion()
        all_results["async_background"] = async_result

        # Check triggered escalations
        triggered_result = self.triggered.check_triggers(state)
        all_results["triggered_escalation"] = triggered_result

        # Aggregate escalation needs
        needs_escalation = (
            async_result.escalation_required or
            triggered_result.escalation_required
        )

        all_reasons = (
            async_result.escalation_reasons +
            triggered_result.escalation_reasons
        )

        escalation_ticket = None
        if needs_escalation:
            escalation_ticket = self.triggered.queue_for_review(state, all_reasons)

        # Can deliver if async passed and no hard escalation needed
        can_deliver = async_result.passed and not needs_escalation

        return (can_deliver, escalation_ticket, all_results)

    def run_all_checks(
        self,
        state: Dict[str, Any]
    ) -> Tuple[bool, Optional[str], Dict[str, LayerResult]]:
        """
        Convenience method to run all checks sequentially.
        For testing or simple use cases.

        In production, use the individual methods for better latency.
        """
        all_results = {}

        # Layer 1: Sync pre-flight
        preflight_passed, preflight_result = self.pre_flight_check(state)
        all_results["sync_preflight"] = preflight_result

        if not preflight_passed:
            return (False, None, all_results)

        # Layer 2: Start async (in this simple case, we wait immediately)
        async_task = self.start_background_checks(state)

        # Layer 3: Pre-delivery checks
        can_deliver, ticket, delivery_results = self.pre_delivery_check(
            state, async_task
        )
        all_results.update(delivery_results)

        return (can_deliver, ticket, all_results)


# =============================================================================
# CONVENIENCE EXPORTS
# =============================================================================

def create_guardrail_coordinator() -> GuardrailCoordinator:
    """Factory function to create a guardrail coordinator"""
    return GuardrailCoordinator()
