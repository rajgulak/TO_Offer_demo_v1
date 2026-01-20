"""
Production Safety Infrastructure

This module implements critical production safety features that prevent
real-world failures in agentic systems:

1. IdempotencyManager - Prevents duplicate processing of requests
2. CostTracker - Tracks LLM costs per request for visibility
3. AlertManager - Sends alerts for critical conditions

These address the most common failure patterns in production agent systems:
- Duplicate actions (847 duplicate charges, $84k incident)
- Cost blowouts ($47k unexpected spend in 3 weeks)
- Silent failures (errors accumulating without detection)

Reference: 7-Layer Production Agent Framework
"""

import os
import json
import time
import hashlib
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple, Callable
from enum import Enum
import logging

# Try to import optional dependencies
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


logger = logging.getLogger(__name__)


# =============================================================================
# IDEMPOTENCY MANAGER
# =============================================================================

class IdempotencyStatus(Enum):
    """Status of an idempotent request."""
    NEW = "new"                    # First time seeing this request
    PROCESSING = "processing"      # Currently being processed
    COMPLETED = "completed"        # Successfully completed
    FAILED = "failed"             # Failed (can be retried)


@dataclass
class IdempotencyRecord:
    """Record of an idempotent request."""
    key: str
    status: IdempotencyStatus
    created_at: str
    updated_at: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    attempt_count: int = 1


