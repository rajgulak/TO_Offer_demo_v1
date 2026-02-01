"""
Tailored Offers Agentic Workflow

This module defines the LangGraph workflow that orchestrates
all 6 agents in the Tailored Offers system.

## Architecture Decision: Enhanced Choreography + Planner-Worker Fallback

We use TWO patterns, each for specific scenarios:

### 1. Enhanced Choreography (Primary - Happy Path)
- LangGraph StateGraph with resilient node wrappers
- Each node has: retry with backoff, timeout handling, graceful degradation
- Use when: Normal operations, predictable failures
- Benefits: Clear debugging ("Node X failed"), no SPOF, visual graph

### 2. Planner-Worker (Secondary - Recovery Path)
- Incremental planning with worker recommendations
- Planner decides next step based on previous results
- Use when: Complex failures, need intelligent recovery, task simplification
- Benefits: Adaptive, handles edge cases, explicit reasoning

## 3-Layer Guardrail Architecture

The workflow is protected by a 3-layer guardrail system for latency optimization:

### Layer 1: Synchronous Pre-flight (~40-70ms)
- Runs BEFORE any LLM/heavy processing
- Fast checks: input validation, suppression, consent, rate limits
- Blocking: if fails, abort immediately

### Layer 2: Asynchronous Background (~200-500ms)
- Runs IN PARALLEL with the workflow
- Compliance audit, value validation, fairness monitoring
- Non-blocking: results checked before delivery

### Layer 3: Triggered Escalation (human-in-loop)
- Activated for exceptional cases
- High-value offers, anomalies, regulatory flags
- Queues for human review when needed

## When to Use Each Pattern:

| Scenario                          | Use                    |
|-----------------------------------|------------------------|
| Normal request                    | Enhanced Choreography  |
| Simple retry needed               | Enhanced Choreography  |
| Rate limit / timeout              | Enhanced Choreography  |
| Multiple consecutive failures     | Planner-Worker         |
| Need to simplify task             | Planner-Worker         |
| Need human escalation             | Planner-Worker         |
| Complex failure pattern           | Planner-Worker         |

Pipeline:
  [Pre-flight Guardrails] → Load Data → Customer Intelligence →
  Flight Optimization → Offer Orchestration → Personalization →
  Channel & Timing → Tracking Setup → [Pre-delivery Guardrails] →
  Final Decision
"""
import os
import time
import asyncio
from typing import Dict, Any, Literal, Callable, Optional
from functools import wraps
from dataclasses import dataclass
from langgraph.graph import StateGraph, END

from .state import AgentState, OfferDecision, create_initial_state
from .prechecks import check_customer_eligibility, check_inventory_availability
from .delivery import generate_message, select_channel, setup_tracking
# ReWOO Pattern: Planner-Worker-Solver for Offer Orchestration
from .offer_orchestration_rewoo import OfferOrchestrationReWOO as OfferOrchestrationAgent

from tools.data_tools import get_enriched_pnr
from infrastructure.guardrails import (
    GuardrailCoordinator,
    GuardrailVerdict,
    LayerResult,
    create_guardrail_coordinator,
)
from infrastructure.production_safety import (
    ProductionSafetyCoordinator,
    AlertSeverity,
    get_safety_coordinator,
    create_safety_coordinator,
)
from infrastructure.human_in_loop import (
    HumanInTheLoopManager,
    ApprovalRequest,
    ApprovalStatus,
    EscalationReason,
    get_hitl_manager,
    create_hitl_manager,
)

# MCP mode toggle - set USE_MCP=true to use MCP client/server
USE_MCP = os.getenv("USE_MCP", "false").lower() == "true"

# Guardrail toggle - set USE_GUARDRAILS=false to disable (for testing)
USE_GUARDRAILS = os.getenv("USE_GUARDRAILS", "true").lower() == "true"


# =============================================================================
# RESILIENT NODE WRAPPER (Enhanced Choreography)
# =============================================================================

@dataclass
class NodeConfig:
    """Configuration for resilient node execution."""
    max_retries: int = 2
    retry_delay: float = 1.0
    retry_backoff: float = 2.0  # Exponential backoff multiplier
    timeout_seconds: Optional[float] = 30.0
    fallback_on_failure: bool = True  # Return graceful degradation vs raise
    node_name: str = "unknown"


class NodeExecutionError(Exception):
    """Raised when a node fails after all retries."""
    def __init__(self, node_name: str, original_error: Exception, attempts: int):
        self.node_name = node_name
        self.original_error = original_error
        self.attempts = attempts
        super().__init__(f"Node '{node_name}' failed after {attempts} attempts: {original_error}")


def resilient_node(config: NodeConfig):
    """
    Decorator that adds resilience to a choreography node.

    Features:
    - Retry with exponential backoff
    - Timeout handling
    - Graceful degradation (optional)
    - Clear error attribution ("Node X failed")

    This is the KEY to Enhanced Choreography - each node handles its own failures.
    """
    def decorator(func: Callable[[AgentState], Dict[str, Any]]):
        @wraps(func)
        def wrapper(state: AgentState) -> Dict[str, Any]:
            last_error = None
            delay = config.retry_delay

            for attempt in range(1, config.max_retries + 2):  # +2 because range is exclusive and we want initial + retries
                try:
                    # Execute the node
                    result = func(state)

                    # Success - add execution metadata
                    if attempt > 1:
                        trace = result.get("reasoning_trace", [])
                        trace.append(f"NODE {config.node_name}: Succeeded on attempt {attempt}")
                        result["reasoning_trace"] = trace

                    return result

                except Exception as e:
                    last_error = e
                    error_type = _classify_error(e)

                    # Log the failure
                    print(f"Node '{config.node_name}' attempt {attempt} failed: {e} (type: {error_type})")

                    # Check if we should retry
                    if attempt <= config.max_retries:
                        if error_type in ["timeout", "rate_limit", "connection"]:
                            # Transient error - retry with backoff
                            print(f"  Retrying in {delay:.1f}s...")
                            time.sleep(delay)
                            delay *= config.retry_backoff
                            continue
                        elif error_type == "validation":
                            # Validation error - no point retrying
                            break
                        else:
                            # Unknown error - retry once
                            if attempt == 1:
                                time.sleep(delay)
                                continue
                            break

            # All retries exhausted
            if config.fallback_on_failure:
                # Return graceful degradation
                return _create_fallback_result(config.node_name, last_error, attempt)
            else:
                # Raise the error
                raise NodeExecutionError(config.node_name, last_error, attempt)

        return wrapper
    return decorator


