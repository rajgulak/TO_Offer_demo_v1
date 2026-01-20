"""
Human-in-the-Loop (HITL) Implementation for Agentic AI

This module implements production-grade human-in-the-loop patterns:
1. Deferred Execution - Halt workflow at risky steps, persist state
2. State Serialization - Full agent state saved for later resume
3. Approval Management - Pending approvals with approve/deny actions
4. Notification Integration - Slack/email for approval requests
5. Stateless Resume - Reconstruct and continue workflow days later

Key Patterns:
- Streaming Chat: SSE → halt → save state → approval UI → resume endpoint
- Async Workflow: Background job → notification → approve/deny → resume

References:
- https://www.youtube.com/watch?v=7GOxUgVTz3s
"""

import json
import uuid
import hashlib
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, Optional, List, Callable, Tuple
import os
import requests

from .logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Data Models
# =============================================================================

class ApprovalStatus(str, Enum):
    """Status of a pending approval."""
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    AUTO_APPROVED = "auto_approved"


class EscalationReason(str, Enum):
    """Why this workflow requires human approval."""
    HIGH_VALUE_OFFER = "high_value_offer"
    VIP_CUSTOMER = "vip_customer"
    ANOMALY_DETECTED = "anomaly_detected"
    REGULATORY_FLAG = "regulatory_flag"
    MANUAL_OVERRIDE = "manual_override"
    FRAUD_RISK = "fraud_risk"
    FIRST_TIME_SCENARIO = "first_time_scenario"


@dataclass
class ApprovalRequest:
    """
    A request for human approval.

    Contains all information needed to:
    1. Display approval UI to human
    2. Resume workflow after approval
    """
    # Identity
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Context
    pnr: str = ""
    customer_name: str = ""
    customer_tier: str = ""

    # What needs approval
    action_type: str = ""  # e.g., "offer_delivery", "high_value_upgrade"
    action_description: str = ""
    reason: EscalationReason = EscalationReason.HIGH_VALUE_OFFER
    reason_details: str = ""

    # The proposed action
    proposed_offer: Dict[str, Any] = field(default_factory=dict)
    offer_value: float = 0.0

    # Risk assessment
    risk_score: float = 0.0
    risk_factors: List[str] = field(default_factory=list)

    # Workflow state (serialized for resume)
    workflow_state: Dict[str, Any] = field(default_factory=dict)
    checkpoint_name: str = ""  # e.g., "pre_delivery", "post_orchestration"

    # Status tracking
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    expires_at: str = field(default_factory=lambda: (datetime.now() + timedelta(hours=24)).isoformat())

    # Resolution
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None
    resolution_notes: Optional[str] = None

    # Notification tracking
    notifications_sent: List[Dict[str, Any]] = field(default_factory=list)

    def is_expired(self) -> bool:
        """Check if this approval request has expired."""
        return datetime.now() > datetime.fromisoformat(self.expires_at)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data["status"] = self.status.value
        data["reason"] = self.reason.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ApprovalRequest":
        """Create from dictionary."""
        data = data.copy()
        data["status"] = ApprovalStatus(data.get("status", "pending"))
        data["reason"] = EscalationReason(data.get("reason", "high_value_offer"))
        return cls(**data)


@dataclass
class ApprovalDecision:
    """The human's decision on an approval request."""
    request_id: str
    approved: bool
    decided_by: str  # User ID or email
    decided_at: str = field(default_factory=lambda: datetime.now().isoformat())
    notes: Optional[str] = None
    modified_offer: Optional[Dict[str, Any]] = None  # Human can modify the offer


# =============================================================================
# State Persistence
# =============================================================================

