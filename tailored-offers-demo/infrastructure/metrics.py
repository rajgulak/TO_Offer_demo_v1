"""
Prometheus Metrics Module

Provides metrics collection for monitoring agent performance,
LLM calls, and system health.
"""

import os
import time
from typing import Optional, Dict, Any, Callable
from functools import wraps
from contextlib import contextmanager

# Try to import prometheus_client, fall back to no-op if not available
try:
    from prometheus_client import (
        Counter,
        Histogram,
        Gauge,
        Summary,
        CollectorRegistry,
        generate_latest,
        start_http_server,
        CONTENT_TYPE_LATEST,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    print("Warning: prometheus-client not installed. Metrics disabled. Install with: pip install prometheus-client")


# Create a custom registry for this application
if PROMETHEUS_AVAILABLE:
    REGISTRY = CollectorRegistry()

    # Agent Metrics
    agent_requests = Counter(
        "tailored_offers_agent_requests_total",
        "Total number of agent requests",
        ["agent_name", "status"],
        registry=REGISTRY,
    )

    agent_duration = Histogram(
        "tailored_offers_agent_duration_seconds",
        "Agent execution duration in seconds",
        ["agent_name"],
        buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
        registry=REGISTRY,
    )

    agent_decision = Counter(
        "tailored_offers_agent_decision_total",
        "Agent decision outcomes",
        ["agent_name", "decision"],
        registry=REGISTRY,
    )

    # LLM Metrics
    llm_calls = Counter(
        "tailored_offers_llm_calls_total",
        "Total number of LLM API calls",
        ["model", "status"],
        registry=REGISTRY,
    )

    llm_latency = Histogram(
        "tailored_offers_llm_latency_seconds",
        "LLM API call latency in seconds",
        ["model"],
        buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
        registry=REGISTRY,
    )

    llm_tokens = Counter(
        "tailored_offers_llm_tokens_total",
        "Total tokens used in LLM calls",
        ["model", "token_type"],  # token_type: input, output
        registry=REGISTRY,
    )

    llm_fallback = Counter(
        "tailored_offers_llm_fallback_total",
        "Number of times LLM fell back to rules",
        ["agent_name", "reason"],
        registry=REGISTRY,
    )

    # MCP Metrics
    mcp_calls = Counter(
        "tailored_offers_mcp_calls_total",
        "Total number of MCP tool calls",
        ["tool_name", "status"],
        registry=REGISTRY,
    )

    mcp_latency = Histogram(
        "tailored_offers_mcp_latency_seconds",
        "MCP tool call latency in seconds",
        ["tool_name"],
        buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
        registry=REGISTRY,
    )

    # Guardrail Metrics
    guardrail_checks = Counter(
        "tailored_offers_guardrail_checks_total",
        "Total guardrail checks performed",
        ["guardrail_name", "result"],  # result: pass, fail
        registry=REGISTRY,
    )

    # Validation Metrics
    validation_results = Counter(
        "tailored_offers_validation_results_total",
        "LLM response validation results",
        ["agent_name", "result"],  # result: valid, invalid
        registry=REGISTRY,
    )

    # Business Metrics
    offer_decisions = Counter(
        "tailored_offers_offer_decisions_total",
        "Offer decision outcomes",
        ["offer_type", "decision"],  # decision: send, suppress
        registry=REGISTRY,
    )

    expected_value = Histogram(
        "tailored_offers_expected_value",
        "Expected value of offers",
        ["offer_type"],
        buckets=(10, 25, 50, 100, 150, 200, 300, 500),
        registry=REGISTRY,
    )

    discount_applied = Histogram(
        "tailored_offers_discount_percent",
        "Discount percentage applied to offers",
        ["offer_type"],
        buckets=(0, 5, 10, 15, 20, 25),
        registry=REGISTRY,
    )

    # Pipeline Metrics
    pipeline_duration = Histogram(
        "tailored_offers_pipeline_duration_seconds",
        "End-to-end pipeline duration",
        [],
        buckets=(1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
        registry=REGISTRY,
    )

    pipeline_success = Counter(
        "tailored_offers_pipeline_success_total",
        "Pipeline completion status",
        ["status"],  # status: success, failure, short_circuit
        registry=REGISTRY,
    )

    # Outcome/Feedback Loop Metrics
    offer_outcomes = Counter(
        "tailored_offers_outcomes_total",
        "Offer outcome tracking",
        ["offer_type", "outcome", "channel"],  # outcome: accepted, rejected, expired
        registry=REGISTRY,
    )

    offer_revenue = Counter(
        "tailored_offers_revenue_total",
        "Total revenue from accepted offers",
        ["offer_type"],
        registry=REGISTRY,
    )

    prediction_error = Histogram(
        "tailored_offers_prediction_error",
        "Difference between expected and actual outcomes",
        ["offer_type"],
        buckets=(-0.5, -0.3, -0.1, 0.0, 0.1, 0.3, 0.5),
        registry=REGISTRY,
    )

    calibration_error = Gauge(
        "tailored_offers_calibration_error",
        "Current calibration error (ECE)",
        ["segment"],  # segment: overall, by_offer_type, by_tier, etc.
        registry=REGISTRY,
    )

    value_capture_rate = Gauge(
        "tailored_offers_value_capture_rate",
        "Actual value / Expected value ratio",
        [],
        registry=REGISTRY,
    )

    feedback_processed = Counter(
        "tailored_offers_feedback_processed_total",
        "Total feedback events processed",
        ["status"],  # status: success, failure
        registry=REGISTRY,
    )

else:
    # No-op metrics when prometheus is not available
    class NoOpMetric:
        def labels(self, *args, **kwargs):
            return self
        def inc(self, amount=1):
            pass
        def dec(self, amount=1):
            pass
        def observe(self, amount):
            pass
        def set(self, value):
            pass
        def time(self):
            return self._no_op_context()
        @contextmanager
        def _no_op_context(self):
            yield

    agent_requests = NoOpMetric()
    agent_duration = NoOpMetric()
    agent_decision = NoOpMetric()
    llm_calls = NoOpMetric()
    llm_latency = NoOpMetric()
    llm_tokens = NoOpMetric()
    llm_fallback = NoOpMetric()
    mcp_calls = NoOpMetric()
    mcp_latency = NoOpMetric()
    guardrail_checks = NoOpMetric()
    validation_results = NoOpMetric()
    offer_decisions = NoOpMetric()
    expected_value = NoOpMetric()
    discount_applied = NoOpMetric()
    pipeline_duration = NoOpMetric()
    pipeline_success = NoOpMetric()
    offer_outcomes = NoOpMetric()
    offer_revenue = NoOpMetric()
    prediction_error = NoOpMetric()
    calibration_error = NoOpMetric()
    value_capture_rate = NoOpMetric()
    feedback_processed = NoOpMetric()
    REGISTRY = None


class MetricsCollector:
    """
    Centralized metrics collection for the application.

    Provides a convenient interface for recording metrics from agents
    and other components.
    """

    def __init__(self):
        self.enabled = PROMETHEUS_AVAILABLE

    def start_metrics_server(self, port: int = 8000):
        """Start the Prometheus metrics HTTP server."""
        if not self.enabled:
            print("Metrics server not started: prometheus-client not installed")
            return

        start_http_server(port, registry=REGISTRY)
        print(f"Metrics server started on port {port}")

    def get_metrics(self) -> bytes:
        """Get the current metrics in Prometheus format."""
        if not self.enabled:
            return b""
        return generate_latest(REGISTRY)

    # Agent metrics
    def record_agent_start(self, agent_name: str) -> float:
        """Record agent execution start. Returns start time."""
        return time.time()

    def record_agent_success(self, agent_name: str, start_time: float, decision: Optional[str] = None):
        """Record successful agent execution."""
        if not self.enabled:
            return

        duration = time.time() - start_time
        agent_requests.labels(agent_name=agent_name, status="success").inc()
        agent_duration.labels(agent_name=agent_name).observe(duration)
        if decision:
            agent_decision.labels(agent_name=agent_name, decision=decision).inc()

    def record_agent_failure(self, agent_name: str, start_time: float, error_type: str = "unknown"):
        """Record failed agent execution."""
        if not self.enabled:
            return

        duration = time.time() - start_time
        agent_requests.labels(agent_name=agent_name, status="failure").inc()
        agent_duration.labels(agent_name=agent_name).observe(duration)

    # LLM metrics
    def record_llm_call(
        self,
        model: str,
        success: bool,
        duration: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ):
        """Record an LLM API call."""
        if not self.enabled:
            return

        status = "success" if success else "failure"
        llm_calls.labels(model=model, status=status).inc()
        llm_latency.labels(model=model).observe(duration)

        if input_tokens > 0:
            llm_tokens.labels(model=model, token_type="input").inc(input_tokens)
        if output_tokens > 0:
            llm_tokens.labels(model=model, token_type="output").inc(output_tokens)

    def record_llm_fallback(self, agent_name: str, reason: str):
        """Record when LLM falls back to rules-based logic."""
        if not self.enabled:
            return
        llm_fallback.labels(agent_name=agent_name, reason=reason).inc()

    # MCP metrics
    def record_mcp_call(self, tool_name: str, success: bool, duration: float):
        """Record an MCP tool call."""
        if not self.enabled:
            return

        status = "success" if success else "failure"
        mcp_calls.labels(tool_name=tool_name, status=status).inc()
        mcp_latency.labels(tool_name=tool_name).observe(duration)

    # Guardrail metrics
    def record_guardrail_check(self, guardrail_name: str, passed: bool):
        """Record a guardrail check result."""
        if not self.enabled:
            return

        result = "pass" if passed else "fail"
        guardrail_checks.labels(guardrail_name=guardrail_name, result=result).inc()

    # Validation metrics
    def record_validation(self, agent_name: str, valid: bool):
        """Record LLM response validation result."""
        if not self.enabled:
            return

        result = "valid" if valid else "invalid"
        validation_results.labels(agent_name=agent_name, result=result).inc()

    # Business metrics
    def record_offer_decision(self, offer_type: str, send: bool, ev: float, discount_pct: float):
        """Record an offer decision with business metrics."""
        if not self.enabled:
            return

        decision = "send" if send else "suppress"
        offer_decisions.labels(offer_type=offer_type, decision=decision).inc()
        expected_value.labels(offer_type=offer_type).observe(ev)
        discount_applied.labels(offer_type=offer_type).observe(discount_pct)

    # Pipeline metrics
    def record_pipeline_completion(self, success: bool, duration: float, short_circuit: bool = False):
        """Record pipeline completion."""
        if not self.enabled:
            return

        if short_circuit:
            status = "short_circuit"
        elif success:
            status = "success"
        else:
            status = "failure"

        pipeline_success.labels(status=status).inc()
        pipeline_duration.observe(duration)

    # Outcome/Feedback Loop metrics
    def record_offer_outcome(
        self,
        offer_type: str,
        outcome: str,
        channel: str = "unknown",
    ):
        """Record an offer outcome (accepted, rejected, expired)."""
        if not self.enabled:
            return

        offer_outcomes.labels(
            offer_type=offer_type,
            outcome=outcome,
            channel=channel,
        ).inc()
        feedback_processed.labels(status="success").inc()

    def record_offer_revenue(self, amount: float, offer_type: str):
        """Record revenue from an accepted offer."""
        if not self.enabled:
            return

        offer_revenue.labels(offer_type=offer_type).inc(amount)

    def record_prediction_error(self, error: float, offer_type: str):
        """Record prediction error (actual - expected)."""
        if not self.enabled:
            return

        prediction_error.labels(offer_type=offer_type).observe(error)

    def record_calibration_error(self, error: float, segment: str = "overall"):
        """Record current calibration error."""
        if not self.enabled:
            return

        calibration_error.labels(segment=segment).set(error)

    def record_value_capture_rate(self, rate: float):
        """Record value capture rate (actual_value / expected_value)."""
        if not self.enabled:
            return

        value_capture_rate.set(rate)


# Global metrics collector instance
metrics = MetricsCollector()


def track_agent_metrics(agent_name: str):
    """Decorator to automatically track agent metrics."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = metrics.record_agent_start(agent_name)
            try:
                result = func(*args, **kwargs)
                decision = result.get("selected_offer") or result.get("decision", "unknown")
                metrics.record_agent_success(agent_name, start_time, decision)
                return result
            except Exception as e:
                metrics.record_agent_failure(agent_name, start_time, type(e).__name__)
                raise
        return wrapper
    return decorator


def track_llm_metrics(model: str = "unknown"):
    """Decorator to automatically track LLM call metrics."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                metrics.record_llm_call(model, True, duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                metrics.record_llm_call(model, False, duration)
                raise
        return wrapper
    return decorator