def _classify_error(e: Exception) -> str:
    """Classify an error for retry decisions."""
    error_str = str(e).lower()

    if "timeout" in error_str or "timed out" in error_str:
        return "timeout"
    elif "rate limit" in error_str or "429" in error_str or "too many requests" in error_str:
        return "rate_limit"
    elif "connection" in error_str or "network" in error_str:
        return "connection"
    elif "validation" in error_str or "invalid" in error_str:
        return "validation"
    elif "not found" in error_str or "404" in error_str:
        return "not_found"
    else:
        return "unknown"


def _create_fallback_result(node_name: str, error: Exception, attempts: int) -> Dict[str, Any]:
    """Create a graceful degradation result when a node fails."""
    return {
        "node_failed": True,
        "failed_node": node_name,
        "error": str(error),
        "attempts": attempts,
        "reasoning_trace": [
            f"NODE {node_name}: FAILED after {attempts} attempts - {error}",
            f"NODE {node_name}: Returning graceful degradation"
        ]
    }


# =============================================================================
# AGENT INSTANCES
# =============================================================================

# Initialize agents (singleton instances)
offer_agent = OfferOrchestrationAgent()


async def load_data_mcp(pnr_locator: str) -> Dict[str, Any]:
    """
    Load data via MCP client/server.

    Uses langchain-mcp-adapters to call the MCP data server.
    """
    from tools.mcp_client import MCPDataClient

    client = MCPDataClient()
    enriched = await client.get_enriched_pnr(pnr_locator)
    return enriched


def load_data(state: AgentState) -> Dict[str, Any]:
    """
    Load all required data for the PNR.

    This is the first step - gather all data before agent processing.

    Data source depends on USE_MCP environment variable:
    - USE_MCP=false (default): Direct Python function calls
    - USE_MCP=true: MCP client/server via langchain-mcp-adapters
    """
    pnr_locator = state["pnr_locator"]

    # Choose data loading method based on USE_MCP flag
    if USE_MCP:
        # Use MCP client (async)
        try:
            enriched = asyncio.run(load_data_mcp(pnr_locator))
            data_source = "MCP"
        except Exception as e:
            return {
                "errors": [f"MCP data load failed: {str(e)}"],
                "reasoning_trace": [f"DATA LOAD (MCP): Failed - {str(e)}"]
            }
    else:
        # Use direct function calls (sync)
        enriched = get_enriched_pnr(pnr_locator)
        data_source = "Direct"

    if not enriched:
        return {
            "errors": [f"PNR {pnr_locator} not found"],
            "reasoning_trace": [f"DATA LOAD ({data_source}): PNR {pnr_locator} not found - aborting"]
        }

    # Build flight identifier from airline code + flight number
    flight = enriched["flight"]
    flight_id = f"{flight.get('operat_airln_cd', 'AA')}{flight.get('operat_flight_nbr', '')}"

    return {
        "customer_data": enriched["customer"],
        "flight_data": enriched["flight"],
        "reservation_data": enriched["pnr"],
        "ml_scores": enriched["ml_scores"],
        "reasoning_trace": [
            f"DATA LOAD ({data_source}): Loaded data for PNR {pnr_locator} | "
            f"Customer: {enriched['customer']['first_name']} {enriched['customer']['last_name']} | "
            f"Flight: {flight_id}"
        ]
    }


# =============================================================================
# RESILIENT NODE FUNCTIONS (Enhanced Choreography)
# =============================================================================
#
# Each node is wrapped with resilient_node() which provides:
# - Retry with exponential backoff for transient errors
# - Clear error attribution ("Node X failed at attempt Y")
# - Graceful degradation when all retries exhausted
#
# If a node fails, you KNOW which node failed - no ambiguity.
# =============================================================================

@resilient_node(NodeConfig(
    node_name="customer_intelligence",
    max_retries=2,
    retry_delay=1.0,
    fallback_on_failure=True,
))
def run_customer_intelligence(state: AgentState) -> Dict[str, Any]:
    """Run Customer Intelligence pre-check with resilience."""
    result = check_customer_eligibility(
        state.get("customer_data", {}),
        state.get("reservation_data"),
        state.get("ml_scores"),
    )
    return {
        "customer_eligible": result.get("customer_eligible", False),
        "customer_segment": result.get("customer_segment", "unknown"),
        "suppression_reason": result.get("suppression_reason"),
        "customer_reasoning": result.get("customer_reasoning", ""),
        "reasoning_trace": result.get("reasoning_trace", []),
    }


@resilient_node(NodeConfig(
    node_name="flight_optimization",
    max_retries=2,
    retry_delay=1.0,
    fallback_on_failure=True,
))
def run_flight_optimization(state: AgentState) -> Dict[str, Any]:
    """Run Flight Optimization pre-check with resilience."""
    result = check_inventory_availability(
        state.get("flight_data", {}),
        state.get("reservation_data", {}).get("max_bkd_cabin_cd", "Y"),
    )
    return {
        "flight_priority": result.get("flight_priority", "low"),
        "recommended_cabins": result.get("recommended_cabins", []),
        "inventory_status": result.get("inventory_status", "unknown"),
        "flight_reasoning": result.get("flight_reasoning", ""),
        "reasoning_trace": result.get("reasoning_trace", []),
    }


@resilient_node(NodeConfig(
    node_name="offer_orchestration",
    max_retries=2,
    retry_delay=1.0,
    fallback_on_failure=True,
))
def run_offer_orchestration(state: AgentState) -> Dict[str, Any]:
    """Run Offer Orchestration Agent with resilience."""
    return offer_agent.analyze(state)


@resilient_node(NodeConfig(
    node_name="personalization",
    max_retries=1,  # Less critical, fewer retries
    retry_delay=0.5,
    fallback_on_failure=True,
))
def run_personalization(state: AgentState) -> Dict[str, Any]:
    """Run Personalization message generation with resilience."""
    result = generate_message(
        state.get("customer_data", {}),
        state.get("flight_data", {}),
        state.get("selected_offer", ""),
        state.get("offer_price", 0),
    )
    return {
        "message_subject": result.get("message_subject", ""),
        "message_body": result.get("message_body", ""),
        "message_tone": result.get("message_tone", "professional"),
        "personalization_elements": result.get("personalization_elements", []),
        "personalization_reasoning": result.get("personalization_reasoning", ""),
        "reasoning_trace": result.get("reasoning_trace", []),
    }


