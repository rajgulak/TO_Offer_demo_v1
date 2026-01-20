"""
Planner-Executor Pattern Module

Implements TWO variants of the Planner-Executor agentic pattern:

## 1. Batch Planner-Executor (Legacy)
Plans all steps upfront, executes all, revises on failure.
- Use for: Simple, predictable workflows where steps are well-defined

## 2. Incremental Planner-Executor (Recommended) ✅
Plans ONE step at a time, executes, observes result, re-plans.
- Use for: Complex workflows where later steps depend on earlier results
- Follows best practice: "Plan next action, wait for result, re-plan based on state"

Pattern Benefits:
- Separation of strategic planning from tactical execution
- Ability to re-plan when execution encounters issues
- Better explainability (plan is visible and auditable)
- Support for human-in-the-loop at planning stage
- Workers return recommendations for failure recovery
- Dynamic task simplification on repeated failures

Usage (Incremental - Recommended):
    coordinator = IncrementalPlannerExecutorCoordinator()
    result = coordinator.run({"pnr_locator": "ABC123"})

Usage (Batch - Legacy):
    planner = OfferPlanner()
    executor = OfferExecutor()
    plan = planner.create_plan(context)
    result = executor.execute(plan)
"""

import os
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod

from .logging import get_logger
from .metrics import metrics
from .memory import get_memory

logger = get_logger("planner_executor")

# Lazy import feedback to avoid circular dependency
def _get_feedback_manager():
    from .feedback import get_feedback_manager
    return get_feedback_manager()


# =============================================================================
# PLAN DATA STRUCTURES
# =============================================================================

class PlanStatus(Enum):
    """Status of a plan."""
    DRAFT = "draft"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    REVISED = "revised"


class StepStatus(Enum):
    """Status of a plan step."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkerRecommendation(Enum):
    """
    Recommendations that workers can return to guide the planner.

    This is the KEY addition for proper planner-worker communication.
    Workers don't just fail - they suggest what to do next.
    """
    CONTINUE = "continue"              # Success, proceed normally
    RETRY = "retry"                    # Transient failure, retry same step
    RETRY_WITH_BACKOFF = "retry_with_backoff"  # Rate limited, wait then retry
    USE_BACKUP = "use_backup"          # Primary failed, try backup approach
    SIMPLIFY = "simplify"              # Too complex, simplify the task
    SKIP = "skip"                      # Non-critical, skip this step
    ABORT = "abort"                    # Unrecoverable, stop execution
    ESCALATE = "escalate"              # Need human intervention


@dataclass
class WorkerResult:
    """
    Rich result from a worker execution.

    Unlike simple success/failure, this includes:
    - status: Did it work?
    - data: What was produced?
    - error: What went wrong (if anything)?
    - recommendation: What should the planner do next?
    - metadata: Additional context for the planner

    This enables intelligent failure recovery instead of blind retries.
    """
    status: str  # "success" or "failure"
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    error_type: Optional[str] = None  # "timeout", "rate_limit", "validation", "api_error", etc.
    recommendation: WorkerRecommendation = WorkerRecommendation.CONTINUE
    backup_suggestion: Optional[str] = None  # e.g., "use_cached_data", "try_alternate_api"
    retry_after_seconds: Optional[float] = None  # For rate limits
    simplification_hint: Optional[str] = None  # e.g., "skip_personalization"
    confidence: float = 1.0  # How confident is the worker in this result?
    duration_ms: Optional[float] = None

    @property
    def success(self) -> bool:
        return self.status == "success"

    @property
    def should_retry(self) -> bool:
        return self.recommendation in [
            WorkerRecommendation.RETRY,
            WorkerRecommendation.RETRY_WITH_BACKOFF,
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "data": self.data,
            "error": self.error,
            "error_type": self.error_type,
            "recommendation": self.recommendation.value,
            "backup_suggestion": self.backup_suggestion,
            "retry_after_seconds": self.retry_after_seconds,
            "simplification_hint": self.simplification_hint,
            "confidence": self.confidence,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def success_result(cls, data: Dict[str, Any], confidence: float = 1.0) -> "WorkerResult":
        """Create a successful result."""
        return cls(
            status="success",
            data=data,
            recommendation=WorkerRecommendation.CONTINUE,
            confidence=confidence,
        )

    @classmethod
    def failure_result(
        cls,
        error: str,
        error_type: str = "unknown",
        recommendation: WorkerRecommendation = WorkerRecommendation.ABORT,
        **kwargs,
    ) -> "WorkerResult":
        """Create a failure result with recommendation."""
        return cls(
            status="failure",
            error=error,
            error_type=error_type,
            recommendation=recommendation,
            **kwargs,
        )


@dataclass
class PlanStep:
    """A single step in a plan."""
    step_id: str
    action: str
    description: str
    agent: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def duration_ms(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() * 1000
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "action": self.action,
            "description": self.description,
            "agent": self.agent,
            "parameters": self.parameters,
            "dependencies": self.dependencies,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


@dataclass
class Plan:
    """A complete execution plan."""
    plan_id: str
    goal: str
    context: Dict[str, Any]
    steps: List[PlanStep]
    status: PlanStatus = PlanStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.now)
    reasoning: str = ""
    confidence: float = 0.0
    revision_history: List[Dict[str, Any]] = field(default_factory=list)

    def get_next_step(self) -> Optional[PlanStep]:
        """Get the next step to execute."""
        for step in self.steps:
            if step.status == StepStatus.PENDING:
                # Check dependencies
                deps_satisfied = all(
                    self.get_step(dep_id).status == StepStatus.COMPLETED
                    for dep_id in step.dependencies
                )
                if deps_satisfied:
                    return step
        return None

    def get_step(self, step_id: str) -> Optional[PlanStep]:
        """Get a step by ID."""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def is_complete(self) -> bool:
        """Check if all steps are completed."""
        return all(
            step.status in [StepStatus.COMPLETED, StepStatus.SKIPPED]
            for step in self.steps
        )

    def has_failed(self) -> bool:
        """Check if any step has failed."""
        return any(step.status == StepStatus.FAILED for step in self.steps)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "goal": self.goal,
            "status": self.status.value,
            "steps": [s.to_dict() for s in self.steps],
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ExecutionResult:
    """Result of plan execution."""
    plan_id: str
    success: bool
    final_result: Optional[Dict[str, Any]]
    steps_completed: int
    steps_failed: int
    total_duration_ms: float
    feedback: str = ""
    needs_replanning: bool = False


# =============================================================================
# PLANNER INTERFACE
# =============================================================================

class BasePlanner(ABC):
    """Abstract base class for planners."""

    @abstractmethod
    def create_plan(self, context: Dict[str, Any]) -> Plan:
        """Create an execution plan for the given context."""
        pass

    @abstractmethod
    def revise_plan(self, plan: Plan, feedback: str) -> Plan:
        """Revise a plan based on execution feedback."""
        pass

    def validate_plan(self, plan: Plan) -> List[str]:
        """Validate a plan and return any issues."""
        issues = []

        if not plan.steps:
            issues.append("Plan has no steps")

        # Check for circular dependencies
        for step in plan.steps:
            if step.step_id in step.dependencies:
                issues.append(f"Step {step.step_id} has circular dependency on itself")

        # Check that all dependencies exist
        step_ids = {s.step_id for s in plan.steps}
        for step in plan.steps:
            for dep in step.dependencies:
                if dep not in step_ids:
                    issues.append(f"Step {step.step_id} depends on non-existent step {dep}")

        return issues


# =============================================================================
# EXECUTOR INTERFACE
# =============================================================================

class BaseExecutor(ABC):
    """Abstract base class for executors."""

    @abstractmethod
    def execute_step(self, step: PlanStep, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single step."""
        pass

    def execute(self, plan: Plan) -> ExecutionResult:
        """Execute a complete plan."""
        start_time = datetime.now()
        plan.status = PlanStatus.EXECUTING

        logger.info(
            "plan_execution_started",
            plan_id=plan.plan_id,
            total_steps=len(plan.steps),
        )

        context = plan.context.copy()
        steps_completed = 0
        steps_failed = 0

        while True:
            step = plan.get_next_step()
            if step is None:
                break

            step.status = StepStatus.IN_PROGRESS
            step.started_at = datetime.now()

            logger.info(
                "step_execution_started",
                plan_id=plan.plan_id,
                step_id=step.step_id,
                action=step.action,
            )

            try:
                # Execute the step
                result = self.execute_step(step, context)
                step.result = result
                step.status = StepStatus.COMPLETED
                step.completed_at = datetime.now()
                steps_completed += 1

                # Update context with result
                context[f"step_{step.step_id}_result"] = result

                logger.info(
                    "step_execution_completed",
                    plan_id=plan.plan_id,
                    step_id=step.step_id,
                    duration_ms=step.duration_ms,
                )

            except Exception as e:
                step.status = StepStatus.FAILED
                step.error = str(e)
                step.completed_at = datetime.now()
                steps_failed += 1

                logger.error(
                    "step_execution_failed",
                    plan_id=plan.plan_id,
                    step_id=step.step_id,
                    error=str(e),
                )

                # Decide whether to continue or abort
                if not self._should_continue_after_failure(step, plan):
                    break

        # Determine final status
        total_duration = (datetime.now() - start_time).total_seconds() * 1000

        if plan.is_complete():
            plan.status = PlanStatus.COMPLETED
            success = True
            feedback = "Plan executed successfully"
        elif plan.has_failed():
            plan.status = PlanStatus.FAILED
            success = False
            feedback = f"Plan failed at step: {[s.step_id for s in plan.steps if s.status == StepStatus.FAILED]}"
        else:
            success = False
            feedback = "Plan execution incomplete"

        # Record metrics
        metrics.record_pipeline_completion(success, total_duration / 1000)

        return ExecutionResult(
            plan_id=plan.plan_id,
            success=success,
            final_result=self._collect_final_result(plan),
            steps_completed=steps_completed,
            steps_failed=steps_failed,
            total_duration_ms=total_duration,
            feedback=feedback,
            needs_replanning=steps_failed > 0,
        )

    def _should_continue_after_failure(self, failed_step: PlanStep, plan: Plan) -> bool:
        """Decide whether to continue execution after a step failure."""
        # By default, check if other steps can still execute
        remaining = [s for s in plan.steps if s.status == StepStatus.PENDING]
        for step in remaining:
            if failed_step.step_id not in step.dependencies:
                return True
        return False

    def _collect_final_result(self, plan: Plan) -> Dict[str, Any]:
        """Collect the final result from completed steps."""
        result = {}
        for step in plan.steps:
            if step.status == StepStatus.COMPLETED and step.result:
                result[step.step_id] = step.result
        return result