class StateStore:
    """
    Persists workflow state for deferred execution.

    In production, this would use Redis or a database.
    For demo, uses in-memory storage.
    """

    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._memory_store: Dict[str, Dict[str, Any]] = {}
        self._ttl_seconds = 86400  # 24 hours

    def save_state(self, key: str, state: Dict[str, Any]) -> bool:
        """Save workflow state."""
        try:
            serialized = json.dumps(state, default=str)

            if self._redis:
                self._redis.setex(f"hitl:state:{key}", self._ttl_seconds, serialized)
            else:
                self._memory_store[key] = {
                    "data": state,
                    "saved_at": datetime.now().isoformat(),
                    "expires_at": (datetime.now() + timedelta(seconds=self._ttl_seconds)).isoformat()
                }

            logger.info("hitl_state_saved", key=key, state_size=len(serialized))
            return True

        except Exception as e:
            logger.error("hitl_state_save_failed", key=key, error=str(e))
            return False

    def load_state(self, key: str) -> Optional[Dict[str, Any]]:
        """Load workflow state."""
        try:
            if self._redis:
                serialized = self._redis.get(f"hitl:state:{key}")
                if serialized:
                    return json.loads(serialized)
            else:
                if key in self._memory_store:
                    entry = self._memory_store[key]
                    # Check expiration
                    if datetime.now() < datetime.fromisoformat(entry["expires_at"]):
                        return entry["data"]
                    else:
                        del self._memory_store[key]

            return None

        except Exception as e:
            logger.error("hitl_state_load_failed", key=key, error=str(e))
            return None

    def delete_state(self, key: str) -> bool:
        """Delete workflow state after completion."""
        try:
            if self._redis:
                self._redis.delete(f"hitl:state:{key}")
            else:
                self._memory_store.pop(key, None)
            return True
        except Exception as e:
            logger.error("hitl_state_delete_failed", key=key, error=str(e))
            return False


class ApprovalStore:
    """
    Manages pending approval requests.

    In production, this would use a database for durability.
    """

    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._memory_store: Dict[str, ApprovalRequest] = {}

    def save(self, request: ApprovalRequest) -> bool:
        """Save an approval request."""
        try:
            if self._redis:
                self._redis.hset(
                    "hitl:approvals",
                    request.id,
                    json.dumps(request.to_dict(), default=str)
                )
            else:
                self._memory_store[request.id] = request

            logger.info(
                "hitl_approval_saved",
                request_id=request.id,
                pnr=request.pnr,
                reason=request.reason.value
            )
            return True

        except Exception as e:
            logger.error("hitl_approval_save_failed", request_id=request.id, error=str(e))
            return False

    def get(self, request_id: str) -> Optional[ApprovalRequest]:
        """Get an approval request by ID."""
        try:
            if self._redis:
                data = self._redis.hget("hitl:approvals", request_id)
                if data:
                    return ApprovalRequest.from_dict(json.loads(data))
            else:
                return self._memory_store.get(request_id)

            return None

        except Exception as e:
            logger.error("hitl_approval_get_failed", request_id=request_id, error=str(e))
            return None

    def get_pending(self) -> List[ApprovalRequest]:
        """Get all pending approval requests."""
        pending = []

        try:
            if self._redis:
                all_approvals = self._redis.hgetall("hitl:approvals")
                for data in all_approvals.values():
                    request = ApprovalRequest.from_dict(json.loads(data))
                    if request.status == ApprovalStatus.PENDING and not request.is_expired():
                        pending.append(request)
            else:
                for request in self._memory_store.values():
                    if request.status == ApprovalStatus.PENDING and not request.is_expired():
                        pending.append(request)

            # Sort by created_at (oldest first)
            pending.sort(key=lambda r: r.created_at)

        except Exception as e:
            logger.error("hitl_get_pending_failed", error=str(e))

        return pending

    def get_by_pnr(self, pnr: str) -> List[ApprovalRequest]:
        """Get all approval requests for a PNR."""
        results = []

        try:
            if self._redis:
                all_approvals = self._redis.hgetall("hitl:approvals")
                for data in all_approvals.values():
                    request = ApprovalRequest.from_dict(json.loads(data))
                    if request.pnr == pnr:
                        results.append(request)
            else:
                for request in self._memory_store.values():
                    if request.pnr == pnr:
                        results.append(request)

        except Exception as e:
            logger.error("hitl_get_by_pnr_failed", pnr=pnr, error=str(e))

        return results

    def update(self, request: ApprovalRequest) -> bool:
        """Update an approval request."""
        return self.save(request)


# =============================================================================
# Notification Service
# =============================================================================