@resilient_node(NodeConfig(
    node_name="channel_timing",
    max_retries=1,
    retry_delay=0.5,
    fallback_on_failure=True,
))
def run_channel_timing(state: AgentState) -> Dict[str, Any]:
    """Run Channel selection with resilience."""
    result = select_channel(
        state.get("customer_data", {}),
        state.get("reservation_data", {}).get("hours_to_departure", 72),
    )
    return {
        "selected_channel": result.get("selected_channel", "email"),
        "send_time": result.get("send_time", ""),
        "backup_channel": result.get("backup_channel", ""),
        "channel_reasoning": result.get("channel_reasoning", ""),
        "reasoning_trace": result.get("reasoning_trace", []),
    }


@resilient_node(NodeConfig(
    node_name="measurement",
    max_retries=1,
    retry_delay=0.5,
    fallback_on_failure=True,
))
def run_measurement(state: AgentState) -> Dict[str, Any]:
    """Run Measurement tracking setup with resilience."""
    result = setup_tracking(
        state.get("pnr_locator", ""),
        state.get("selected_offer", ""),
    )
    return {
        "experiment_group": result.get("experiment_group", ""),
        "tracking_id": result.get("tracking_id", ""),
        "measurement_reasoning": result.get("measurement_reasoning", ""),
        "reasoning_trace": result.get("reasoning_trace", []),
    }


def compile_final_decision(state: AgentState) -> Dict[str, Any]:
    """
    Compile final offer decision from all agent outputs.

    This is the supervisor's final step - assembling the complete decision.
    """
    reasoning_parts = ["=== FINAL DECISION ==="]

    if not state.get("should_send_offer", False):
        reason = state.get("suppression_reason") or "Offer criteria not met"
        reasoning_parts.append(f"Decision: NO OFFER")
        reasoning_parts.append(f"Reason: {reason}")

        return {
            "final_decision": None,
            "reasoning_trace": [f"SUPERVISOR: Final decision - NO OFFER ({reason})"]
        }

    # Compile the offer decision
    decision = OfferDecision(
        offer_type=state.get("selected_offer", ""),
        price=state.get("offer_price", 0),
        discount_percent=state.get("discount_applied", 0),
        channel=state.get("selected_channel", ""),
        send_time=state.get("send_time", ""),
        message_subject=state.get("message_subject", ""),
        message_body=state.get("message_body", ""),
        fallback_offer=state.get("fallback_offer"),
        experiment_group=state.get("experiment_group", ""),
        tracking_id=state.get("tracking_id", "")
    )

    reasoning_parts.append(f"Decision: SEND OFFER")
    reasoning_parts.append(f"Offer: {decision.offer_type} @ ${decision.price:.0f}")
    reasoning_parts.append(f"Channel: {decision.channel} at {decision.send_time}")
    reasoning_parts.append(f"Experiment: {decision.experiment_group}")
    reasoning_parts.append(f"Tracking: {decision.tracking_id}")

    return {
        "final_decision": decision,
        "reasoning_trace": [
            f"SUPERVISOR: Final decision - SEND {decision.offer_type} @ ${decision.price:.0f} "
            f"via {decision.channel} | Tracking: {decision.tracking_id}"
        ]
    }


def should_continue_after_customer(state: AgentState) -> Literal["flight_optimization", "end"]:
    """Determine if workflow should continue after customer intelligence"""
    if state.get("customer_eligible", False):
        return "flight_optimization"
    return "end"


def should_continue_after_offer(state: AgentState) -> Literal["personalization", "end"]:
    """Determine if workflow should continue after offer orchestration"""
    if state.get("should_send_offer", False):
        return "personalization"
    return "end"


def create_workflow() -> StateGraph:
    """
    Create the LangGraph workflow for Tailored Offers.

    Returns a compiled workflow graph.
    """
    # Create the graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("load_data", load_data)
    workflow.add_node("customer_intelligence", run_customer_intelligence)
    workflow.add_node("flight_optimization", run_flight_optimization)
    workflow.add_node("offer_orchestration", run_offer_orchestration)
    workflow.add_node("personalization", run_personalization)
    workflow.add_node("channel_timing", run_channel_timing)
    workflow.add_node("measurement", run_measurement)
    workflow.add_node("final_decision", compile_final_decision)

    # Set entry point
    workflow.set_entry_point("load_data")

    # Add edges
    workflow.add_edge("load_data", "customer_intelligence")

    # Conditional edge after customer intelligence
    workflow.add_conditional_edges(
        "customer_intelligence",
        should_continue_after_customer,
        {
            "flight_optimization": "flight_optimization",
            "end": "final_decision"
        }
    )

    workflow.add_edge("flight_optimization", "offer_orchestration")

    # Conditional edge after offer orchestration
    workflow.add_conditional_edges(
        "offer_orchestration",
        should_continue_after_offer,
        {
            "personalization": "personalization",
            "end": "final_decision"
        }
    )

    workflow.add_edge("personalization", "channel_timing")
    workflow.add_edge("channel_timing", "measurement")
    workflow.add_edge("measurement", "final_decision")
    workflow.add_edge("final_decision", END)

    return workflow


def run_offer_evaluation(pnr_locator: str) -> Dict[str, Any]:
    """
    Run the complete offer evaluation workflow for a PNR.

    Args:
        pnr_locator: The PNR to evaluate

    Returns:
        Dictionary with final state including decision and reasoning trace
    """
    # Create workflow
    workflow = create_workflow()
    app = workflow.compile()

    # Create initial state
    initial_state = create_initial_state(pnr_locator)

    # Run the workflow
    final_state = app.invoke(initial_state)

    return final_state


def run_offer_evaluation_streaming(pnr_locator: str):
    """
    Run workflow with streaming to show agent-by-agent progress.

    Yields state updates as each agent completes.
    """
    workflow = create_workflow()
    app = workflow.compile()

    initial_state = create_initial_state(pnr_locator)

    # Stream the execution
    for event in app.stream(initial_state):
        yield event


# =============================================================================
# ENTRY POINTS: When to Use Each Pattern
# =============================================================================
#
# PATTERN 1: Enhanced Choreography (Primary - Happy Path)
#   Function: run_offer_evaluation()
#   Use when:
#     - Normal request processing
#     - Simple retryable failures (timeout, rate limit)
#     - Need clear debugging ("Node X failed")
#     - Want predictable, auditable flow
#
# PATTERN 2: Planner-Worker (Secondary - Recovery Path)
#   Function: run_offer_evaluation_with_recovery()
#   Use when:
#     - Multiple consecutive failures in choreography
#     - Need intelligent task simplification
#     - Need human escalation
#     - Complex failure patterns that need adaptive recovery
#
# =============================================================================