# =============================================================================
# OFFER PLANNER - DOMAIN SPECIFIC
# =============================================================================

class OfferPlanner(BasePlanner):
    """
    Planner for tailored offer decisions.

    Creates a plan that:
    1. Validates customer eligibility
    2. Analyzes flight inventory
    3. Evaluates offer options
    4. Generates personalized message
    5. Selects optimal channel/timing
    """

    def __init__(self, use_llm: bool = True):
        self.use_llm = use_llm
        self.memory = get_memory()

    def create_plan(self, context: Dict[str, Any]) -> Plan:
        """Create an offer evaluation plan."""
        import uuid

        pnr = context.get("pnr_locator", "unknown")
        customer_id = context.get("customer_id", "unknown")

        # Get memory context for better planning
        memory_context = self.memory.get_context_for_agent(
            session_id=context.get("session_id", pnr),
            customer_id=customer_id,
            agent_name="planner",
        )

        # Create plan steps
        steps = [
            PlanStep(
                step_id="eligibility",
                action="check_eligibility",
                description="Verify customer eligibility and check for suppressions",
                agent="customer_intelligence",
                parameters={"pnr": pnr},
                dependencies=[],
            ),
            PlanStep(
                step_id="inventory",
                action="analyze_inventory",
                description="Check cabin availability and identify upgrade opportunities",
                agent="flight_optimization",
                parameters={"pnr": pnr},
                dependencies=["eligibility"],
            ),
            PlanStep(
                step_id="offer_selection",
                action="select_offer",
                description="Evaluate offer options and select optimal offer based on EV",
                agent="offer_orchestration",
                parameters={"pnr": pnr, "use_llm": self.use_llm},
                dependencies=["inventory"],
            ),
            PlanStep(
                step_id="personalization",
                action="generate_message",
                description="Create personalized offer message for customer",
                agent="personalization",
                parameters={"pnr": pnr},
                dependencies=["offer_selection"],
            ),
            PlanStep(
                step_id="channel_timing",
                action="select_channel",
                description="Determine optimal channel and timing for delivery",
                agent="channel_timing",
                parameters={"pnr": pnr},
                dependencies=["personalization"],
            ),
            PlanStep(
                step_id="tracking",
                action="setup_tracking",
                description="Configure A/B test tracking and measurement",
                agent="measurement_learning",
                parameters={"pnr": pnr},
                dependencies=["channel_timing"],
            ),
        ]

        # Adjust plan based on memory insights
        customer_insights = memory_context.get("customer_insights", {})
        if customer_insights.get("acceptance_rate", 0.5) < 0.3:
            # Customer has low acceptance - add extra analysis step
            steps.insert(2, PlanStep(
                step_id="risk_analysis",
                action="analyze_risk",
                description="Extra analysis for low-acceptance customer",
                agent="offer_orchestration",
                parameters={"pnr": pnr, "mode": "conservative"},
                dependencies=["inventory"],
            ))
            # Update offer_selection to depend on risk_analysis
            for step in steps:
                if step.step_id == "offer_selection":
                    step.dependencies.append("risk_analysis")

        plan = Plan(
            plan_id=f"plan_{pnr}_{uuid.uuid4().hex[:8]}",
            goal=f"Evaluate and deliver optimal offer for PNR {pnr}",
            context=context,
            steps=steps,
            reasoning=self._generate_plan_reasoning(context, memory_context),
            confidence=self._calculate_confidence(context, memory_context),
        )

        logger.info(
            "plan_created",
            plan_id=plan.plan_id,
            pnr=pnr,
            steps=len(steps),
            confidence=plan.confidence,
        )

        return plan

    def revise_plan(self, plan: Plan, feedback: str) -> Plan:
        """Revise a failed plan based on feedback."""
        import uuid

        # Record the revision
        plan.revision_history.append({
            "timestamp": datetime.now().isoformat(),
            "feedback": feedback,
            "previous_status": plan.status.value,
        })

        # Identify failed steps
        failed_steps = [s for s in plan.steps if s.status == StepStatus.FAILED]

        for step in failed_steps:
            # Reset failed step for retry
            step.status = StepStatus.PENDING
            step.error = None
            step.result = None

            # Adjust parameters based on failure
            if "timeout" in (step.error or "").lower():
                # Increase timeout or add retry
                step.parameters["retry_count"] = step.parameters.get("retry_count", 0) + 1

            if "no eligible offers" in feedback.lower():
                # Try with relaxed constraints
                step.parameters["relaxed_constraints"] = True

        plan.status = PlanStatus.REVISED

        logger.info(
            "plan_revised",
            plan_id=plan.plan_id,
            revision_count=len(plan.revision_history),
            feedback=feedback[:100],
        )

        return plan

    def _generate_plan_reasoning(
        self,
        context: Dict[str, Any],
        memory_context: Dict[str, Any],
    ) -> str:
        """Generate reasoning for the plan."""
        reasoning_parts = []

        reasoning_parts.append(f"Planning offer evaluation for PNR: {context.get('pnr_locator')}")

        # Add insights from memory
        customer_insights = memory_context.get("customer_insights", {})
        if customer_insights.get("has_history"):
            acceptance_rate = customer_insights.get("acceptance_rate", 0.5)
            reasoning_parts.append(f"Customer history shows {acceptance_rate:.0%} acceptance rate")

            if customer_insights.get("preferred_channel"):
                reasoning_parts.append(
                    f"Customer prefers {customer_insights['preferred_channel']} channel"
                )

        recommendations = memory_context.get("recommendations", [])
        if recommendations:
            reasoning_parts.append("Recommendations from learning memory:")
            for rec in recommendations[:3]:
                reasoning_parts.append(f"  - {rec}")

        return "\n".join(reasoning_parts)

    def _calculate_confidence(
        self,
        context: Dict[str, Any],
        memory_context: Dict[str, Any],
    ) -> float:
        """
        Calculate confidence score for the plan.

        Uses feedback data to adjust confidence based on historical performance.
        """
        confidence = 0.5  # Base confidence

        # Increase confidence with more customer history
        customer_insights = memory_context.get("customer_insights", {})
        if customer_insights.get("total_interactions", 0) > 5:
            confidence += 0.2

        # Increase confidence with good acceptance rate
        if customer_insights.get("acceptance_rate", 0.5) > 0.5:
            confidence += 0.1

        # Decrease confidence for suppressed customers
        if context.get("suppressed"):
            confidence -= 0.3

        # Adjust confidence based on feedback loop data
        try:
            feedback_manager = _get_feedback_manager()
            agent_feedback = feedback_manager.get_agent_feedback(
                agent_name="offer_orchestration",
                days=30,
            )

            # Apply confidence adjustment from feedback
            if agent_feedback.total_decisions > 10:
                confidence += agent_feedback.confidence_adjustment

                # Log feedback-based adjustment
                if abs(agent_feedback.confidence_adjustment) > 0.05:
                    logger.info(
                        "confidence_adjusted_by_feedback",
                        adjustment=agent_feedback.confidence_adjustment,
                        overconfident=agent_feedback.overconfident,
                        underconfident=agent_feedback.underconfident,
                    )

        except Exception as e:
            # Feedback not available - use base confidence
            logger.debug("feedback_not_available", error=str(e))

        return min(max(confidence, 0.0), 1.0)

    def get_feedback_insights(self) -> Dict[str, Any]:
        """
        Get insights from the feedback loop for planning.

        Returns recommendations and performance data to inform planning.
        """
        try:
            feedback_manager = _get_feedback_manager()

            # Get calibration report
            calibration = feedback_manager.get_calibration_report()

            # Get agent feedback
            agent_feedback = feedback_manager.get_agent_feedback(
                agent_name="offer_orchestration",
                days=30,
            )

            return {
                "calibration": {
                    "total_outcomes": calibration.total_outcomes,
                    "acceptance_rate": calibration.overall_acceptance_rate,
                    "calibration_error": calibration.mean_calibration_error,
                    "value_capture_rate": calibration.value_capture_rate,
                },
                "agent_feedback": {
                    "success_rate": agent_feedback.success_rate,
                    "overconfident": agent_feedback.overconfident,
                    "underconfident": agent_feedback.underconfident,
                    "recommendations": agent_feedback.recommendations[:3],
                },
                "has_sufficient_data": calibration.total_outcomes >= 10,
            }
        except Exception as e:
            logger.debug("feedback_insights_not_available", error=str(e))
            return {
                "calibration": {},
                "agent_feedback": {},
                "has_sufficient_data": False,
            }