class NotificationService:
    """
    Sends notifications for approval requests.

    Supports:
    - Slack webhooks
    - Email (placeholder)
    - Custom webhooks
    """

    def __init__(
        self,
        slack_webhook: Optional[str] = None,
        email_config: Optional[Dict[str, Any]] = None,
        approval_ui_base_url: Optional[str] = None,
    ):
        self.slack_webhook = slack_webhook or os.environ.get("HITL_SLACK_WEBHOOK")
        self.email_config = email_config
        self.approval_ui_base_url = approval_ui_base_url or os.environ.get(
            "HITL_APPROVAL_UI_URL", "http://localhost:5173/approvals"
        )

    def notify(self, request: ApprovalRequest) -> Dict[str, Any]:
        """Send notifications for an approval request."""
        results = {
            "slack": None,
            "email": None,
        }

        if self.slack_webhook:
            results["slack"] = self._send_slack(request)

        if self.email_config:
            results["email"] = self._send_email(request)

        return results

    def _send_slack(self, request: ApprovalRequest) -> Dict[str, Any]:
        """Send Slack notification with approval buttons."""
        try:
            # Build approval URL
            approve_url = f"{self.approval_ui_base_url}/{request.id}"

            # Emoji based on reason
            emoji_map = {
                EscalationReason.HIGH_VALUE_OFFER: ":moneybag:",
                EscalationReason.VIP_CUSTOMER: ":crown:",
                EscalationReason.ANOMALY_DETECTED: ":warning:",
                EscalationReason.REGULATORY_FLAG: ":scales:",
                EscalationReason.FRAUD_RISK: ":rotating_light:",
            }
            emoji = emoji_map.get(request.reason, ":question:")

            # Build message
            message = {
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"{emoji} Approval Required: {request.action_type}",
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {"type": "mrkdwn", "text": f"*PNR:*\n{request.pnr}"},
                            {"type": "mrkdwn", "text": f"*Customer:*\n{request.customer_name}"},
                            {"type": "mrkdwn", "text": f"*Tier:*\n{request.customer_tier}"},
                            {"type": "mrkdwn", "text": f"*Offer Value:*\n${request.offer_value:.2f}"},
                        ]
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Reason:* {request.reason.value}\n{request.reason_details}"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Proposed Offer:*\n```{json.dumps(request.proposed_offer, indent=2)}```"
                        }
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "Approve"},
                                "style": "primary",
                                "url": f"{approve_url}?action=approve"
                            },
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "Deny"},
                                "style": "danger",
                                "url": f"{approve_url}?action=deny"
                            },
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "View Details"},
                                "url": approve_url
                            }
                        ]
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"Request ID: `{request.id}` | Expires: {request.expires_at}"
                            }
                        ]
                    }
                ]
            }

            response = requests.post(
                self.slack_webhook,
                json=message,
                timeout=10
            )

            success = response.status_code == 200

            logger.info(
                "hitl_slack_notification",
                request_id=request.id,
                success=success,
                status_code=response.status_code
            )

            return {"sent": success, "status_code": response.status_code}

        except Exception as e:
            logger.error("hitl_slack_notification_failed", request_id=request.id, error=str(e))
            return {"sent": False, "error": str(e)}

    def _send_email(self, request: ApprovalRequest) -> Dict[str, Any]:
        """Send email notification (placeholder)."""
        # In production, integrate with SendGrid, SES, etc.
        logger.info("hitl_email_notification_placeholder", request_id=request.id)
        return {"sent": False, "reason": "not_implemented"}


# =============================================================================
# Escalation Rules
# =============================================================================

class EscalationRules:
    """
    Defines rules for when to escalate to human approval.

    Decision logic is in backend code, NOT in LLM prompts.
    """

    def __init__(
        self,
        high_value_threshold: float = 500.0,
        vip_tiers: List[str] = None,
        anomaly_threshold: float = 0.8,
        regulatory_routes: List[str] = None,
    ):
        self.high_value_threshold = high_value_threshold
        self.vip_tiers = vip_tiers or ["ConciergeKey", "Executive Platinum"]
        self.anomaly_threshold = anomaly_threshold
        self.regulatory_routes = regulatory_routes or ["EU", "UK", "GDPR"]

    def check(
        self,
        offer_value: float,
        customer_tier: str,
        destination: str = "",
        anomaly_score: float = 0.0,
        is_first_time: bool = False,
        manual_flag: bool = False,
    ) -> Tuple[bool, Optional[EscalationReason], str]:
        """
        Check if this action requires human approval.

        Returns: (needs_approval, reason, details)
        """
        # Manual override always escalates
        if manual_flag:
            return True, EscalationReason.MANUAL_OVERRIDE, "Manually flagged for review"

        # High-value offers
        if offer_value > self.high_value_threshold:
            return (
                True,
                EscalationReason.HIGH_VALUE_OFFER,
                f"Offer value ${offer_value:.2f} exceeds ${self.high_value_threshold} threshold"
            )

        # VIP customers
        if customer_tier in self.vip_tiers:
            return (
                True,
                EscalationReason.VIP_CUSTOMER,
                f"Customer is {customer_tier} - requires approval for any offer"
            )

        # Anomaly detection
        if anomaly_score > self.anomaly_threshold:
            return (
                True,
                EscalationReason.ANOMALY_DETECTED,
                f"Anomaly score {anomaly_score:.2f} exceeds {self.anomaly_threshold} threshold"
            )

        # Regulatory routes
        for route in self.regulatory_routes:
            if route.lower() in destination.lower():
                return (
                    True,
                    EscalationReason.REGULATORY_FLAG,
                    f"Destination '{destination}' matches regulatory route '{route}'"
                )

        # First-time scenarios (optional)
        if is_first_time:
            return (
                True,
                EscalationReason.FIRST_TIME_SCENARIO,
                "First time this scenario has been encountered"
            )

        # No escalation needed
        return False, None, ""