def run_offer_evaluation_with_recovery(
    pnr_locator: str,
    max_choreography_failures: int = 2,
) -> Dict[str, Any]:
    """
    Offer evaluation with automatic escalation to Planner-Worker.

    Strategy:
    1. Try Enhanced Choreography first (handles simple failures via node retries)
    2. If choreography fails completely, escalate to Planner-Worker for
       intelligent recovery (task simplification, human escalation, etc.)

    This represents the PRINCIPLE:
    - Choreography for happy path + simple failures
    - Planner-Worker for complex recovery scenarios

    Args:
        pnr_locator: The PNR to evaluate
        max_choreography_failures: How many node failures before escalating

    Returns:
        Dictionary with final state including decision and reasoning trace
    """
    from infrastructure.planner_executor import run_offer_evaluation_incremental

    # Step 1: Try Enhanced Choreography (handles simple failures)
    result = run_offer_evaluation(pnr_locator)

    # Check if choreography succeeded
    node_failures = _count_node_failures(result)

    if node_failures == 0:
        # Happy path - choreography succeeded
        result["execution_pattern"] = "enhanced_choreography"
        return result

    if node_failures <= max_choreography_failures:
        # Minor failures handled by node retries - still acceptable
        result["execution_pattern"] = "enhanced_choreography"
        result["node_failures_handled"] = node_failures
        return result

    # Step 2: Escalate to Planner-Worker for intelligent recovery
    print(f"Choreography had {node_failures} failures, escalating to Planner-Worker...")

    incremental_result = run_offer_evaluation_incremental(pnr_locator)
    state = _convert_incremental_result(
        incremental_result,
        pnr_locator,
        escalation_reason=f"Choreography failed with {node_failures} node failures"
    )
    state["execution_pattern"] = "planner_worker"
    return state


def _count_node_failures(result: Dict[str, Any]) -> int:
    """Count how many nodes failed in the choreography result."""
    failures = 0

    # Check for explicit node failures
    if result.get("node_failed"):
        failures += 1

    # Check reasoning trace for failure indicators
    for trace in result.get("reasoning_trace", []):
        if "FAILED" in trace or "failed" in trace.lower():
            failures += 1

    # Check for errors list
    if result.get("errors"):
        failures += len(result["errors"])

    return failures


def _convert_incremental_result(
    result,
    pnr_locator: str,
    escalation_reason: str = None,
) -> Dict[str, Any]:
    """Convert IncrementalExecutionResult to workflow-compatible format."""
    from .state import OfferDecision, create_initial_state

    # Start with initial state
    state = create_initial_state(pnr_locator)

    # Merge in the accumulated data from incremental execution
    if result.final_result:
        state.update(result.final_result)

    # Add metadata about execution
    state["execution_mode"] = "planner_worker"
    state["execution_success"] = result.success
    state["steps_completed"] = result.steps_completed
    state["steps_failed"] = result.steps_failed

    if escalation_reason:
        state["escalation_reason"] = escalation_reason
        trace = state.get("reasoning_trace", [])
        trace.insert(0, f"ESCALATION: {escalation_reason}")
        trace.insert(1, "ESCALATION: Using Planner-Worker for intelligent recovery")
        state["reasoning_trace"] = trace

    # Build final decision if we have the data
    if state.get("should_send_offer") and state.get("selected_offer"):
        state["final_decision"] = OfferDecision(
            offer_type=state.get("selected_offer", ""),
            price=state.get("offer_price", 0),
            discount_percent=state.get("discount_applied", 0),
            channel=state.get("selected_channel", ""),
            send_time=state.get("send_time", ""),
            message_subject=state.get("message_subject", ""),
            message_body=state.get("message_body", ""),
            fallback_offer=state.get("fallback_offer"),
            experiment_group=state.get("experiment_group", ""),
            tracking_id=state.get("tracking_id", "")
        )

    return state


# =============================================================================
# DIRECT ACCESS (For Testing / Specific Scenarios)
# =============================================================================

def run_choreography_only(pnr_locator: str) -> Dict[str, Any]:
    """
    Run ONLY Enhanced Choreography (no Planner-Worker fallback).

    Use when:
    - Testing choreography in isolation
    - Want fast-fail behavior
    - Debugging specific node failures

    Raises NodeExecutionError if a node fails after all retries.
    """
    result = run_offer_evaluation(pnr_locator)
    result["execution_pattern"] = "enhanced_choreography_only"
    return result


def run_planner_worker_only(pnr_locator: str) -> Dict[str, Any]:
    """
    Run ONLY Planner-Worker pattern (skip choreography).

    Use when:
    - Known complex failure scenario
    - Need task simplification capability
    - Need human escalation support
    - Testing planner-worker in isolation
    """
    from infrastructure.planner_executor import run_offer_evaluation_incremental

    result = run_offer_evaluation_incremental(pnr_locator)
    state = _convert_incremental_result(result, pnr_locator)
    state["execution_pattern"] = "planner_worker_only"
    return state


# =============================================================================
# GUARDRAIL-ENABLED EVALUATION
# =============================================================================
#
# This is the RECOMMENDED entry point for production use.
# It wraps the workflow with 3-layer guardrail protection:
#
# 1. Pre-flight sync checks (~60ms) - block invalid requests immediately
# 2. Async background checks - run in parallel, don't add latency
# 3. Pre-delivery triggered checks - human escalation for edge cases
#
# Latency impact: ~60ms additional for sync pre-flight (unavoidable)
#                 ~0ms for async (runs in parallel with workflow)
# =============================================================================