class IdempotencyManager:
    """
    Prevents duplicate processing of requests.

    Critical for preventing:
    - Duplicate offers sent to same customer
    - Duplicate tracking records
    - Duplicate side effects (emails, notifications)

    Usage:
        idempotency = IdempotencyManager()

        # Generate key for this request
        key = idempotency.get_key(pnr="ABC123", operation="offer_evaluation")

        # Check if already processed
        is_duplicate, cached_result = idempotency.check(key)
        if is_duplicate:
            return cached_result  # Return cached result, don't reprocess

        # Process the request
        try:
            result = process_offer(pnr)
            idempotency.complete(key, result)
            return result
        except Exception as e:
            idempotency.fail(key, str(e))
            raise

    Key Generation:
    - Includes PNR, operation type, and date
    - Same request on same day = same key
    - Next day = new key (allows daily re-evaluation)
    """

    DEFAULT_TTL_SECONDS = 86400  # 24 hours

    def __init__(
        self,
        redis_url: str = None,
        ttl_seconds: int = None,
        key_prefix: str = "idempotency"
    ):
        """
        Initialize IdempotencyManager.

        Args:
            redis_url: Redis connection URL (uses in-memory if not provided)
            ttl_seconds: Time-to-live for idempotency records
            key_prefix: Prefix for all keys
        """
        self.ttl_seconds = ttl_seconds or self.DEFAULT_TTL_SECONDS
        self.key_prefix = key_prefix

        # Use Redis if available and configured, otherwise in-memory
        self._redis = None
        if redis_url and REDIS_AVAILABLE:
            try:
                self._redis = redis.from_url(redis_url)
                self._redis.ping()
                logger.info("IdempotencyManager using Redis backend")
            except Exception as e:
                logger.warning(f"Redis connection failed, using in-memory: {e}")
                self._redis = None

        # In-memory fallback
        self._cache: Dict[str, IdempotencyRecord] = {}
        self._lock = threading.Lock()

    def get_key(
        self,
        pnr: str,
        operation: str,
        include_date: bool = True,
        extra_components: List[str] = None
    ) -> str:
        """
        Generate idempotency key for a request.

        Args:
            pnr: PNR locator
            operation: Operation type (e.g., "offer_evaluation", "send_offer")
            include_date: Include date in key (allows daily re-processing)
            extra_components: Additional components to include in key

        Returns:
            Idempotency key string
        """
        components = [self.key_prefix, operation, pnr]

        if include_date:
            components.append(datetime.now().strftime("%Y-%m-%d"))

        if extra_components:
            components.extend(extra_components)

        # Create deterministic key
        key_string = ":".join(components)
        return key_string

    def check(self, key: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Check if request was already processed.

        Args:
            key: Idempotency key

        Returns:
            (is_duplicate, cached_result)
            - (True, result) if already completed
            - (True, None) if currently processing
            - (False, None) if new request
        """
        record = self._get_record(key)

        if record is None:
            # New request - mark as processing
            self._set_record(key, IdempotencyRecord(
                key=key,
                status=IdempotencyStatus.PROCESSING,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
            ))
            return (False, None)

        if record.status == IdempotencyStatus.COMPLETED:
            logger.info(f"Idempotency hit: {key} already completed")
            return (True, record.result)

        if record.status == IdempotencyStatus.PROCESSING:
            # Check if processing timed out (>5 minutes)
            created = datetime.fromisoformat(record.created_at)
            if datetime.now() - created > timedelta(minutes=5):
                logger.warning(f"Idempotency timeout: {key} stuck in processing, allowing retry")
                # Update attempt count and allow retry
                record.attempt_count += 1
                record.updated_at = datetime.now().isoformat()
                self._set_record(key, record)
                return (False, None)

            logger.info(f"Idempotency: {key} currently processing")
            return (True, None)

        if record.status == IdempotencyStatus.FAILED:
            # Allow retry of failed requests
            logger.info(f"Idempotency: {key} previously failed, allowing retry")
            record.status = IdempotencyStatus.PROCESSING
            record.attempt_count += 1
            record.updated_at = datetime.now().isoformat()
            self._set_record(key, record)
            return (False, None)

        return (False, None)

    def complete(self, key: str, result: Dict[str, Any]):
        """
        Mark request as completed with result.

        Args:
            key: Idempotency key
            result: Result to cache
        """
        record = self._get_record(key)
        if record:
            record.status = IdempotencyStatus.COMPLETED
            record.result = result
            record.updated_at = datetime.now().isoformat()
        else:
            record = IdempotencyRecord(
                key=key,
                status=IdempotencyStatus.COMPLETED,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                result=result,
            )

        self._set_record(key, record)
        logger.info(f"Idempotency: {key} marked completed")

    def fail(self, key: str, error: str):
        """
        Mark request as failed.

        Args:
            key: Idempotency key
            error: Error message
        """
        record = self._get_record(key)
        if record:
            record.status = IdempotencyStatus.FAILED
            record.error = error
            record.updated_at = datetime.now().isoformat()
        else:
            record = IdempotencyRecord(
                key=key,
                status=IdempotencyStatus.FAILED,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                error=error,
            )

        self._set_record(key, record)
        logger.warning(f"Idempotency: {key} marked failed: {error}")

    def _get_record(self, key: str) -> Optional[IdempotencyRecord]:
        """Get record from storage."""
        if self._redis:
            data = self._redis.get(key)
            if data:
                record_dict = json.loads(data)
                return IdempotencyRecord(
                    key=record_dict["key"],
                    status=IdempotencyStatus(record_dict["status"]),
                    created_at=record_dict["created_at"],
                    updated_at=record_dict["updated_at"],
                    result=record_dict.get("result"),
                    error=record_dict.get("error"),
                    attempt_count=record_dict.get("attempt_count", 1),
                )
            return None

        with self._lock:
            return self._cache.get(key)

    def _set_record(self, key: str, record: IdempotencyRecord):
        """Set record in storage."""
        if self._redis:
            record_dict = {
                "key": record.key,
                "status": record.status.value,
                "created_at": record.created_at,
                "updated_at": record.updated_at,
                "result": record.result,
                "error": record.error,
                "attempt_count": record.attempt_count,
            }
            self._redis.setex(key, self.ttl_seconds, json.dumps(record_dict))
            return

        with self._lock:
            self._cache[key] = record
            # Simple TTL cleanup for in-memory
            self._cleanup_expired()

    def _cleanup_expired(self):
        """Remove expired records from in-memory cache."""
        now = datetime.now()
        expired_keys = []

        for key, record in self._cache.items():
            created = datetime.fromisoformat(record.created_at)
            if (now - created).total_seconds() > self.ttl_seconds:
                expired_keys.append(key)

        for key in expired_keys:
            del self._cache[key]

    def get_stats(self) -> Dict[str, Any]:
        """Get idempotency statistics."""
        if self._redis:
            # For Redis, we'd need to scan keys (expensive)
            return {"backend": "redis", "note": "stats require key scan"}

        with self._lock:
            status_counts = {}
            for record in self._cache.values():
                status = record.status.value
                status_counts[status] = status_counts.get(status, 0) + 1

            return {
                "backend": "memory",
                "total_records": len(self._cache),
                "status_counts": status_counts,
            }


# =============================================================================
# COST TRACKER
# =============================================================================

@dataclass
class LLMCallCost:
    """Cost details for an LLM call."""
    request_id: str
    timestamp: str
    model: str
    input_tokens: int
    output_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float
    pnr: Optional[str] = None
    agent_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class CostTracker:
    """
    Tracks LLM costs per request for visibility and budgeting.

    Critical for:
    - Understanding cost drivers
    - Setting budgets and alerts
    - Optimizing expensive operations
    - Preventing cost blowouts

    Usage:
        tracker = CostTracker()

        # Track an LLM call
        cost = tracker.track_call(
            request_id="req-123",
            pnr="ABC123",
            model="gpt-4o",
            input_tokens=1500,
            output_tokens=500,
            agent_name="OfferOrchestration"
        )

        # Get cost summary
        summary = tracker.get_summary(hours=24)
        print(f"Last 24h cost: ${summary['total_cost_usd']:.2f}")

    Pricing is configurable and defaults to approximate 2024 rates.
    """

    # Default pricing per 1K tokens (2024 approximate rates)
    DEFAULT_PRICING = {
        # OpenAI models
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
        # Anthropic models
        "claude-3-opus": {"input": 0.015, "output": 0.075},
        "claude-3-sonnet": {"input": 0.003, "output": 0.015},
        "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
        "claude-3-5-sonnet": {"input": 0.003, "output": 0.015},
        # Default fallback
        "default": {"input": 0.01, "output": 0.03},
    }

    def __init__(
        self,
        pricing: Dict[str, Dict[str, float]] = None,
        budget_hourly_usd: float = None,
        budget_daily_usd: float = None,
    ):
        """
        Initialize CostTracker.

        Args:
            pricing: Custom pricing dict {model: {input: $, output: $}}
            budget_hourly_usd: Optional hourly budget for alerts
            budget_daily_usd: Optional daily budget for alerts
        """
        self.pricing = pricing or self.DEFAULT_PRICING
        self.budget_hourly_usd = budget_hourly_usd or float(os.getenv("LLM_BUDGET_HOURLY", "100"))
        self.budget_daily_usd = budget_daily_usd or float(os.getenv("LLM_BUDGET_DAILY", "1000"))

        # In-memory storage (use TimescaleDB/InfluxDB in production)
        self._calls: List[LLMCallCost] = []
        self._lock = threading.Lock()

        # Aggregated metrics
        self._total_cost_usd = 0.0
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._call_count = 0

    def track_call(
        self,
        request_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        pnr: str = None,
        agent_name: str = None,
        metadata: Dict[str, Any] = None,
    ) -> LLMCallCost:
        """
        Track cost for an LLM call.

        Args:
            request_id: Unique request identifier
            model: Model name (e.g., "gpt-4o", "claude-3-sonnet")
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            pnr: Associated PNR (optional)
            agent_name: Name of the agent making the call
            metadata: Additional metadata

        Returns:
            LLMCallCost with calculated costs
        """
        # Get pricing for model
        model_pricing = self.pricing.get(model, self.pricing["default"])

        # Calculate costs
        input_cost = (input_tokens / 1000) * model_pricing["input"]
        output_cost = (output_tokens / 1000) * model_pricing["output"]
        total_cost = input_cost + output_cost

        # Create cost record
        cost_record = LLMCallCost(
            request_id=request_id,
            timestamp=datetime.now().isoformat(),
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_cost_usd=input_cost,
            output_cost_usd=output_cost,
            total_cost_usd=total_cost,
            pnr=pnr,
            agent_name=agent_name,
            metadata=metadata or {},
        )

        # Store and update aggregates
        with self._lock:
            self._calls.append(cost_record)
            self._total_cost_usd += total_cost
            self._total_input_tokens += input_tokens
            self._total_output_tokens += output_tokens
            self._call_count += 1

        # Log for observability
        logger.info(
            "llm_cost_tracked",
            extra={
                "request_id": request_id,
                "pnr": pnr,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": total_cost,
                "agent": agent_name,
            }
        )

        return cost_record

    def get_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get cost summary for a time window.

        Args:
            hours: Number of hours to look back

        Returns:
            Summary dict with costs, counts, and breakdowns
        """
        cutoff = datetime.now() - timedelta(hours=hours)

        with self._lock:
            recent_calls = [
                c for c in self._calls
                if datetime.fromisoformat(c.timestamp) > cutoff
            ]

        if not recent_calls:
            return {
                "hours": hours,
                "total_cost_usd": 0,
                "call_count": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_by_model": {},
                "cost_by_agent": {},
                "avg_cost_per_call": 0,
            }

        # Aggregate
        total_cost = sum(c.total_cost_usd for c in recent_calls)
        input_tokens = sum(c.input_tokens for c in recent_calls)
        output_tokens = sum(c.output_tokens for c in recent_calls)

        # By model
        cost_by_model = {}
        for c in recent_calls:
            cost_by_model[c.model] = cost_by_model.get(c.model, 0) + c.total_cost_usd

        # By agent
        cost_by_agent = {}
        for c in recent_calls:
            if c.agent_name:
                cost_by_agent[c.agent_name] = cost_by_agent.get(c.agent_name, 0) + c.total_cost_usd

        return {
            "hours": hours,
            "total_cost_usd": total_cost,
            "call_count": len(recent_calls),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_by_model": cost_by_model,
            "cost_by_agent": cost_by_agent,
            "avg_cost_per_call": total_cost / len(recent_calls) if recent_calls else 0,
        }

    def get_hourly_cost(self) -> float:
        """Get cost for the last hour."""
        return self.get_summary(hours=1)["total_cost_usd"]

    def get_daily_cost(self) -> float:
        """Get cost for the last 24 hours."""
        return self.get_summary(hours=24)["total_cost_usd"]

    def check_budget(self) -> Dict[str, Any]:
        """
        Check if costs are within budget.

        Returns:
            Dict with budget status and warnings
        """
        hourly = self.get_hourly_cost()
        daily = self.get_daily_cost()

        return {
            "hourly_cost_usd": hourly,
            "hourly_budget_usd": self.budget_hourly_usd,
            "hourly_utilization": hourly / self.budget_hourly_usd if self.budget_hourly_usd else 0,
            "hourly_exceeded": hourly > self.budget_hourly_usd,
            "daily_cost_usd": daily,
            "daily_budget_usd": self.budget_daily_usd,
            "daily_utilization": daily / self.budget_daily_usd if self.budget_daily_usd else 0,
            "daily_exceeded": daily > self.budget_daily_usd,
        }

    def get_all_time_stats(self) -> Dict[str, Any]:
        """Get all-time statistics."""
        with self._lock:
            return {
                "total_cost_usd": self._total_cost_usd,
                "total_input_tokens": self._total_input_tokens,
                "total_output_tokens": self._total_output_tokens,
                "total_calls": self._call_count,
                "avg_cost_per_call": self._total_cost_usd / self._call_count if self._call_count else 0,
            }


# =============================================================================
# ALERT MANAGER
# =============================================================================

class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """An alert event."""
    id: str
    timestamp: str
    severity: AlertSeverity
    title: str
    message: str
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False


class AlertManager:
    """
    Sends alerts for critical conditions.

    Critical for:
    - Detecting failures early
    - Preventing silent errors from accumulating
    - Enabling quick incident response
    - Cost anomaly detection

    Usage:
        alerts = AlertManager(
            slack_webhook="https://hooks.slack.com/...",
            pagerduty_key="your-key"
        )

        # Manual alert
        alerts.send(
            severity=AlertSeverity.WARNING,
            title="High Error Rate",
            message="Error rate is 5.2% over last 5 minutes"
        )

        # Automated checks (call periodically)
        alerts.check_error_rate(error_count=50, total_count=1000, window_minutes=5)
        alerts.check_cost_anomaly(cost_tracker)

    Supports:
    - Slack webhooks
    - PagerDuty
    - Console/log output (always)
    - Custom handlers
    """

    def __init__(
        self,
        slack_webhook: str = None,
        pagerduty_key: str = None,
        custom_handlers: List[Callable[[Alert], None]] = None,
        error_rate_threshold: float = 0.05,  # 5%
        cost_hourly_threshold: float = 100.0,  # $100/hour
    ):
        """
        Initialize AlertManager.

        Args:
            slack_webhook: Slack incoming webhook URL
            pagerduty_key: PagerDuty integration key
            custom_handlers: List of custom alert handler functions
            error_rate_threshold: Error rate threshold for alerts
            cost_hourly_threshold: Hourly cost threshold for alerts
        """
        self.slack_webhook = slack_webhook or os.getenv("SLACK_ALERT_WEBHOOK")
        self.pagerduty_key = pagerduty_key or os.getenv("PAGERDUTY_KEY")
        self.custom_handlers = custom_handlers or []
        self.error_rate_threshold = error_rate_threshold
        self.cost_hourly_threshold = cost_hourly_threshold

        # Alert history
        self._alerts: List[Alert] = []
        self._lock = threading.Lock()

        # Rate limiting for alerts (prevent alert storms)
        self._last_alert_time: Dict[str, datetime] = {}
        self._alert_cooldown_seconds = 300  # 5 minutes between same alerts

    def send(
        self,
        severity: AlertSeverity,
        title: str,
        message: str,
        source: str = "tailored-offers",
        metadata: Dict[str, Any] = None,
        force: bool = False,
    ) -> Optional[Alert]:
        """
        Send an alert.

        Args:
            severity: Alert severity level
            title: Alert title
            message: Alert message
            source: Source system
            metadata: Additional metadata
            force: Bypass rate limiting

        Returns:
            Alert object if sent, None if rate limited
        """
        # Rate limiting (prevent alert storms)
        alert_key = f"{severity.value}:{title}"
        if not force and alert_key in self._last_alert_time:
            time_since = (datetime.now() - self._last_alert_time[alert_key]).total_seconds()
            if time_since < self._alert_cooldown_seconds:
                logger.debug(f"Alert rate limited: {title} (sent {time_since:.0f}s ago)")
                return None

        # Create alert
        alert = Alert(
            id=f"alert-{datetime.now().strftime('%Y%m%d%H%M%S')}-{hashlib.md5(title.encode()).hexdigest()[:8]}",
            timestamp=datetime.now().isoformat(),
            severity=severity,
            title=title,
            message=message,
            source=source,
            metadata=metadata or {},
        )

        # Store alert
        with self._lock:
            self._alerts.append(alert)
            self._last_alert_time[alert_key] = datetime.now()

        # Always log
        log_level = {
            AlertSeverity.INFO: logging.INFO,
            AlertSeverity.WARNING: logging.WARNING,
            AlertSeverity.ERROR: logging.ERROR,
            AlertSeverity.CRITICAL: logging.CRITICAL,
        }.get(severity, logging.WARNING)

        logger.log(
            log_level,
            f"ALERT [{severity.value.upper()}] {title}: {message}",
            extra={"alert_id": alert.id, "metadata": metadata}
        )

        # Send to configured channels
        if self.slack_webhook:
            self._send_slack(alert)

        if self.pagerduty_key and severity in [AlertSeverity.ERROR, AlertSeverity.CRITICAL]:
            self._send_pagerduty(alert)

        # Custom handlers
        for handler in self.custom_handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Custom alert handler failed: {e}")

        return alert

    def _send_slack(self, alert: Alert):
        """Send alert to Slack."""
        if not REQUESTS_AVAILABLE:
            logger.warning("requests library not available for Slack alerts")
            return

        color_map = {
            AlertSeverity.INFO: "#36a64f",
            AlertSeverity.WARNING: "#ffcc00",
            AlertSeverity.ERROR: "#ff6600",
            AlertSeverity.CRITICAL: "#ff0000",
        }

        payload = {
            "attachments": [{
                "color": color_map.get(alert.severity, "#808080"),
                "title": f"[{alert.severity.value.upper()}] {alert.title}",
                "text": alert.message,
                "fields": [
                    {"title": "Source", "value": alert.source, "short": True},
                    {"title": "Time", "value": alert.timestamp, "short": True},
                ],
                "footer": f"Alert ID: {alert.id}",
            }]
        }

        try:
            response = requests.post(self.slack_webhook, json=payload, timeout=5)
            if response.status_code != 200:
                logger.error(f"Slack alert failed: {response.status_code}")
        except Exception as e:
            logger.error(f"Slack alert failed: {e}")

    def _send_pagerduty(self, alert: Alert):
        """Send alert to PagerDuty."""
        if not REQUESTS_AVAILABLE:
            logger.warning("requests library not available for PagerDuty alerts")
            return

        severity_map = {
            AlertSeverity.INFO: "info",
            AlertSeverity.WARNING: "warning",
            AlertSeverity.ERROR: "error",
            AlertSeverity.CRITICAL: "critical",
        }

        payload = {
            "routing_key": self.pagerduty_key,
            "event_action": "trigger",
            "dedup_key": alert.id,
            "payload": {
                "summary": f"{alert.title}: {alert.message}",
                "severity": severity_map.get(alert.severity, "warning"),
                "source": alert.source,
                "timestamp": alert.timestamp,
                "custom_details": alert.metadata,
            },
        }

        try:
            response = requests.post(
                "https://events.pagerduty.com/v2/enqueue",
                json=payload,
                timeout=5
            )
            if response.status_code != 202:
                logger.error(f"PagerDuty alert failed: {response.status_code}")
        except Exception as e:
            logger.error(f"PagerDuty alert failed: {e}")

    def check_error_rate(
        self,
        error_count: int,
        total_count: int,
        window_minutes: int = 5
    ) -> Optional[Alert]:
        """
        Check error rate and alert if threshold exceeded.

        Args:
            error_count: Number of errors in window
            total_count: Total requests in window
            window_minutes: Time window

        Returns:
            Alert if sent, None otherwise
        """
        if total_count == 0:
            return None

        error_rate = error_count / total_count

        if error_rate > self.error_rate_threshold:
            return self.send(
                severity=AlertSeverity.WARNING if error_rate < 0.10 else AlertSeverity.ERROR,
                title="High Error Rate",
                message=f"Error rate is {error_rate:.1%} ({error_count}/{total_count}) over last {window_minutes} minutes",
                metadata={
                    "error_count": error_count,
                    "total_count": total_count,
                    "error_rate": error_rate,
                    "threshold": self.error_rate_threshold,
                    "window_minutes": window_minutes,
                }
            )

        return None

    def check_cost_anomaly(self, cost_tracker: CostTracker) -> Optional[Alert]:
        """
        Check for cost anomalies and alert.

        Args:
            cost_tracker: CostTracker instance

        Returns:
            Alert if sent, None otherwise
        """
        budget_status = cost_tracker.check_budget()

        if budget_status["hourly_exceeded"]:
            return self.send(
                severity=AlertSeverity.CRITICAL,
                title="Cost Budget Exceeded",
                message=f"Hourly LLM cost ${budget_status['hourly_cost_usd']:.2f} exceeds budget ${budget_status['hourly_budget_usd']:.2f}",
                metadata=budget_status,
            )

        # Warn at 80% utilization
        if budget_status["hourly_utilization"] > 0.8:
            return self.send(
                severity=AlertSeverity.WARNING,
                title="Cost Budget Warning",
                message=f"Hourly LLM cost ${budget_status['hourly_cost_usd']:.2f} is at {budget_status['hourly_utilization']:.0%} of budget",
                metadata=budget_status,
            )

        return None

    def check_circuit_breaker(self, breaker_name: str, is_open: bool) -> Optional[Alert]:
        """
        Alert when circuit breaker opens.

        Args:
            breaker_name: Name of the circuit breaker
            is_open: Whether the breaker is open

        Returns:
            Alert if sent, None otherwise
        """
        if is_open:
            return self.send(
                severity=AlertSeverity.ERROR,
                title="Circuit Breaker Open",
                message=f"Circuit breaker '{breaker_name}' has opened due to failures",
                metadata={"breaker_name": breaker_name},
            )

        return None

    def get_recent_alerts(self, hours: int = 24) -> List[Alert]:
        """Get alerts from the last N hours."""
        cutoff = datetime.now() - timedelta(hours=hours)

        with self._lock:
            return [
                a for a in self._alerts
                if datetime.fromisoformat(a.timestamp) > cutoff
            ]

    def get_alert_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Get alert statistics."""
        recent = self.get_recent_alerts(hours)

        by_severity = {}
        for alert in recent:
            sev = alert.severity.value
            by_severity[sev] = by_severity.get(sev, 0) + 1

        return {
            "hours": hours,
            "total_alerts": len(recent),
            "by_severity": by_severity,
            "acknowledged": sum(1 for a in recent if a.acknowledged),
            "unacknowledged": sum(1 for a in recent if not a.acknowledged),
        }


# =============================================================================
# CONVENIENCE: Production Safety Coordinator
# =============================================================================

class ProductionSafetyCoordinator:
    """
    Coordinates all production safety features.

    Usage:
        safety = ProductionSafetyCoordinator()

        # In your request handler
        async def handle_offer_request(pnr: str):
            # Check idempotency
            idem_key = safety.idempotency.get_key(pnr, "offer_evaluation")
            is_dup, cached = safety.idempotency.check(idem_key)
            if is_dup and cached:
                return cached

            try:
                # Process request
                result = await process_offer(pnr)

                # Track cost (if LLM was used)
                safety.cost_tracker.track_call(...)

                # Mark complete
                safety.idempotency.complete(idem_key, result)

                return result

            except Exception as e:
                safety.idempotency.fail(idem_key, str(e))
                safety.alerts.send(
                    severity=AlertSeverity.ERROR,
                    title="Offer Processing Failed",
                    message=str(e)
                )
                raise
    """

    def __init__(
        self,
        redis_url: str = None,
        slack_webhook: str = None,
        pagerduty_key: str = None,
    ):
        self.idempotency = IdempotencyManager(redis_url=redis_url)
        self.cost_tracker = CostTracker()
        self.alerts = AlertManager(
            slack_webhook=slack_webhook,
            pagerduty_key=pagerduty_key,
        )

    def run_periodic_checks(self, error_count: int = 0, total_count: int = 0):
        """
        Run periodic health checks.

        Call this periodically (e.g., every minute) to check for anomalies.
        """
        # Check error rate
        if total_count > 0:
            self.alerts.check_error_rate(error_count, total_count)

        # Check cost
        self.alerts.check_cost_anomaly(self.cost_tracker)

    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status."""
        return {
            "idempotency": self.idempotency.get_stats(),
            "cost": self.cost_tracker.check_budget(),
            "alerts": self.alerts.get_alert_stats(hours=1),
        }


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

_coordinator: Optional[ProductionSafetyCoordinator] = None


def get_safety_coordinator() -> ProductionSafetyCoordinator:
    """Get or create the global safety coordinator."""
    global _coordinator
    if _coordinator is None:
        _coordinator = ProductionSafetyCoordinator(
            redis_url=os.getenv("REDIS_URL"),
            slack_webhook=os.getenv("SLACK_ALERT_WEBHOOK"),
            pagerduty_key=os.getenv("PAGERDUTY_KEY"),
        )
    return _coordinator


def create_safety_coordinator(
    redis_url: str = None,
    slack_webhook: str = None,
    pagerduty_key: str = None,
) -> ProductionSafetyCoordinator:
    """Create a new safety coordinator with custom config."""
    return ProductionSafetyCoordinator(
        redis_url=redis_url,
        slack_webhook=slack_webhook,
        pagerduty_key=pagerduty_key,
    )