# =============================================================================
# Human-in-the-Loop Manager
# =============================================================================

class HumanInTheLoopManager:
    """
    Main interface for Human-in-the-Loop functionality.

    Usage:
        hitl = HumanInTheLoopManager()

        # Check if approval needed
        needs_approval, reason, details = hitl.check_escalation(...)

        if needs_approval:
            # Create approval request and halt
            request = hitl.create_approval_request(...)
            hitl.save_workflow_state(request.id, current_state)
            hitl.notify(request)
            return {"status": "pending_approval", "request_id": request.id}

        # Later, when approved:
        decision = hitl.get_decision(request_id)
        if decision and decision.approved:
            state = hitl.load_workflow_state(request_id)
            # Resume workflow with state
    """

    def __init__(
        self,
        redis_client=None,
        slack_webhook: Optional[str] = None,
        approval_ui_url: Optional[str] = None,
        escalation_rules: Optional[EscalationRules] = None,
    ):
        self.state_store = StateStore(redis_client)
        self.approval_store = ApprovalStore(redis_client)
        self.notification_service = NotificationService(
            slack_webhook=slack_webhook,
            approval_ui_base_url=approval_ui_url,
        )
        self.escalation_rules = escalation_rules or EscalationRules()

        logger.info("hitl_manager_initialized")

    def check_escalation(
        self,
        offer_value: float,
        customer_tier: str,
        destination: str = "",
        anomaly_score: float = 0.0,
        is_first_time: bool = False,
        manual_flag: bool = False,
    ) -> Tuple[bool, Optional[EscalationReason], str]:
        """Check if this action requires human approval."""
        return self.escalation_rules.check(
            offer_value=offer_value,
            customer_tier=customer_tier,
            destination=destination,
            anomaly_score=anomaly_score,
            is_first_time=is_first_time,
            manual_flag=manual_flag,
        )

    def create_approval_request(
        self,
        pnr: str,
        customer_name: str,
        customer_tier: str,
        action_type: str,
        action_description: str,
        reason: EscalationReason,
        reason_details: str,
        proposed_offer: Dict[str, Any],
        offer_value: float,
        workflow_state: Dict[str, Any],
        checkpoint_name: str = "pre_delivery",
        risk_score: float = 0.0,
        risk_factors: List[str] = None,
        expires_in_hours: int = 24,
    ) -> ApprovalRequest:
        """Create a new approval request."""
        request = ApprovalRequest(
            pnr=pnr,
            customer_name=customer_name,
            customer_tier=customer_tier,
            action_type=action_type,
            action_description=action_description,
            reason=reason,
            reason_details=reason_details,
            proposed_offer=proposed_offer,
            offer_value=offer_value,
            workflow_state=workflow_state,
            checkpoint_name=checkpoint_name,
            risk_score=risk_score,
            risk_factors=risk_factors or [],
            expires_at=(datetime.now() + timedelta(hours=expires_in_hours)).isoformat(),
        )

        # Save request
        self.approval_store.save(request)

        # Save workflow state
        self.state_store.save_state(request.id, workflow_state)

        logger.info(
            "hitl_approval_request_created",
            request_id=request.id,
            pnr=pnr,
            reason=reason.value,
            offer_value=offer_value,
        )

        return request

    def notify(self, request: ApprovalRequest) -> Dict[str, Any]:
        """Send notifications for an approval request."""
        results = self.notification_service.notify(request)

        # Track notifications sent
        request.notifications_sent.append({
            "sent_at": datetime.now().isoformat(),
            "results": results,
        })
        self.approval_store.update(request)

        return results

    def approve(
        self,
        request_id: str,
        decided_by: str,
        notes: Optional[str] = None,
        modified_offer: Optional[Dict[str, Any]] = None,
    ) -> Optional[ApprovalRequest]:
        """Approve an approval request."""
        request = self.approval_store.get(request_id)

        if not request:
            logger.warning("hitl_approve_not_found", request_id=request_id)
            return None

        if request.status != ApprovalStatus.PENDING:
            logger.warning(
                "hitl_approve_invalid_status",
                request_id=request_id,
                current_status=request.status.value
            )
            return None

        if request.is_expired():
            request.status = ApprovalStatus.EXPIRED
            self.approval_store.update(request)
            logger.warning("hitl_approve_expired", request_id=request_id)
            return None

        # Update request
        request.status = ApprovalStatus.APPROVED
        request.resolved_at = datetime.now().isoformat()
        request.resolved_by = decided_by
        request.resolution_notes = notes

        if modified_offer:
            request.proposed_offer = modified_offer

        self.approval_store.update(request)

        logger.info(
            "hitl_request_approved",
            request_id=request_id,
            decided_by=decided_by,
            pnr=request.pnr,
        )

        return request

    def deny(
        self,
        request_id: str,
        decided_by: str,
        notes: Optional[str] = None,
    ) -> Optional[ApprovalRequest]:
        """Deny an approval request."""
        request = self.approval_store.get(request_id)

        if not request:
            logger.warning("hitl_deny_not_found", request_id=request_id)
            return None

        if request.status != ApprovalStatus.PENDING:
            logger.warning(
                "hitl_deny_invalid_status",
                request_id=request_id,
                current_status=request.status.value
            )
            return None

        # Update request
        request.status = ApprovalStatus.DENIED
        request.resolved_at = datetime.now().isoformat()
        request.resolved_by = decided_by
        request.resolution_notes = notes

        self.approval_store.update(request)

        # Clean up workflow state
        self.state_store.delete_state(request_id)

        logger.info(
            "hitl_request_denied",
            request_id=request_id,
            decided_by=decided_by,
            pnr=request.pnr,
        )

        return request

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """Get an approval request by ID."""
        return self.approval_store.get(request_id)

    def get_pending_requests(self) -> List[ApprovalRequest]:
        """Get all pending approval requests."""
        return self.approval_store.get_pending()

    def get_requests_by_pnr(self, pnr: str) -> List[ApprovalRequest]:
        """Get all approval requests for a PNR."""
        return self.approval_store.get_by_pnr(pnr)

    def load_workflow_state(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Load saved workflow state for resuming."""
        return self.state_store.load_state(request_id)

    def cleanup_completed(self, request_id: str) -> bool:
        """Clean up state after workflow completion."""
        return self.state_store.delete_state(request_id)

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about approval requests."""
        all_requests = []

        if self.approval_store._redis:
            all_data = self.approval_store._redis.hgetall("hitl:approvals")
            for data in all_data.values():
                all_requests.append(ApprovalRequest.from_dict(json.loads(data)))
        else:
            all_requests = list(self.approval_store._memory_store.values())

        stats = {
            "total": len(all_requests),
            "pending": sum(1 for r in all_requests if r.status == ApprovalStatus.PENDING),
            "approved": sum(1 for r in all_requests if r.status == ApprovalStatus.APPROVED),
            "denied": sum(1 for r in all_requests if r.status == ApprovalStatus.DENIED),
            "expired": sum(1 for r in all_requests if r.status == ApprovalStatus.EXPIRED),
            "by_reason": {},
        }

        for request in all_requests:
            reason = request.reason.value
            stats["by_reason"][reason] = stats["by_reason"].get(reason, 0) + 1

        return stats


# =============================================================================
# Singleton Access
# =============================================================================

_hitl_manager: Optional[HumanInTheLoopManager] = None


def get_hitl_manager() -> HumanInTheLoopManager:
    """Get the singleton HITL manager instance."""
    global _hitl_manager
    if _hitl_manager is None:
        _hitl_manager = HumanInTheLoopManager()
    return _hitl_manager


def create_hitl_manager(
    redis_client=None,
    slack_webhook: Optional[str] = None,
    approval_ui_url: Optional[str] = None,
    escalation_rules: Optional[EscalationRules] = None,
) -> HumanInTheLoopManager:
    """Create a new HITL manager instance."""
    global _hitl_manager
    _hitl_manager = HumanInTheLoopManager(
        redis_client=redis_client,
        slack_webhook=slack_webhook,
        approval_ui_url=approval_ui_url,
        escalation_rules=escalation_rules,
    )
    return _hitl_manager