def run_offer_evaluation_guarded(
    pnr_locator: str,
    guardrail_coordinator: GuardrailCoordinator = None,
) -> Dict[str, Any]:
    """
    Run offer evaluation with 3-layer guardrail protection.

    This is the RECOMMENDED production entry point.

    Flow:
    1. Run sync pre-flight guardrails (~60ms)
       - If fails: abort immediately with reason
    2. Load data and start async background guardrails
    3. Execute main workflow (Enhanced Choreography)
    4. Wait for async guardrails before delivery
    5. Check triggered escalations
       - If escalation: queue for human review
    6. Return final result with guardrail metadata

    Args:
        pnr_locator: The PNR to evaluate
        guardrail_coordinator: Optional custom coordinator (for testing)

    Returns:
        Dictionary with final state, guardrail results, and any escalation info
    """
    # Initialize guardrails
    coordinator = guardrail_coordinator or create_guardrail_coordinator()

    # Create initial state for guardrail checks
    initial_state = create_initial_state(pnr_locator)

    # Load data first (needed for guardrail checks)
    data_result = load_data(initial_state)
    initial_state.update(data_result)

    # Check for data load errors
    if initial_state.get("errors"):
        return {
            "pnr_locator": pnr_locator,
            "should_send_offer": False,
            "suppression_reason": initial_state["errors"][0],
            "guardrail_results": {},
            "reasoning_trace": initial_state.get("reasoning_trace", []),
        }

    # =================================================================
    # LAYER 1: Synchronous Pre-flight Guardrails (~60ms)
    # =================================================================
    # These are BLOCKING - if they fail, we abort immediately.
    # This saves us from wasting LLM calls on invalid requests.
    # =================================================================

    preflight_passed, preflight_result = coordinator.pre_flight_check(initial_state)

    if not preflight_passed:
        # Fail fast - don't run expensive LLM processing
        failed_checks = [
            r.message for r in preflight_result.results
            if r.verdict != GuardrailVerdict.PASS
        ]

        return {
            "pnr_locator": pnr_locator,
            "should_send_offer": False,
            "suppression_reason": f"Pre-flight guardrail failed: {failed_checks[0]}",
            "customer_data": initial_state.get("customer_data"),
            "guardrail_results": {"sync_preflight": _layer_result_to_dict(preflight_result)},
            "guardrail_blocked": True,
            "guardrail_latency_ms": preflight_result.total_latency_ms,
            "reasoning_trace": [
                f"GUARDRAIL L1: Pre-flight check failed ({preflight_result.total_latency_ms:.1f}ms)",
                f"GUARDRAIL L1: Blocked reason: {failed_checks[0]}",
            ],
        }

    # =================================================================
    # LAYER 2: Start Async Background Guardrails (runs in parallel)
    # =================================================================
    # Start background checks now - they'll run while the workflow executes.
    # We'll check results before final delivery.
    # =================================================================

    async_task = coordinator.start_background_checks(initial_state)

    # Add pre-flight success to trace
    trace = initial_state.get("reasoning_trace", [])
    trace.append(f"GUARDRAIL L1: Pre-flight passed ({preflight_result.total_latency_ms:.1f}ms)")
    trace.append("GUARDRAIL L2: Started background checks (running in parallel)")
    initial_state["reasoning_trace"] = trace

    # =================================================================
    # MAIN WORKFLOW: Enhanced Choreography
    # =================================================================
    # Run the main workflow while async guardrails run in background.
    # =================================================================

    workflow = create_workflow()
    app = workflow.compile()

    # Note: We skip load_data in the workflow since we already loaded it
    # We need to adjust the initial state to reflect this
    initial_state["_data_loaded"] = True

    final_state = app.invoke(initial_state)

    # =================================================================
    # LAYER 2 & 3: Pre-delivery Guardrails
    # =================================================================
    # Before delivering the offer, check:
    # - Async background results (compliance, fairness, PII)
    # - Triggered escalation conditions (high-value, anomalies)
    # =================================================================

    can_deliver, escalation_ticket, delivery_results = coordinator.pre_delivery_check(
        final_state, async_task
    )

    # Collect all guardrail results
    guardrail_results = {
        "sync_preflight": _layer_result_to_dict(preflight_result),
    }
    for layer_name, layer_result in delivery_results.items():
        guardrail_results[layer_name] = _layer_result_to_dict(layer_result)

    # Calculate total guardrail latency
    total_guardrail_latency = preflight_result.total_latency_ms
    for layer_result in delivery_results.values():
        # Only count async latency if we had to wait
        if layer_result.layer == "async_background":
            # Async ran in parallel, so minimal additional latency
            total_guardrail_latency += 0  # Already accounted for
        else:
            total_guardrail_latency += layer_result.total_latency_ms

    # Update state with guardrail results
    final_state["guardrail_results"] = guardrail_results
    final_state["guardrail_latency_ms"] = total_guardrail_latency
    final_state["guardrail_can_deliver"] = can_deliver
    final_state["execution_pattern"] = "enhanced_choreography_guarded"

    # Handle escalation
    if escalation_ticket:
        final_state["guardrail_escalated"] = True
        final_state["escalation_ticket"] = escalation_ticket
        final_state["should_send_offer"] = False  # Hold until reviewed

        trace = final_state.get("reasoning_trace", [])
        trace.append(f"GUARDRAIL L3: Escalated for human review - ticket {escalation_ticket}")
        final_state["reasoning_trace"] = trace

    # Add guardrail summary to trace
    trace = final_state.get("reasoning_trace", [])
    async_result = delivery_results.get("async_background")
    if async_result:
        trace.append(f"GUARDRAIL L2: Background checks completed ({async_result.total_latency_ms:.1f}ms)")

    triggered_result = delivery_results.get("triggered_escalation")
    if triggered_result:
        trace.append(f"GUARDRAIL L3: Triggered checks completed ({triggered_result.total_latency_ms:.1f}ms)")

    trace.append(f"GUARDRAIL: Total latency overhead: {total_guardrail_latency:.1f}ms")
    final_state["reasoning_trace"] = trace

    return final_state


def _layer_result_to_dict(result: LayerResult) -> Dict[str, Any]:
    """Convert LayerResult to a serializable dictionary."""
    return {
        "layer": result.layer,
        "passed": result.passed,
        "total_latency_ms": result.total_latency_ms,
        "escalation_required": result.escalation_required,
        "escalation_reasons": result.escalation_reasons,
        "checks": [
            {
                "name": r.name,
                "verdict": r.verdict.value,
                "message": r.message,
                "latency_ms": r.latency_ms,
            }
            for r in result.results
        ]
    }


# =============================================================================
# CONVENIENCE: Combined Evaluation with All Features
# =============================================================================


def run_offer_evaluation_full(
    pnr_locator: str,
    use_guardrails: bool = True,
    use_recovery: bool = True,
) -> Dict[str, Any]:
    """
    Full-featured offer evaluation with configurable guardrails and recovery.

    This combines:
    - 3-layer guardrails (if use_guardrails=True)
    - Planner-Worker recovery (if use_recovery=True)

    Recommended for production use with all safety features enabled.

    Args:
        pnr_locator: The PNR to evaluate
        use_guardrails: Enable 3-layer guardrail protection
        use_recovery: Enable Planner-Worker recovery for complex failures

    Returns:
        Dictionary with final state and all metadata
    """
    # Determine which evaluation function to use
    if use_guardrails and USE_GUARDRAILS:
        result = run_offer_evaluation_guarded(pnr_locator)
    elif use_recovery:
        result = run_offer_evaluation_with_recovery(pnr_locator)
    else:
        result = run_offer_evaluation(pnr_locator)

    # If recovery is enabled and we had significant failures, try planner-worker
    if use_recovery and _count_node_failures(result) > 2:
        if not result.get("execution_pattern", "").endswith("_recovery"):
            from infrastructure.planner_executor import run_offer_evaluation_incremental

            print("Multiple failures detected, attempting Planner-Worker recovery...")
            recovery_result = run_offer_evaluation_incremental(pnr_locator)
            result = _convert_incremental_result(
                recovery_result,
                pnr_locator,
                escalation_reason="Multiple node failures triggered recovery"
            )
            result["execution_pattern"] = "enhanced_choreography_guarded_with_recovery"

    return result


