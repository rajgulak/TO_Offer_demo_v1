# Architecture Decisions Record (ADR)

## Tailored Offers Agent Framework


---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Core Architecture Decisions](#core-architecture-decisions)
3. [Agentic Patterns](#agentic-patterns)
4. [Production Safety](#production-safety)
5. [Infrastructure Components](#infrastructure-components)
6. [API & Workflow Entry Points](#api--workflow-entry-points)
7. [File Structure](#file-structure)

---

## Executive Summary

This document captures all architectural decisions made in building the Tailored Offers Agent Framework - a production-grade agentic AI system for personalized airline offer generation.

### Key Principles

1. **Bounded Autonomy**: Agents can reason but respect hard guardrails
2. **Explainability First**: Every decision is traceable with full reasoning
3. **Production Safety**: Idempotency, cost tracking, alerting before scale
4. **Latency Optimization**: 3-layer guardrails minimize response time
5. **Graceful Degradation**: System continues operating under failures

### What Makes This Best-in-Class

| Feature | Implementation | Why It Matters |
|---------|---------------|----------------|
| Dual Execution | Choreography + Planner-Worker | Fast path + intelligent recovery |
| 3-Layer Guardrails | Sync/Async/Triggered | 60ms vs 500ms latency |
| Production Safety | Idempotency + Cost + Alerts | No duplicates, cost visibility |
| Feedback Loop | Outcome → Agent learning | Continuous improvement |
| Memory System | 4 memory types | Context-aware decisions |

---

## Core Architecture Decisions

### ADR-001: Workflow vs Agent vs LLM Call

**Decision**: Use a decision tree to determine component type for each step.

```
Does it need to EXPLAIN why?
├─ NO → Is it generative text?
│   ├─ YES → LLM Call (just generate, no reasoning)
│   └─ NO  → Workflow (just code, log the result)
└─ YES → Agent (returns decision + reasoning)
```

**Applied to Tailored Offers**:

| Step | Needs Explanation? | Generative? | Type |
|------|-------------------|-------------|------|
| Customer Intelligence | No (yes/no check) | No | ⚡ Workflow |
| Flight Optimization | No (data lookup) | No | ⚡ Workflow |
| **Offer Orchestration** | **Yes (15+ factors)** | No | **🧠 Agent** |
| Personalization | No (just text) | Yes | ✨ LLM Call |
| Channel & Timing | No (rule-based) | No | ⚡ Workflow |
| Measurement | No (random A/B) | No | ⚡ Workflow |

**Rationale**: Only 1 out of 6 steps needs an "Agent" - the complex multi-factor decision. This minimizes LLM costs while maximizing explainability where it matters.

---

### ADR-002: Hardcoded Graph vs LLM Supervisor

**Decision**: Use hardcoded LangGraph orchestration, NOT LLM supervisor.

| Aspect | LLM Supervisor | Hardcoded Graph (Chosen) |
|--------|---------------|--------------------------|
| Routing | LLM decides next step | Code defines sequence |
| Cost | LLM call for every decision | LLM only where needed |
| Predictability | Variable | Consistent |
| Debugging | Trace LLM decisions | Clear execution path |
| Testing | Hard to test | Unit testable |

**Implementation**:
```python
# LangGraph defines sequence - no LLM routing
graph = StateGraph()
graph.add_node("customer_intel", customer_workflow)
graph.add_node("flight_opt", flight_workflow)
graph.add_node("offer", offer_agent)  # Only agent
graph.add_node("personalize", llm_call)
graph.add_edge("customer_intel", "flight_opt")
graph.add_edge("flight_opt", "offer")
graph.add_edge("offer", "personalize")
```

---

### ADR-003: Dual Execution Pattern

**Decision**: Enhanced Choreography (primary) + Planner-Worker (secondary/recovery).

```
┌─────────────────────────────────────────────────────────────────┐
│           PATTERN 1: Enhanced Choreography (Primary)            │
│                      Happy Path + Simple Failures               │
│                                                                 │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                  │
│  │  Node A  │───→│  Node B  │───→│  Node C  │───→ ...          │
│  │(resilient)│   │(resilient)│   │(resilient)│                  │
│  └──────────┘    └──────────┘    └──────────┘                  │
│       │              │              │                           │
│       ▼              ▼              ▼                           │
│   Retry with     Retry with     Retry with                     │
│   backoff        backoff        backoff                        │
└──────────────────────────────────────────────────────────────────┘
                           │ If multiple failures
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│           PATTERN 2: Planner-Worker (Secondary)                 │
│                 Complex Recovery Scenarios                      │
│                                                                 │
│     ┌──────────┐         ┌──────────┐                          │
│     │ PLANNER  │◄────────│  STATE   │                          │
│     └────┬─────┘         └────▲─────┘                          │
│          │ "Do X"             │ Result + Recommendation        │
│          ▼                    │                                 │
│     ┌──────────┐              │                                 │
│     │  WORKER  │──────────────┘                                 │
│     └──────────┘                                                │
└─────────────────────────────────────────────────────────────────┘
```

**When to Use Each**:

| Scenario | Pattern | Why |
|----------|---------|-----|
| Normal request | Choreography | Fast, predictable |
| Single timeout | Choreography | Node retry handles it |
| Multiple nodes failing | Planner-Worker | Intelligent recovery |
| Need human decision | Planner-Worker | Escalation support |

---

### ADR-004: 3-Layer Guardrail Architecture

**Decision**: Layer guardrails by timing requirements to optimize latency.

**Problem**: Running all guardrails inline adds ~500ms latency.

**Solution**:
- Layer 1 (Sync): ~60ms - MUST pass before LLM
- Layer 2 (Async): ~0ms impact - runs in parallel
- Layer 3 (Triggered): human-in-loop for exceptions

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 1: SYNCHRONOUS PRE-FLIGHT (~40-70ms)                    │
│  ──────────────────────────────────────────                     │
│  BLOCKING: If fails → abort immediately (save LLM costs)       │
│                                                                 │
│    • Input validation (PNR format)                              │
│    • Customer suppression check                                 │
│    • Marketing consent check                                    │
│    • Rate limiting (daily offer quota)                          │
│    • Time-to-departure (>6 hours)                              │
│    • Budget check (segment allocation)                          │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 2: ASYNCHRONOUS BACKGROUND (~200-500ms)                 │
│  ──────────────────────────────────────────────                 │
│  NON-BLOCKING: Runs in PARALLEL with main workflow             │
│                                                                 │
│    • Compliance audit trail logging                             │
│    • Offer value validation (EV, discount limits)               │
│    • Fairness monitoring (bias detection)                       │
│    • Historical frequency check (offer fatigue)                 │
│    • PII handling verification                                  │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 3: TRIGGERED ESCALATION (Human-in-Loop)                 │
│  ──────────────────────────────────────────────                 │
│  ESCALATES: Creates ticket for human approval                  │
│                                                                 │
│    • High-value offers (>$500)                                 │
│    • Anomaly detection (unusual patterns)                       │
│    • Regulatory flags (GDPR routes, etc.)                      │
│    • Override requests                                          │
└─────────────────────────────────────────────────────────────────┘
```

**Latency Comparison**:
| Approach | Latency Impact |
|----------|---------------|
| All inline (naive) | +500ms |
| 3-Layer Architecture | +60ms (sync) + 0ms (async in parallel) |

---

## Agentic Patterns

### Memory System

Four types of memory for context-aware decisions:

| Memory Type | Purpose | TTL | Storage |
|-------------|---------|-----|---------|
| ConversationMemory | Current session context | Session | In-memory |
| CustomerMemory | Historical interactions | 30 days | Redis |
| OfferMemory | Past decisions & outcomes | 90 days | Redis |
| LearningMemory | Patterns from success/failure | Persistent | Redis |

**Implementation**: `infrastructure/memory.py`

### Incremental Planner-Worker

Correct pattern: Plan ONE step → Execute → Observe → Re-plan

```
Plan(step 1) → Execute → Result{data, recommendation}
    ↓
Observe → Plan(step 2) → Execute → Result{data, recommendation}
    ↓
Observe → Plan(step 3) → ... (repeat until goal or abort)
```

**Worker Recommendations**:
- `CONTINUE` - proceed to next step
- `RETRY` - retry current step with backoff
- `SIMPLIFY` - reduce task complexity
- `ESCALATE` - require human intervention
- `ABORT` - stop processing

**Implementation**: `infrastructure/planner_executor.py`

### Feedback Loop

Complete cycle: Data → Agent → Offer → Customer → OUTCOME → Back to Agent

| Component | Purpose |
|-----------|---------|
| FeedbackManager | Core interface |
| OfferOutcome | Captures expected vs actual |
| CalibrationReport | Prediction quality analysis |
| AgentFeedback | Improvement recommendations |

**Features**:
- Outcome capture (accepted, rejected, expired)
- Calibration analysis (ECE, Brier score)
- Automatic confidence adjustment
- Segment-specific analysis

**Implementation**: `infrastructure/feedback.py`

---

## Production Safety

### ADR-005: Idempotency Keys

**Decision**: Prevent duplicate processing with idempotency manager.

**Problem**: Same request could process 2-3x without idempotency.

**Solution**:
```python
class IdempotencyManager:
    def get_key(self, pnr: str, operation: str) -> str:
        # Include date to allow daily re-evaluation
        return f"idempotency:{operation}:{pnr}:{date}"

    def check(self, key: str) -> Tuple[bool, Optional[Dict]]:
        # Returns (is_duplicate, cached_result)

    def complete(self, key: str, result: Dict):
        # Cache result for future duplicates
```

**Implementation**: `infrastructure/production_safety.py`

### ADR-006: Cost Tracking

**Decision**: Track per-request LLM costs with model-specific pricing.

**Problem**: No visibility into LLM spend led to $47k in 3 weeks (industry example).

**Solution**:
```python
class CostTracker:
    PRICING = {
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "claude-3-sonnet": {"input": 0.003, "output": 0.015},
    }

    def track_call(self, request_id, model, input_tokens, output_tokens):
        # Calculate and log cost
        # Update Prometheus metrics
        # Store for analysis
```

**Implementation**: `infrastructure/production_safety.py`

### ADR-007: Alert Manager

**Decision**: Proactive alerting for error rates and cost anomalies.

**Thresholds**:
- Error rate > 5% → Warning
- Hourly cost > $100 → Critical

**Channels**:
- Slack (all alerts)
- PagerDuty (critical only)
- Structured logs (always)

**Implementation**: `infrastructure/production_safety.py`

### ADR-008: Human-in-the-Loop (HITL)

**Decision**: Implement true deferred execution for high-risk decisions.

**Problem**: Some decisions are too risky for full automation:
- High-value offers (>$500)
- VIP customers (ConciergeKey, Executive Platinum)
- Regulatory routes (GDPR)
- Anomalous patterns

**Solution**: Deliberately halt automated flows, persist state, resume after human approval.

```
┌─────────────────────────────────────────────────────────────────┐
│                 Human-in-the-Loop Flow                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Request → Evaluate → Check Rules → [NEEDS APPROVAL?]          │
│                                           │                     │
│                          NO ←─────────────┼──────────→ YES      │
│                           │               │              │      │
│                           ▼               │              ▼      │
│                      Complete             │       Save State    │
│                      Workflow             │       Send Notification
│                           │               │       Return "pending"
│                           │               │              │      │
│                           │               │      ┌───────▼──────┐
│                           │               │      │ Human Review │
│                           │               │      │   Approve?   │
│                           │               │      └───────┬──────┘
│                           │               │        YES   │   NO  │
│                           │               │         │    │    │  │
│                           │               │    Load │    │  Clean│
│                           │               │    State│    │  Up   │
│                           │               │         ▼    │    ▼  │
│                           │               │     Resume   │  Deny │
│                           ▼               ▼         ▼    ▼    ▼  │
│                       [FINAL RESULT]                            │
└─────────────────────────────────────────────────────────────────┘
```

**Escalation Rules** (in backend, NOT LLM):
```python
class EscalationRules:
    high_value_threshold = 500.0  # Offers > $500
    vip_tiers = ["ConciergeKey", "Executive Platinum"]
    anomaly_threshold = 0.8
    regulatory_routes = ["EU", "UK", "GDPR"]
```

**Key Components**:
| Component | Purpose |
|-----------|---------|
| `ApprovalRequest` | Captures request context and proposed action |
| `StateStore` | Persists workflow state for later resume |
| `ApprovalStore` | Manages pending/approved/denied requests |
| `NotificationService` | Slack, email, PagerDuty notifications |
| `EscalationRules` | Backend rules for when to escalate |
| `HumanInTheLoopManager` | Main orchestration interface |

**API Flow**:
```
1. GET  /api/pnrs/{pnr}/evaluate-hitl  → May return "pending_approval"
2. GET  /api/approvals/pending         → List pending approvals
3. POST /api/approvals/{id}/approve    → Human approves
4. POST /api/approvals/{id}/resume     → Complete workflow
```

**Implementation**: `infrastructure/human_in_loop.py`

---

## Infrastructure Components

### Observability Stack

| Component | Tool | File |
|-----------|------|------|
| Logging | structlog | `infrastructure/logging.py` |
| Metrics | Prometheus | `infrastructure/metrics.py` |
| Tracing | LangSmith/LangFuse | `infrastructure/tracing.py` |
| Validation | Custom | `infrastructure/validation.py` |

### Resilience Stack

| Component | Tool | File |
|-----------|------|------|
| Retry | tenacity | `infrastructure/retry.py` |
| Circuit Breaker | pybreaker | `infrastructure/retry.py` |
| Timeout | configurable | env vars |

### Prompt Management

| Feature | Implementation |
|---------|---------------|
| Versioning | PromptRegistry with version tracking |
| A/B Testing | Treatment percentage per prompt |
| Rollback | Instant version switch |

**File**: `config/prompts.py`

---

## API & Workflow Entry Points

### Workflow Functions

| Function | Features | Use Case |
|----------|----------|----------|
| `run_offer_evaluation()` | Basic | Testing |
| `run_offer_evaluation_guarded()` | + 3-Layer Guardrails | Staging |
| `run_offer_evaluation_with_recovery()` | + Planner-Worker fallback | Production |
| `run_offer_evaluation_production()` | + Idempotency + Cost | Production |
| `run_offer_evaluation_with_hitl()` | + Human-in-the-Loop | **Ultimate (Recommended)** |

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/pnrs/{pnr}/evaluate` | GET | Evaluate single PNR (SSE) |
| `/api/pnrs/{pnr}/evaluate-hitl` | GET | Evaluate with HITL (may halt) |
| `/api/outcomes` | POST | Record offer outcome |
| `/api/outcomes/{pnr}` | GET | Get outcome for PNR |
| `/api/calibration` | GET | Calibration report |
| `/api/feedback/{agent}` | GET | Agent-specific feedback |
| `/api/approvals/pending` | GET | List pending approvals |
| `/api/approvals/{id}` | GET | Get approval details |
| `/api/approvals/{id}/approve` | POST | Approve request |
| `/api/approvals/{id}/deny` | POST | Deny request |
| `/api/approvals/{id}/resume` | POST | Resume after approval |

---

## File Structure

```
tailored-offers-demo/
├── agents/
│   ├── workflow.py              # Main orchestration (all entry points)
│   ├── customer_intelligence.py # Customer eligibility workflow
│   ├── offer_orchestration.py   # 🧠 THE Agent (complex decisions)
│   ├── flight_optimization.py   # Flight data workflow
│   ├── channel_timing.py        # Delivery optimization workflow
│   ├── personalization.py       # ✨ LLM Call (text generation)
│   └── measurement.py           # A/B assignment workflow
│
├── infrastructure/
│   ├── __init__.py              # All exports
│   ├── logging.py               # Structured logging (structlog)
│   ├── metrics.py               # Prometheus metrics
│   ├── tracing.py               # LangSmith/LangFuse
│   ├── human_in_loop.py         # HITL (deferred execution, approvals)
│   ├── retry.py                 # Retry + Circuit breaker
│   ├── validation.py            # LLM response validation
│   ├── memory.py                # 4-type memory system
│   ├── planner_executor.py      # Incremental planner-worker
│   ├── feedback.py              # Outcome capture + learning
│   ├── guardrails.py            # 3-Layer architecture
│   └── production_safety.py     # Idempotency + Cost + Alerts
│
├── config/
│   ├── settings.py              # Environment config
│   └── prompts.py               # Prompt versioning + A/B
│
├── tools/
│   ├── data_tools.py            # MCP tool implementations
│   └── mcp_client.py            # MCP client wrapper
│
├── api/
│   └── routes.py                # FastAPI endpoints
│
├── frontend/
│   └── src/components/
│       ├── ArchitectureOverview.tsx   # Architecture visualization
│       ├── PipelineVisualization.tsx  # Pipeline animation
│       └── InteractiveTutorial.tsx    # Guided tour
│
└── docs/
    ├── ARCHITECTURE_DECISIONS.md      # This file
    ├── AGENTIC_AI_ASSESSMENT.md       # Code quality assessment
    └── PRODUCTION_READINESS_ASSESSMENT.md # 7-layer framework
```

---

## Quick Reference

### Production Deployment Checklist

- [ ] Set `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`
- [ ] Configure Redis for memory/idempotency (or use in-memory for dev)
- [ ] Set alert webhooks: `SLACK_WEBHOOK_URL`, `PAGERDUTY_ROUTING_KEY`
- [ ] Configure cost thresholds in environment
- [ ] Enable LangSmith tracing: `LANGSMITH_API_KEY`
- [ ] Run health check: `GET /health`

### Code Snippet: Full Production Call

```python
from agents.workflow import run_offer_evaluation_production
from infrastructure import get_safety_coordinator, create_guardrail_coordinator

# Initialize (once at startup)
safety = get_safety_coordinator()
guardrails = create_guardrail_coordinator()

# Process request
result = run_offer_evaluation_production(
    pnr_locator="ABC123",
    safety_coordinator=safety,
    guardrail_coordinator=guardrails,
    request_id="req-uuid-here"
)

# Result includes:
# - offer_decision (with full reasoning)
# - personalized_message
# - channel & timing
# - cost_tracked (dollars)
# - guardrail_results
# - idempotency_status
```

---