class OfferExecutor(BaseExecutor):
    """
    Executor for offer evaluation plans.

    Maps plan steps to agent calls.
    """

    def __init__(self):
        # Import agents
        from agents.customer_intelligence import CustomerIntelligenceAgent
        from agents.flight_optimization import FlightOptimizationAgent
        from agents.offer_orchestration import OfferOrchestrationAgent
        from agents.personalization import PersonalizationAgent
        from agents.channel_timing import ChannelTimingAgent
        from agents.measurement_learning import MeasurementLearningAgent

        self.agents = {
            "customer_intelligence": CustomerIntelligenceAgent(),
            "flight_optimization": FlightOptimizationAgent(),
            "offer_orchestration": OfferOrchestrationAgent(),
            "personalization": PersonalizationAgent(),
            "channel_timing": ChannelTimingAgent(),
            "measurement_learning": MeasurementLearningAgent(),
        }

        self.memory = get_memory()

    def execute_step(self, step: PlanStep, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single plan step by calling the appropriate agent."""
        agent = self.agents.get(step.agent)
        if not agent:
            raise ValueError(f"Unknown agent: {step.agent}")

        # Build state from context
        state = self._build_state(context, step)

        # Execute agent
        result = agent.analyze(state)

        # Record in memory
        customer_id = context.get("customer_id") or state.get("customer_data", {}).get("lylty_acct_id")
        if customer_id:
            self.memory.record_decision(
                session_id=context.get("session_id", context.get("pnr_locator", "unknown")),
                customer_id=customer_id,
                agent_name=step.agent,
                decision=result,
            )

        # Check for step-specific outcomes
        if step.action == "check_eligibility":
            if not result.get("customer_eligible", True):
                # Early termination - mark remaining steps as skipped
                logger.info("eligibility_check_failed", reason=result.get("suppression_reason"))

        return result

    def _build_state(self, context: Dict[str, Any], step: PlanStep) -> Dict[str, Any]:
        """Build agent state from execution context."""
        state = {
            "pnr_locator": context.get("pnr_locator"),
            "customer_data": context.get("customer_data"),
            "flight_data": context.get("flight_data"),
            "reservation_data": context.get("reservation_data"),
            "ml_scores": context.get("ml_scores"),
            "reasoning_trace": context.get("reasoning_trace", []),
        }

        # Add results from previous steps
        for key, value in context.items():
            if key.startswith("step_") and key.endswith("_result"):
                # Merge previous step results into state
                if isinstance(value, dict):
                    state.update(value)

        # Add step-specific parameters
        state.update(step.parameters)

        return state


# =============================================================================
# PLANNER-EXECUTOR COORDINATOR
# =============================================================================

class PlannerExecutorCoordinator:
    """
    Coordinates the planner-executor pattern with feedback loops.

    Features:
    - Automatic re-planning on failure
    - Human-in-the-loop support
    - Memory integration
    """

    def __init__(
        self,
        planner: Optional[BasePlanner] = None,
        executor: Optional[BaseExecutor] = None,
        max_revisions: int = 2,
        require_plan_approval: bool = False,
    ):
        self.planner = planner or OfferPlanner()
        self.executor = executor or OfferExecutor()
        self.max_revisions = max_revisions
        self.require_plan_approval = require_plan_approval
        self.memory = get_memory()

    def run(
        self,
        context: Dict[str, Any],
        plan_approval_callback: Optional[Callable[[Plan], bool]] = None,
    ) -> ExecutionResult:
        """
        Run the full planner-executor cycle.

        Args:
            context: Initial context for planning
            plan_approval_callback: Optional callback for human approval

        Returns:
            Final execution result
        """
        # Create initial plan
        plan = self.planner.create_plan(context)

        # Validate plan
        issues = self.planner.validate_plan(plan)
        if issues:
            logger.warning("plan_validation_issues", issues=issues)

        # Request approval if required
        if self.require_plan_approval:
            if plan_approval_callback:
                approved = plan_approval_callback(plan)
            else:
                approved = True  # Default approve if no callback
                logger.warning("plan_auto_approved", reason="no approval callback")

            if not approved:
                return ExecutionResult(
                    plan_id=plan.plan_id,
                    success=False,
                    final_result=None,
                    steps_completed=0,
                    steps_failed=0,
                    total_duration_ms=0,
                    feedback="Plan rejected during approval",
                )

            plan.status = PlanStatus.APPROVED

        # Execute with retry loop
        revision_count = 0
        while revision_count <= self.max_revisions:
            result = self.executor.execute(plan)

            if result.success:
                logger.info(
                    "plan_execution_success",
                    plan_id=plan.plan_id,
                    revisions=revision_count,
                )
                return result

            if not result.needs_replanning or revision_count >= self.max_revisions:
                logger.warning(
                    "plan_execution_failed",
                    plan_id=plan.plan_id,
                    feedback=result.feedback,
                    revisions=revision_count,
                )
                return result

            # Revise and retry
            plan = self.planner.revise_plan(plan, result.feedback)
            revision_count += 1

            logger.info(
                "plan_revision",
                plan_id=plan.plan_id,
                revision=revision_count,
            )

        return result

    async def run_async(
        self,
        context: Dict[str, Any],
    ) -> ExecutionResult:
        """Async version of run (for API integration)."""
        # For now, delegate to sync version
        # In production, this would use async agents
        import asyncio
        return await asyncio.to_thread(self.run, context)

    def record_outcome(
        self,
        plan_id: str,
        outcome: str,
        customer_feedback: Optional[str] = None,
    ) -> bool:
        """
        Record the outcome of a completed plan.

        This closes the feedback loop by recording whether the offer
        was accepted or rejected.

        Args:
            plan_id: ID of the plan that was executed
            outcome: "accepted", "rejected", "expired"
            customer_feedback: Optional feedback from customer

        Returns:
            True if outcome was recorded successfully
        """
        try:
            from .feedback import get_feedback_manager, OutcomeType

            feedback_manager = get_feedback_manager()

            # Find the plan execution context
            # In a real system, this would look up the plan by ID
            # For now, we log the outcome
            logger.info(
                "plan_outcome_recorded",
                plan_id=plan_id,
                outcome=outcome,
                has_feedback=bool(customer_feedback),
            )

            return True

        except Exception as e:
            logger.error("failed_to_record_outcome", plan_id=plan_id, error=str(e))
            return False

    def get_performance_report(self, days: int = 30) -> Dict[str, Any]:
        """
        Get a performance report for the planner-executor.

        Uses feedback data to analyze how well plans are performing.
        """
        try:
            feedback_manager = _get_feedback_manager()

            # Get summary stats
            stats = feedback_manager.get_summary_stats(days=days)

            # Get calibration report
            calibration = feedback_manager.get_calibration_report(days=days)

            return {
                "period_days": days,
                "summary": stats,
                "calibration": {
                    "overall_acceptance_rate": calibration.overall_acceptance_rate,
                    "mean_calibration_error": calibration.mean_calibration_error,
                    "brier_score": calibration.brier_score,
                    "value_capture_rate": calibration.value_capture_rate,
                },
                "segments": calibration.by_offer_type,
                "recommendations": self._generate_planning_recommendations(calibration),
            }
        except Exception as e:
            logger.warning("performance_report_failed", error=str(e))
            return {
                "period_days": days,
                "error": str(e),
                "recommendations": ["Insufficient data for performance analysis"],
            }

    def _generate_planning_recommendations(self, calibration) -> List[str]:
        """Generate recommendations for improving planning based on feedback."""
        recommendations = []

        if calibration.total_outcomes < 10:
            recommendations.append("Need more outcome data to generate reliable recommendations")
            return recommendations

        # Check calibration
        if calibration.mean_calibration_error > 0.15:
            recommendations.append(
                f"High calibration error ({calibration.mean_calibration_error:.1%}) - "
                "consider adjusting probability estimates"
            )

        # Check value capture
        if calibration.value_capture_rate < 0.7:
            recommendations.append(
                f"Low value capture rate ({calibration.value_capture_rate:.1%}) - "
                "offers may be underperforming vs expectations"
            )
        elif calibration.value_capture_rate > 1.3:
            recommendations.append(
                f"Exceeding expected value ({calibration.value_capture_rate:.1%}) - "
                "probability estimates may be too conservative"
            )

        # Check acceptance rate
        if calibration.overall_acceptance_rate < 0.15:
            recommendations.append(
                "Low overall acceptance rate - review targeting criteria"
            )
        elif calibration.overall_acceptance_rate > 0.5:
            recommendations.append(
                "High acceptance rate - may have room to increase prices"
            )

        if not recommendations:
            recommendations.append("Performance within expected parameters")

        return recommendations


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_offer_plan(pnr_locator: str, **kwargs) -> Plan:
    """Create an offer evaluation plan for a PNR."""
    planner = OfferPlanner()
    context = {"pnr_locator": pnr_locator, **kwargs}
    return planner.create_plan(context)


def execute_offer_plan(plan: Plan) -> ExecutionResult:
    """Execute an offer evaluation plan."""
    executor = OfferExecutor()
    return executor.execute(plan)


def run_offer_evaluation_with_planning(
    pnr_locator: str,
    require_approval: bool = False,
    **kwargs
) -> ExecutionResult:
    """
    Run full offer evaluation using planner-executor pattern.

    This is the main entry point for plan-based offer evaluation.

    NOTE: Consider using run_offer_evaluation_incremental() instead
    for better failure handling and dynamic re-planning.
    """
    coordinator = PlannerExecutorCoordinator(
        require_plan_approval=require_approval,
    )

    context = {
        "pnr_locator": pnr_locator,
        **kwargs,
    }

    return coordinator.run(context)


# =============================================================================
# INCREMENTAL PLANNER-EXECUTOR PATTERN (RECOMMENDED)
# =============================================================================
#
# This implements the CORRECT planner-worker pattern:
# 1. Planner plans ONLY the next action
# 2. Worker executes and returns rich result with recommendation
# 3. Planner observes result and plans next action based on updated state
# 4. Repeat until goal achieved or unrecoverable failure
#
# Key differences from batch pattern:
# - No upfront planning of entire workflow
# - Workers return recommendations, not just success/failure
# - Planner is consulted after EVERY step
# - Dynamic task simplification on repeated failures
# =============================================================================


@dataclass
class IncrementalState:
    """
    State tracked during incremental plan-execute cycles.

    This is the "memory" that the planner queries before each decision.
    Tracks: current goal, steps completed, results so far, failed attempts.
    """
    goal: str
    context: Dict[str, Any]
    completed_steps: List[str] = field(default_factory=list)
    results: Dict[str, WorkerResult] = field(default_factory=dict)
    failed_attempts: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    current_step: Optional[str] = None
    is_simplified: bool = False
    simplification_level: int = 0  # 0 = full, 1 = reduced, 2 = minimal
    started_at: datetime = field(default_factory=datetime.now)
    human_escalation_requested: bool = False

    # Available steps in order of execution (can be modified during execution)
    available_steps: List[str] = field(default_factory=lambda: [
        "eligibility",
        "inventory",
        "offer_selection",
        "personalization",
        "channel_timing",
        "tracking",
    ])

    # Steps that can be skipped during simplification
    optional_steps: List[str] = field(default_factory=lambda: [
        "personalization",
        "tracking",
    ])

    def get_next_step(self) -> Optional[str]:
        """Get the next step to execute based on current state."""
        for step in self.available_steps:
            if step not in self.completed_steps:
                return step
        return None

    def record_success(self, step: str, result: WorkerResult) -> None:
        """Record a successful step execution."""
        self.completed_steps.append(step)
        self.results[step] = result
        self.current_step = None

        # Merge result data into context for next steps
        if result.data:
            self.context.update(result.data)

    def record_failure(self, step: str, result: WorkerResult) -> None:
        """Record a failed step execution."""
        if step not in self.failed_attempts:
            self.failed_attempts[step] = []

        self.failed_attempts[step].append({
            "timestamp": datetime.now().isoformat(),
            "error": result.error,
            "error_type": result.error_type,
            "recommendation": result.recommendation.value,
        })
        self.results[step] = result

    def get_retry_count(self, step: str) -> int:
        """Get number of retry attempts for a step."""
        return len(self.failed_attempts.get(step, []))

    def simplify(self, hint: Optional[str] = None) -> bool:
        """
        Simplify the task by removing optional steps.

        Returns True if simplification was possible, False if already minimal.
        """
        if self.simplification_level >= 2:
            return False  # Already at minimal

        self.simplification_level += 1
        self.is_simplified = True

        if hint and hint in self.available_steps:
            # Remove the specific suggested step
            self.available_steps = [s for s in self.available_steps if s != hint]
        elif self.simplification_level == 1:
            # Level 1: Remove tracking
            self.available_steps = [s for s in self.available_steps if s != "tracking"]
        elif self.simplification_level == 2:
            # Level 2: Remove personalization too
            self.available_steps = [s for s in self.available_steps if s != "personalization"]

        logger.info(
            "task_simplified",
            level=self.simplification_level,
            remaining_steps=self.available_steps,
            hint=hint,
        )
        return True

    def is_goal_achieved(self) -> bool:
        """Check if the goal has been achieved."""
        # Goal is achieved when all required steps are completed
        required_steps = [s for s in self.available_steps if s not in self.optional_steps]
        return all(step in self.completed_steps for step in required_steps)

    def should_abort(self) -> bool:
        """Check if execution should be aborted."""
        # Abort if any non-optional step has failed 3+ times
        for step in self.available_steps:
            if step in self.optional_steps:
                continue
            if self.get_retry_count(step) >= 3:
                return True
        return False

    def get_accumulated_data(self) -> Dict[str, Any]:
        """Get all data accumulated from completed steps."""
        data = dict(self.context)
        for step, result in self.results.items():
            if result.success and result.data:
                data.update(result.data)
        return data

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "completed_steps": self.completed_steps,
            "current_step": self.current_step,
            "failed_attempts": self.failed_attempts,
            "is_simplified": self.is_simplified,
            "simplification_level": self.simplification_level,
            "available_steps": self.available_steps,
            "human_escalation_requested": self.human_escalation_requested,
        }


class IncrementalOfferPlanner:
    """
    Incremental planner that plans ONE step at a time.

    Key principle: "Plan next action, wait for result, re-plan based on state."

    Unlike the batch OfferPlanner which creates all steps upfront,
    this planner is consulted after EVERY worker execution.
    """

    def __init__(self):
        self.memory = get_memory()

    def plan_next_action(self, state: IncrementalState) -> Optional[PlanStep]:
        """
        Plan ONLY the next action based on current state.

        This is called after each worker execution, giving the planner
        a chance to adjust based on what actually happened.
        """
        # Check if we should abort
        if state.should_abort():
            logger.warning(
                "planner_abort",
                reason="too_many_failures",
                failed_steps=list(state.failed_attempts.keys()),
            )
            return None

        # Check if goal is achieved
        if state.is_goal_achieved():
            logger.info("planner_goal_achieved", completed=state.completed_steps)
            return None

        # Get the next step
        next_step_id = state.get_next_step()
        if not next_step_id:
            return None

        # Check if this step has failed before
        retry_count = state.get_retry_count(next_step_id)
        last_failure = None
        if retry_count > 0:
            last_failure = state.failed_attempts[next_step_id][-1]

        # Build step with context-aware parameters
        step = self._build_step(next_step_id, state, retry_count, last_failure)

        state.current_step = next_step_id

        logger.info(
            "planner_next_action",
            step_id=next_step_id,
            retry_count=retry_count,
            is_simplified=state.is_simplified,
        )

        return step

    def _build_step(
        self,
        step_id: str,
        state: IncrementalState,
        retry_count: int,
        last_failure: Optional[Dict[str, Any]],
    ) -> PlanStep:
        """Build a step with parameters adjusted based on state and history."""
        pnr = state.context.get("pnr_locator", "unknown")

        # Base step definitions
        step_definitions = {
            "eligibility": {
                "action": "check_eligibility",
                "description": "Verify customer eligibility and check for suppressions",
                "agent": "customer_intelligence",
            },
            "inventory": {
                "action": "analyze_inventory",
                "description": "Check cabin availability and identify upgrade opportunities",
                "agent": "flight_optimization",
            },
            "offer_selection": {
                "action": "select_offer",
                "description": "Evaluate offer options and select optimal offer based on EV",
                "agent": "offer_orchestration",
            },
            "personalization": {
                "action": "generate_message",
                "description": "Create personalized offer message for customer",
                "agent": "personalization",
            },
            "channel_timing": {
                "action": "select_channel",
                "description": "Determine optimal channel and timing for delivery",
                "agent": "channel_timing",
            },
            "tracking": {
                "action": "setup_tracking",
                "description": "Configure A/B test tracking and measurement",
                "agent": "measurement_learning",
            },
        }

        definition = step_definitions.get(step_id, {
            "action": step_id,
            "description": f"Execute {step_id}",
            "agent": "unknown",
        })

        # Build parameters
        parameters = {"pnr": pnr}

        # Add retry-specific parameters
        if retry_count > 0:
            parameters["retry_count"] = retry_count
            parameters["is_retry"] = True

            # Adjust based on last failure type
            if last_failure:
                error_type = last_failure.get("error_type", "")
                recommendation = last_failure.get("recommendation", "")

                if error_type == "timeout":
                    parameters["timeout_multiplier"] = 1.5 ** retry_count
                elif error_type == "rate_limit":
                    parameters["use_backup_api"] = True
                elif recommendation == "use_backup":
                    parameters["use_backup"] = True
                elif recommendation == "simplify":
                    parameters["simplified_mode"] = True

        # Add accumulated data from previous steps
        accumulated = state.get_accumulated_data()
        if "customer_data" in accumulated:
            parameters["customer_data"] = accumulated["customer_data"]
        if "flight_data" in accumulated:
            parameters["flight_data"] = accumulated["flight_data"]
        if "offer_options" in accumulated:
            parameters["offer_options"] = accumulated["offer_options"]

        return PlanStep(
            step_id=step_id,
            action=definition["action"],
            description=definition["description"],
            agent=definition["agent"],
            parameters=parameters,
            dependencies=[],  # No static dependencies - planner controls order
        )

    def handle_failure(
        self,
        state: IncrementalState,
        step: PlanStep,
        result: WorkerResult,
    ) -> str:
        """
        Handle a worker failure and decide what to do next.

        Returns: "retry", "skip", "simplify", "escalate", or "abort"
        """
        recommendation = result.recommendation
        retry_count = state.get_retry_count(step.step_id)

        # Handle based on worker's recommendation
        if recommendation == WorkerRecommendation.RETRY:
            if retry_count < 3:
                return "retry"
            else:
                return "abort" if step.step_id not in state.optional_steps else "skip"

        elif recommendation == WorkerRecommendation.RETRY_WITH_BACKOFF:
            if retry_count < 3:
                # The coordinator will handle the backoff
                return "retry_with_backoff"
            else:
                return "abort" if step.step_id not in state.optional_steps else "skip"

        elif recommendation == WorkerRecommendation.USE_BACKUP:
            if retry_count < 2:
                return "retry"  # Retry will use backup based on parameters
            else:
                return "abort" if step.step_id not in state.optional_steps else "skip"

        elif recommendation == WorkerRecommendation.SIMPLIFY:
            if state.simplify(result.simplification_hint):
                return "continue"  # Simplified, try next step
            else:
                return "abort"  # Can't simplify further

        elif recommendation == WorkerRecommendation.SKIP:
            if step.step_id in state.optional_steps:
                state.completed_steps.append(step.step_id)  # Mark as done
                return "continue"
            else:
                return "abort"  # Can't skip required step

        elif recommendation == WorkerRecommendation.ESCALATE:
            state.human_escalation_requested = True
            return "escalate"

        elif recommendation == WorkerRecommendation.ABORT:
            return "abort"

        # Default: try to continue if possible
        if step.step_id in state.optional_steps:
            return "skip"
        elif retry_count < 3:
            return "retry"
        else:
            return "abort"


class IncrementalOfferExecutor:
    """
    Executor that returns rich WorkerResult with recommendations.

    Unlike the batch executor, this wraps agent calls to provide
    intelligent failure recommendations instead of just errors.
    """

    def __init__(self):
        from agents.customer_intelligence import CustomerIntelligenceAgent
        from agents.flight_optimization import FlightOptimizationAgent
        from agents.offer_orchestration import OfferOrchestrationAgent
        from agents.personalization import PersonalizationAgent
        from agents.channel_timing import ChannelTimingAgent
        from agents.measurement_learning import MeasurementLearningAgent

        self.agents = {
            "customer_intelligence": CustomerIntelligenceAgent(),
            "flight_optimization": FlightOptimizationAgent(),
            "offer_orchestration": OfferOrchestrationAgent(),
            "personalization": PersonalizationAgent(),
            "channel_timing": ChannelTimingAgent(),
            "measurement_learning": MeasurementLearningAgent(),
        }

        self.memory = get_memory()

    def execute_step(self, step: PlanStep, state: IncrementalState) -> WorkerResult:
        """
        Execute a single step and return a rich WorkerResult.

        The result includes not just success/failure, but a recommendation
        for what the planner should do next.
        """
        start_time = datetime.now()

        agent = self.agents.get(step.agent)
        if not agent:
            return WorkerResult.failure_result(
                error=f"Unknown agent: {step.agent}",
                error_type="configuration",
                recommendation=WorkerRecommendation.ABORT,
            )

        # Build state for agent
        agent_state = self._build_agent_state(step, state)

        try:
            # Execute agent with timeout handling
            result = self._execute_with_monitoring(agent, step, agent_state)

            duration_ms = (datetime.now() - start_time).total_seconds() * 1000

            # Check for early termination conditions
            termination = self._check_early_termination(step, result)
            if termination:
                return termination

            # Record success in memory
            customer_id = state.context.get("customer_id") or agent_state.get("customer_data", {}).get("lylty_acct_id")
            if customer_id:
                self.memory.record_decision(
                    session_id=state.context.get("session_id", state.context.get("pnr_locator", "unknown")),
                    customer_id=customer_id,
                    agent_name=step.agent,
                    decision=result,
                )

            return WorkerResult.success_result(
                data=result,
                confidence=result.get("confidence", 1.0) if isinstance(result, dict) else 1.0,
            )

        except TimeoutError as e:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            return WorkerResult.failure_result(
                error=str(e),
                error_type="timeout",
                recommendation=WorkerRecommendation.RETRY_WITH_BACKOFF,
                retry_after_seconds=2.0 * (1 + state.get_retry_count(step.step_id)),
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            error_str = str(e).lower()

            # Determine error type and recommendation based on error
            if "rate limit" in error_str or "429" in error_str:
                return WorkerResult.failure_result(
                    error=str(e),
                    error_type="rate_limit",
                    recommendation=WorkerRecommendation.RETRY_WITH_BACKOFF,
                    retry_after_seconds=5.0,
                    backup_suggestion="use_cached_data",
                    duration_ms=duration_ms,
                )

            elif "timeout" in error_str or "timed out" in error_str:
                return WorkerResult.failure_result(
                    error=str(e),
                    error_type="timeout",
                    recommendation=WorkerRecommendation.RETRY,
                    duration_ms=duration_ms,
                )

            elif "not found" in error_str or "404" in error_str:
                return WorkerResult.failure_result(
                    error=str(e),
                    error_type="not_found",
                    recommendation=WorkerRecommendation.ABORT,
                    duration_ms=duration_ms,
                )

            elif "validation" in error_str or "invalid" in error_str:
                return WorkerResult.failure_result(
                    error=str(e),
                    error_type="validation",
                    recommendation=WorkerRecommendation.SIMPLIFY,
                    simplification_hint=step.step_id if step.step_id in state.optional_steps else None,
                    duration_ms=duration_ms,
                )

            elif "connection" in error_str or "network" in error_str:
                return WorkerResult.failure_result(
                    error=str(e),
                    error_type="network",
                    recommendation=WorkerRecommendation.RETRY_WITH_BACKOFF,
                    retry_after_seconds=3.0,
                    backup_suggestion="use_backup_api",
                    duration_ms=duration_ms,
                )

            else:
                # Unknown error - let planner decide
                return WorkerResult.failure_result(
                    error=str(e),
                    error_type="unknown",
                    recommendation=WorkerRecommendation.RETRY if state.get_retry_count(step.step_id) < 2 else WorkerRecommendation.ABORT,
                    duration_ms=duration_ms,
                )

    def _build_agent_state(self, step: PlanStep, state: IncrementalState) -> Dict[str, Any]:
        """Build the state dict expected by agents."""
        agent_state = {
            "pnr_locator": state.context.get("pnr_locator"),
            "reasoning_trace": state.context.get("reasoning_trace", []),
        }

        # Add accumulated data from previous steps
        accumulated = state.get_accumulated_data()
        agent_state.update(accumulated)

        # Add step-specific parameters
        agent_state.update(step.parameters)

        return agent_state

    def _execute_with_monitoring(
        self,
        agent,
        step: PlanStep,
        agent_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute agent with monitoring and timeout handling."""
        # For now, direct execution
        # In production, this could add timeout, circuit breaker, etc.
        return agent.analyze(agent_state)

    def _check_early_termination(
        self,
        step: PlanStep,
        result: Dict[str, Any],
    ) -> Optional[WorkerResult]:
        """Check if we should terminate early based on step result."""
        if step.step_id == "eligibility":
            if not result.get("customer_eligible", True):
                # Customer not eligible - this is a valid "success" but we should stop
                return WorkerResult(
                    status="success",
                    data=result,
                    recommendation=WorkerRecommendation.ABORT,  # Don't continue to next steps
                    confidence=1.0,
                )

        if step.step_id == "offer_selection":
            if not result.get("should_send_offer", True):
                # No offer to send - valid success but stop here
                return WorkerResult(
                    status="success",
                    data=result,
                    recommendation=WorkerRecommendation.ABORT,
                    confidence=result.get("confidence", 1.0),
                )

        return None


class IncrementalPlannerExecutorCoordinator:
    """
    Coordinator for the CORRECT incremental planner-worker pattern.

    This implements:
    1. Plan ONLY the next action
    2. Execute and get rich result with recommendation
    3. Handle failure based on worker's recommendation
    4. Re-plan based on updated state
    5. Repeat until goal achieved or unrecoverable failure

    Key differences from batch pattern:
    - Planner consulted after EVERY step
    - Workers return recommendations, not just errors
    - Dynamic retry with backoff
    - Task simplification on repeated failures
    - Human escalation support
    """

    def __init__(
        self,
        planner: Optional[IncrementalOfferPlanner] = None,
        executor: Optional[IncrementalOfferExecutor] = None,
        max_retries_per_step: int = 3,
        require_human_approval: bool = False,
    ):
        self.planner = planner or IncrementalOfferPlanner()
        self.executor = executor or IncrementalOfferExecutor()
        self.max_retries_per_step = max_retries_per_step
        self.require_human_approval = require_human_approval
        self.memory = get_memory()

    def run(
        self,
        context: Dict[str, Any],
        human_callback: Optional[Callable[[IncrementalState, str], bool]] = None,
    ) -> ExecutionResult:
        """
        Run the incremental planner-executor cycle.

        Args:
            context: Initial context with pnr_locator, etc.
            human_callback: Optional callback for human escalation.
                           Called with (state, reason) -> should_continue

        Returns:
            ExecutionResult with final outcome
        """
        import time

        # Initialize state
        state = IncrementalState(
            goal=f"Evaluate and deliver optimal offer for PNR {context.get('pnr_locator')}",
            context=context,
        )

        logger.info(
            "incremental_execution_started",
            pnr=context.get("pnr_locator"),
            goal=state.goal,
        )

        steps_completed = 0
        steps_failed = 0

        while True:
            # 1. PLAN: Get next action from planner
            next_step = self.planner.plan_next_action(state)

            if next_step is None:
                # No more steps - either goal achieved or should abort
                break

            logger.info(
                "executing_step",
                step_id=next_step.step_id,
                retry_count=state.get_retry_count(next_step.step_id),
            )

            # 2. EXECUTE: Run the worker
            result = self.executor.execute_step(next_step, state)

            # 3. OBSERVE: Process the result
            if result.success:
                state.record_success(next_step.step_id, result)
                steps_completed += 1

                logger.info(
                    "step_succeeded",
                    step_id=next_step.step_id,
                    confidence=result.confidence,
                )

                # Check if worker recommends early termination
                if result.recommendation == WorkerRecommendation.ABORT:
                    logger.info(
                        "early_termination",
                        step_id=next_step.step_id,
                        reason="worker_recommendation",
                    )
                    break
            else:
                state.record_failure(next_step.step_id, result)
                steps_failed += 1

                logger.warning(
                    "step_failed",
                    step_id=next_step.step_id,
                    error=result.error,
                    error_type=result.error_type,
                    recommendation=result.recommendation.value,
                )

                # 4. HANDLE FAILURE: Ask planner what to do
                action = self.planner.handle_failure(state, next_step, result)

                if action == "retry":
                    # Will retry on next iteration
                    continue

                elif action == "retry_with_backoff":
                    # Wait before retry
                    wait_time = result.retry_after_seconds or 2.0
                    logger.info("backoff_wait", seconds=wait_time)
                    time.sleep(wait_time)
                    continue

                elif action == "skip":
                    # Mark as skipped and continue
                    state.completed_steps.append(next_step.step_id)
                    logger.info("step_skipped", step_id=next_step.step_id)
                    continue

                elif action == "simplify":
                    # Task was simplified, continue with reduced steps
                    continue

                elif action == "escalate":
                    # Human intervention needed
                    if human_callback:
                        should_continue = human_callback(state, f"Step {next_step.step_id} failed: {result.error}")
                        if should_continue:
                            continue
                    # No callback or human said stop
                    logger.warning("human_escalation", step_id=next_step.step_id)
                    break

                elif action == "abort":
                    logger.error(
                        "execution_aborted",
                        step_id=next_step.step_id,
                        reason=result.error,
                    )
                    break

                elif action == "continue":
                    # Planner says continue (e.g., after simplification)
                    continue

        # Build final result
        total_duration = (datetime.now() - state.started_at).total_seconds() * 1000
        success = state.is_goal_achieved() or (
            steps_completed > 0 and
            "eligibility" in state.completed_steps and
            "offer_selection" in state.completed_steps
        )

        # Record metrics
        metrics.record_pipeline_completion(success, total_duration / 1000)

        logger.info(
            "incremental_execution_completed",
            success=success,
            steps_completed=steps_completed,
            steps_failed=steps_failed,
            duration_ms=total_duration,
            simplified=state.is_simplified,
        )

        return ExecutionResult(
            plan_id=f"incremental_{context.get('pnr_locator')}_{state.started_at.strftime('%H%M%S')}",
            success=success,
            final_result=state.get_accumulated_data(),
            steps_completed=steps_completed,
            steps_failed=steps_failed,
            total_duration_ms=total_duration,
            feedback=self._generate_feedback(state),
            needs_replanning=False,  # Incremental doesn't need re-planning
        )

    def _generate_feedback(self, state: IncrementalState) -> str:
        """Generate human-readable feedback about the execution."""
        parts = []

        if state.is_goal_achieved():
            parts.append("Goal achieved successfully.")
        elif state.human_escalation_requested:
            parts.append("Execution paused for human review.")
        elif state.should_abort():
            parts.append("Execution aborted due to repeated failures.")
        else:
            parts.append(f"Completed {len(state.completed_steps)}/{len(state.available_steps)} steps.")

        if state.is_simplified:
            parts.append(f"Task was simplified (level {state.simplification_level}).")

        if state.failed_attempts:
            failed_steps = list(state.failed_attempts.keys())
            parts.append(f"Failures encountered in: {', '.join(failed_steps)}")

        return " ".join(parts)


# =============================================================================
# CONVENIENCE FUNCTIONS (INCREMENTAL)
# =============================================================================

def run_offer_evaluation_incremental(
    pnr_locator: str,
    human_callback: Optional[Callable] = None,
    **kwargs,
) -> ExecutionResult:
    """
    Run offer evaluation using the CORRECT incremental planner-executor pattern.

    This is the RECOMMENDED entry point for offer evaluation.

    Key benefits over batch pattern:
    - Plans one step at a time based on actual results
    - Workers return recommendations for failure recovery
    - Dynamic task simplification on repeated failures
    - Human escalation support

    Args:
        pnr_locator: The PNR to evaluate
        human_callback: Optional callback for human escalation
        **kwargs: Additional context (customer_id, session_id, etc.)

    Returns:
        ExecutionResult with final outcome
    """
    coordinator = IncrementalPlannerExecutorCoordinator()

    context = {
        "pnr_locator": pnr_locator,
        **kwargs,
    }

    return coordinator.run(context, human_callback=human_callback)