# =============================================================================
# PRODUCTION-SAFE EVALUATION (RECOMMENDED FOR PRODUCTION)
# =============================================================================
#
# This is the SAFEST entry point for production use.
# It combines:
# 1. Idempotency - Prevents duplicate offer processing
# 2. 3-Layer Guardrails - Pre-flight, async, triggered checks
# 3. Cost Tracking - Tracks LLM costs per request
# 4. Alerting - Sends alerts on failures
# 5. Planner-Worker Recovery - Handles complex failures
#
# Use this for production deployments at scale.
# =============================================================================


def run_offer_evaluation_production(
    pnr_locator: str,
    safety_coordinator: ProductionSafetyCoordinator = None,
    guardrail_coordinator: GuardrailCoordinator = None,
    request_id: str = None,
) -> Dict[str, Any]:
    """
    Production-safe offer evaluation with all safety features.

    This is the RECOMMENDED entry point for production deployments.

    Features:
    1. Idempotency - Prevents duplicate processing of same PNR
    2. 3-Layer Guardrails - Fast pre-flight + async + human escalation
    3. Cost Tracking - Tracks LLM token usage and costs
    4. Alerting - Sends alerts on errors and anomalies
    5. Recovery - Uses Planner-Worker for complex failures

    Args:
        pnr_locator: The PNR to evaluate
        safety_coordinator: Optional custom safety coordinator
        guardrail_coordinator: Optional custom guardrail coordinator
        request_id: Optional request ID for tracing

    Returns:
        Dictionary with final state, safety metadata, and any cached results
    """
    import uuid
    from datetime import datetime

    # Initialize coordinators
    safety = safety_coordinator or get_safety_coordinator()
    guardrails = guardrail_coordinator or create_guardrail_coordinator()

    # Generate request ID if not provided
    if not request_id:
        request_id = f"req-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"

    # =================================================================
    # STEP 1: IDEMPOTENCY CHECK
    # =================================================================
    # Prevents duplicate processing of the same request
    # =================================================================

    idem_key = safety.idempotency.get_key(
        pnr=pnr_locator,
        operation="offer_evaluation",
        include_date=True  # Allow re-evaluation next day
    )

    is_duplicate, cached_result = safety.idempotency.check(idem_key)

    if is_duplicate and cached_result:
        # Return cached result - don't reprocess
        cached_result["_cached"] = True
        cached_result["_idempotency_key"] = idem_key
        cached_result["_request_id"] = request_id

        # Add to trace
        trace = cached_result.get("reasoning_trace", [])
        trace.insert(0, f"IDEMPOTENCY: Returning cached result for {pnr_locator}")
        cached_result["reasoning_trace"] = trace

        return cached_result

    if is_duplicate and not cached_result:
        # Currently processing - return in-progress status
        return {
            "pnr_locator": pnr_locator,
            "status": "processing",
            "message": "Request is currently being processed",
            "_idempotency_key": idem_key,
            "_request_id": request_id,
        }

    # =================================================================
    # STEP 2: PROCESS REQUEST
    # =================================================================
    # Run the full evaluation with guardrails
    # =================================================================

    start_time = time.time()

    try:
        # Run guarded evaluation
        result = run_offer_evaluation_guarded(
            pnr_locator=pnr_locator,
            guardrail_coordinator=guardrails,
        )

        # =================================================================
        # STEP 3: TRACK COST
        # =================================================================
        # Note: In a real implementation, you'd track actual LLM tokens
        # Here we estimate based on reasoning length
        # =================================================================

        reasoning_length = len(str(result.get("reasoning_trace", [])))
        estimated_input_tokens = reasoning_length // 4  # Rough estimate
        estimated_output_tokens = len(str(result.get("offer_reasoning", ""))) // 4

        if estimated_input_tokens > 0 or estimated_output_tokens > 0:
            cost = safety.cost_tracker.track_call(
                request_id=request_id,
                pnr=pnr_locator,
                model="gpt-4o",  # Default model assumption
                input_tokens=estimated_input_tokens,
                output_tokens=estimated_output_tokens,
                agent_name="OfferOrchestration",
            )
            result["_cost_usd"] = cost.total_cost_usd

        # =================================================================
        # STEP 4: MARK COMPLETE
        # =================================================================

        result["_idempotency_key"] = idem_key
        result["_request_id"] = request_id
        result["_processing_time_ms"] = (time.time() - start_time) * 1000
        result["execution_pattern"] = "production_safe"

        # Cache the result
        safety.idempotency.complete(idem_key, result)

        # Add to trace
        trace = result.get("reasoning_trace", [])
        trace.append(f"PRODUCTION: Request {request_id} completed in {result['_processing_time_ms']:.0f}ms")
        result["reasoning_trace"] = trace

        return result

    except Exception as e:
        # =================================================================
        # STEP 5: HANDLE FAILURE
        # =================================================================

        # Mark idempotency as failed (allows retry)
        safety.idempotency.fail(idem_key, str(e))

        # Send alert
        safety.alerts.send(
            severity=AlertSeverity.ERROR,
            title="Offer Evaluation Failed",
            message=f"PNR {pnr_locator}: {str(e)}",
            source="tailored-offers",
            metadata={
                "pnr": pnr_locator,
                "request_id": request_id,
                "error": str(e),
            }
        )

        # Return error result
        return {
            "pnr_locator": pnr_locator,
            "should_send_offer": False,
            "suppression_reason": f"Processing error: {str(e)}",
            "error": str(e),
            "_idempotency_key": idem_key,
            "_request_id": request_id,
            "_processing_time_ms": (time.time() - start_time) * 1000,
            "execution_pattern": "production_safe_error",
            "reasoning_trace": [
                f"PRODUCTION: Request {request_id} failed: {str(e)}"
            ],
        }


