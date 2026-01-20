"""
Infrastructure Module for Tailored Offers Demo

Provides production-grade observability, retry logic, and validation:
- Structured logging with structlog
- Prometheus metrics collection
- LangSmith/LangFuse tracing
- Retry logic with tenacity
- LLM semantic validation
- Agent memory (short-term, long-term, episodic)
- Planner-Executor pattern (batch and incremental)
- Feedback loops for continuous improvement

Planner-Executor Patterns:
- Batch (Legacy): Plans all steps upfront, executes all, revises on failure
- Incremental (Recommended): Plans ONE step at a time, observes result, re-plans
"""

from .logging import get_logger, configure_logging
from .metrics import (
    MetricsCollector,
    agent_duration,
    agent_requests,
    llm_calls,
    llm_latency,
    llm_tokens,
)
from .retry import (
    retry_llm_call,
    retry_mcp_call,
    retry_with_fallback,
    RetryConfig,
)
from .tracing import (
    TracingManager,
    trace_agent,
    trace_llm_call,
    get_tracer,
)
from .validation import (
    LLMResponseValidator,
    ValidationResult,
    validate_offer_decision,
    validate_personalization_response,
)
from .memory import (
    AgentMemory,
    ConversationMemory,
    CustomerMemory,
    OfferMemory,
    LearningMemory,
    get_memory,
)
from .planner_executor import (
    # Data structures
    Plan,
    PlanStep,
    PlanStatus,
    StepStatus,
    ExecutionResult,
    WorkerResult,
    WorkerRecommendation,
    # Batch planner-executor (legacy)
    OfferPlanner,
    OfferExecutor,
    PlannerExecutorCoordinator,
    create_offer_plan,
    execute_offer_plan,
    run_offer_evaluation_with_planning,
    # Incremental planner-executor (recommended)
    IncrementalState,
    IncrementalOfferPlanner,
    IncrementalOfferExecutor,
    IncrementalPlannerExecutorCoordinator,
    run_offer_evaluation_incremental,
)
from .feedback import (
    FeedbackManager,
    FeedbackStore,
    OfferOutcome,
    OutcomeType,
    FeedbackStatus,
    CalibrationReport,
    CalibrationBucket,
    AgentFeedback,
    get_feedback_manager,
    record_offer_outcome,
    get_calibration_report,
)
from .guardrails import (
    # Guardrail types
    GuardrailVerdict,
    GuardrailResult,
    LayerResult,
    # Layer 1: Synchronous Pre-flight
    SyncGuardrails,
    # Layer 2: Asynchronous Background
    AsyncGuardrails,
    AsyncGuardrailTask,
    # Layer 3: Triggered Escalation
    TriggeredGuardrails,
    # Coordinator
    GuardrailCoordinator,
    create_guardrail_coordinator,
)
from .production_safety import (
    # Idempotency
    IdempotencyManager,
    IdempotencyStatus,
    IdempotencyRecord,
    # Cost Tracking
    CostTracker,
    LLMCallCost,
    # Alerting
    AlertManager,
    AlertSeverity,
    Alert,
    # Coordinator
    ProductionSafetyCoordinator,
    get_safety_coordinator,
    create_safety_coordinator,
)
from .human_in_loop import (
    # Data Models
    ApprovalStatus,
    ApprovalRequest,
    ApprovalDecision,
    EscalationReason,
    # State Management
    StateStore,
    ApprovalStore,
    # Notifications
    NotificationService,
    # Rules
    EscalationRules,
    # Manager
    HumanInTheLoopManager,
    get_hitl_manager,
    create_hitl_manager,
)

__all__ = [
    # Logging
    "get_logger",
    "configure_logging",
    # Metrics
    "MetricsCollector",
    "agent_duration",
    "agent_requests",
    "llm_calls",
    "llm_latency",
    "llm_tokens",
    # Retry
    "retry_llm_call",
    "retry_mcp_call",
    "retry_with_fallback",
    "RetryConfig",
    # Tracing
    "TracingManager",
    "trace_agent",
    "trace_llm_call",
    "get_tracer",
    # Validation
    "LLMResponseValidator",
    "ValidationResult",
    "validate_offer_decision",
    "validate_personalization_response",
    # Memory
    "AgentMemory",
    "ConversationMemory",
    "CustomerMemory",
    "OfferMemory",
    "LearningMemory",
    "get_memory",
    # Planner-Executor (Data Structures)
    "Plan",
    "PlanStep",
    "PlanStatus",
    "StepStatus",
    "ExecutionResult",
    "WorkerResult",
    "WorkerRecommendation",
    # Planner-Executor (Batch - Legacy)
    "OfferPlanner",
    "OfferExecutor",
    "PlannerExecutorCoordinator",
    "create_offer_plan",
    "execute_offer_plan",
    "run_offer_evaluation_with_planning",
    # Planner-Executor (Incremental - Recommended)
    "IncrementalState",
    "IncrementalOfferPlanner",
    "IncrementalOfferExecutor",
    "IncrementalPlannerExecutorCoordinator",
    "run_offer_evaluation_incremental",
    # Feedback Loop
    "FeedbackManager",
    "FeedbackStore",
    "OfferOutcome",
    "OutcomeType",
    "FeedbackStatus",
    "CalibrationReport",
    "CalibrationBucket",
    "AgentFeedback",
    "get_feedback_manager",
    "record_offer_outcome",
    "get_calibration_report",
    # Guardrails (3-Layer Architecture)
    "GuardrailVerdict",
    "GuardrailResult",
    "LayerResult",
    "SyncGuardrails",
    "AsyncGuardrails",
    "AsyncGuardrailTask",
    "TriggeredGuardrails",
    "GuardrailCoordinator",
    "create_guardrail_coordinator",
    # Production Safety (Critical for Production)
    "IdempotencyManager",
    "IdempotencyStatus",
    "IdempotencyRecord",
    "CostTracker",
    "LLMCallCost",
    "AlertManager",
    "AlertSeverity",
    "Alert",
    "ProductionSafetyCoordinator",
    "get_safety_coordinator",
    "create_safety_coordinator",
    # Human-in-the-Loop (HITL)
    "ApprovalStatus",
    "ApprovalRequest",
    "ApprovalDecision",
    "EscalationReason",
    "StateStore",
    "ApprovalStore",
    "NotificationService",
    "EscalationRules",
    "HumanInTheLoopManager",
    "get_hitl_manager",
    "create_hitl_manager",
]