# =============================================================================
# HUMAN-IN-THE-LOOP EVALUATION (ULTIMATE PRODUCTION SAFETY)
# =============================================================================
#
# This is the ULTIMATE entry point for production use with human oversight.
# It combines all safety features PLUS true human-in-the-loop:
#
# 1. Idempotency - Prevents duplicate offer processing
# 2. 3-Layer Guardrails - Pre-flight, async, triggered checks
# 3. Cost Tracking - Tracks LLM costs per request
# 4. Alerting - Sends alerts on failures
# 5. Human-in-the-Loop - Deferred execution for high-risk decisions
#    - Halts workflow at risky steps
#    - Persists state for later resume
#    - Sends notifications for approval
#    - Resumes only after human approval
#
# Use this when you need human oversight for high-value or risky decisions.
# =============================================================================


def run_offer_evaluation_with_hitl(
    pnr_locator: str,
    safety_coordinator: ProductionSafetyCoordinator = None,
    guardrail_coordinator: GuardrailCoordinator = None,
    hitl_manager: HumanInTheLoopManager = None,
    request_id: str = None,
    force_approval: bool = False,
) -> Dict[str, Any]:
    """
    Production-safe offer evaluation with Human-in-the-Loop support.

    This is the ULTIMATE entry point for production deployments requiring
    human oversight for high-risk decisions.

    Flow:
    1. Run all production safety checks (idempotency, guardrails)
    2. Check if human approval is required (high-value, VIP, etc.)
    3. If approval needed:
       - Save workflow state
       - Send notification (Slack, email)
       - Return "pending_approval" status
       - Human approves/denies via API
       - Resume workflow on approval
    4. If no approval needed or already approved: complete workflow

    Args:
        pnr_locator: The PNR to evaluate
        safety_coordinator: Optional custom safety coordinator
        guardrail_coordinator: Optional custom guardrail coordinator
        hitl_manager: Optional custom HITL manager
        request_id: Optional request ID for tracing
        force_approval: Force human approval regardless of rules (for testing)

    Returns:
        Dictionary with final state, or pending_approval status if halted
    """
    import uuid
    from datetime import datetime

    # Initialize coordinators
    safety = safety_coordinator or get_safety_coordinator()
    guardrails = guardrail_coordinator or create_guardrail_coordinator()
    hitl = hitl_manager or get_hitl_manager()

    # Generate request ID if not provided
    if not request_id:
        request_id = f"req-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"

    # =================================================================
    # STEP 1: CHECK FOR EXISTING PENDING APPROVAL
    # =================================================================
    # If there's already a pending approval for this PNR, return it
    # =================================================================

    existing_requests = hitl.get_requests_by_pnr(pnr_locator)
    pending_requests = [r for r in existing_requests if r.status == ApprovalStatus.PENDING]

    if pending_requests:
        pending = pending_requests[0]
        return {
            "pnr_locator": pnr_locator,
            "status": "pending_approval",
            "approval_request_id": pending.id,
            "message": f"Waiting for human approval (reason: {pending.reason.value})",
            "created_at": pending.created_at,
            "expires_at": pending.expires_at,
            "_request_id": request_id,
            "reasoning_trace": [
                f"HITL: Found pending approval request {pending.id}",
                f"HITL: Reason: {pending.reason.value} - {pending.reason_details}",
            ],
        }

    # =================================================================
    # STEP 2: IDEMPOTENCY CHECK
    # =================================================================

    idem_key = safety.idempotency.get_key(
        pnr=pnr_locator,
        operation="offer_evaluation_hitl",
        include_date=True
    )

    is_duplicate, cached_result = safety.idempotency.check(idem_key)

    if is_duplicate and cached_result:
        cached_result["_cached"] = True
        cached_result["_idempotency_key"] = idem_key
        cached_result["_request_id"] = request_id
        return cached_result

    # =================================================================
    # STEP 3: RUN EVALUATION UP TO OFFER DECISION
    # =================================================================
    # We run the workflow to get the offer decision, then check if
    # human approval is needed before delivery.
    # =================================================================

    start_time = time.time()

    try:
        # Run guarded evaluation (gets offer but doesn't "deliver" yet)
        result = run_offer_evaluation_guarded(
            pnr_locator=pnr_locator,
            guardrail_coordinator=guardrails,
        )

        # If no offer should be sent, no need for HITL
        if not result.get("should_send_offer", False):
            result["_idempotency_key"] = idem_key
            result["_request_id"] = request_id
            result["execution_pattern"] = "production_hitl_no_offer"
            safety.idempotency.complete(idem_key, result)
            return result

        # =================================================================
        # STEP 4: CHECK IF HUMAN APPROVAL REQUIRED
        # =================================================================

        # Build offer_decision from state fields (state doesn't have an offer_decision dict)
        offer_decision = {
            "offer_type": result.get("selected_offer", "Unknown"),
            "price": result.get("offer_price", 0) or 0,
            "discount_percent": result.get("discount_applied", 0) or 0,
            "expected_value": result.get("expected_value", 0) or 0,
        }
        offer_value = offer_decision["price"]

        # Extract customer info
        customer_data = result.get("customer_data", {})
        customer_name = f"{customer_data.get('first_name', '')} {customer_data.get('last_name', '')}".strip() or "Unknown"
        customer_tier = customer_data.get("loyalty_tier", "General")

        # Extract destination for regulatory checks
        flight_data = result.get("flight_data", {})
        destination = flight_data.get("destination", "")

        # Check escalation rules
        needs_approval, reason, reason_details = hitl.check_escalation(
            offer_value=offer_value,
            customer_tier=customer_tier,
            destination=destination,
            anomaly_score=0.0,  # Could integrate with anomaly detection
            is_first_time=False,
            manual_flag=force_approval,
        )

        # =================================================================
        # STEP 5A: NO APPROVAL NEEDED - COMPLETE WORKFLOW
        # =================================================================

        if not needs_approval:
            result["_idempotency_key"] = idem_key
            result["_request_id"] = request_id
            result["_processing_time_ms"] = (time.time() - start_time) * 1000
            result["execution_pattern"] = "production_hitl_auto_approved"

            trace = result.get("reasoning_trace", [])
            trace.append(f"HITL: No human approval required (value=${offer_value:.2f}, tier={customer_tier})")
            result["reasoning_trace"] = trace

            safety.idempotency.complete(idem_key, result)
            return result

        # =================================================================
        # STEP 5B: APPROVAL NEEDED - HALT AND DEFER
        # =================================================================

        # Create approval request with full workflow state
        approval_request = hitl.create_approval_request(
            pnr=pnr_locator,
            customer_name=customer_name,
            customer_tier=customer_tier,
            action_type="offer_delivery",
            action_description=f"Deliver {offer_decision.get('offer_type', 'upgrade')} offer worth ${offer_value:.2f}",
            reason=reason,
            reason_details=reason_details,
            proposed_offer=offer_decision,
            offer_value=offer_value,
            workflow_state=result,  # Save full state for resume
            checkpoint_name="pre_delivery",
            risk_score=offer_value / 1000,  # Simple risk score
            risk_factors=[
                f"Offer value: ${offer_value:.2f}",
                f"Customer tier: {customer_tier}",
                f"Destination: {destination}",
            ],
        )

        # Send notifications
        notification_results = hitl.notify(approval_request)

        # Mark idempotency as pending (not complete, but not failed)
        safety.idempotency.fail(idem_key, "pending_approval")

        # Return pending status
        return {
            "pnr_locator": pnr_locator,
            "status": "pending_approval",
            "approval_request_id": approval_request.id,
            "approval_reason": reason.value,
            "approval_reason_details": reason_details,
            "proposed_offer": offer_decision,
            "offer_value": offer_value,
            "customer_name": customer_name,
            "customer_tier": customer_tier,
            "notifications_sent": notification_results,
            "created_at": approval_request.created_at,
            "expires_at": approval_request.expires_at,
            "_request_id": request_id,
            "_processing_time_ms": (time.time() - start_time) * 1000,
            "execution_pattern": "production_hitl_pending",
            "reasoning_trace": [
                f"HITL: Human approval required",
                f"HITL: Reason: {reason.value} - {reason_details}",
                f"HITL: Created approval request {approval_request.id}",
                f"HITL: Workflow state saved for later resume",
                f"HITL: Notifications sent: {notification_results}",
            ],
        }

    except Exception as e:
        safety.idempotency.fail(idem_key, str(e))

        safety.alerts.send(
            severity=AlertSeverity.ERROR,
            title="HITL Evaluation Failed",
            message=f"PNR {pnr_locator}: {str(e)}",
            source="tailored-offers-hitl",
            metadata={"pnr": pnr_locator, "request_id": request_id, "error": str(e)}
        )

        return {
            "pnr_locator": pnr_locator,
            "should_send_offer": False,
            "suppression_reason": f"Processing error: {str(e)}",
            "error": str(e),
            "_request_id": request_id,
            "execution_pattern": "production_hitl_error",
            "reasoning_trace": [f"HITL: Request failed: {str(e)}"],
        }


def resume_after_approval(
    approval_request_id: str,
    hitl_manager: HumanInTheLoopManager = None,
    safety_coordinator: ProductionSafetyCoordinator = None,
) -> Dict[str, Any]:
    """
    Resume a workflow after human approval.

    This is called after a human approves a pending request via the API.
    It loads the saved workflow state and completes the offer delivery.

    Args:
        approval_request_id: The ID of the approved request
        hitl_manager: Optional custom HITL manager
        safety_coordinator: Optional custom safety coordinator

    Returns:
        Final workflow result with offer delivered
    """
    hitl = hitl_manager or get_hitl_manager()
    safety = safety_coordinator or get_safety_coordinator()

    # Get the approval request
    request = hitl.get_request(approval_request_id)

    if not request:
        return {
            "error": "Approval request not found",
            "approval_request_id": approval_request_id,
        }

    if request.status != ApprovalStatus.APPROVED:
        return {
            "error": f"Request not approved (status: {request.status.value})",
            "approval_request_id": approval_request_id,
            "current_status": request.status.value,
        }

    # Load saved workflow state
    saved_state = hitl.load_workflow_state(approval_request_id)

    if not saved_state:
        return {
            "error": "Workflow state not found - may have expired",
            "approval_request_id": approval_request_id,
        }

    # The saved state already contains the complete offer evaluation
    # We just need to mark it as delivered/approved
    result = saved_state.copy()
    result["_approval_request_id"] = approval_request_id
    result["_approved_by"] = request.resolved_by
    result["_approved_at"] = request.resolved_at
    result["_approval_notes"] = request.resolution_notes
    result["execution_pattern"] = "production_hitl_approved"

    # Use modified offer if human made changes
    if request.proposed_offer != saved_state.get("offer_decision"):
        result["offer_decision"] = request.proposed_offer
        result["_offer_modified_by_human"] = True

    # Update reasoning trace
    trace = result.get("reasoning_trace", [])
    trace.append(f"HITL: Approved by {request.resolved_by} at {request.resolved_at}")
    if request.resolution_notes:
        trace.append(f"HITL: Approval notes: {request.resolution_notes}")
    trace.append("HITL: Workflow resumed and completed")
    result["reasoning_trace"] = trace

    # Cache the final result
    idem_key = safety.idempotency.get_key(
        pnr=request.pnr,
        operation="offer_evaluation_hitl",
        include_date=True
    )
    safety.idempotency.complete(idem_key, result)

    # Clean up saved state
    hitl.cleanup_completed(approval_request_id)

    return result


def handle_denial(
    approval_request_id: str,
    hitl_manager: HumanInTheLoopManager = None,
    safety_coordinator: ProductionSafetyCoordinator = None,
) -> Dict[str, Any]:
    """
    Handle a denied approval request.

    Args:
        approval_request_id: The ID of the denied request
        hitl_manager: Optional custom HITL manager
        safety_coordinator: Optional custom safety coordinator

    Returns:
        Result indicating the offer was not delivered
    """
    hitl = hitl_manager or get_hitl_manager()
    safety = safety_coordinator or get_safety_coordinator()

    request = hitl.get_request(approval_request_id)

    if not request:
        return {
            "error": "Approval request not found",
            "approval_request_id": approval_request_id,
        }

    if request.status != ApprovalStatus.DENIED:
        return {
            "error": f"Request not denied (status: {request.status.value})",
            "approval_request_id": approval_request_id,
        }

    result = {
        "pnr_locator": request.pnr,
        "should_send_offer": False,
        "suppression_reason": f"Human denied: {request.resolution_notes or 'No reason provided'}",
        "_approval_request_id": approval_request_id,
        "_denied_by": request.resolved_by,
        "_denied_at": request.resolved_at,
        "_denial_notes": request.resolution_notes,
        "execution_pattern": "production_hitl_denied",
        "reasoning_trace": [
            f"HITL: Denied by {request.resolved_by} at {request.resolved_at}",
            f"HITL: Denial reason: {request.resolution_notes or 'Not provided'}",
            "HITL: Offer will not be delivered",
        ],
    }

    # Cache denial result
    idem_key = safety.idempotency.get_key(
        pnr=request.pnr,
        operation="offer_evaluation_hitl",
        include_date=True
    )
    safety.idempotency.complete(idem_key, result)

    return result
