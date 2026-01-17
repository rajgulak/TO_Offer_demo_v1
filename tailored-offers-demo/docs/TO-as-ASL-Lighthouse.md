# Tailored Offers as ASL Lighthouse Project

**Proposal: Use TO to Validate ASL Patterns Before Platform Investment**

---

## Executive Summary

The ASL v1 proposal is architecturally sound but carries significant execution risk due to scope and timeline. We propose using **Tailored Offers (TO) as the lighthouse project** that validates ASL concepts in production before building the full platform.

**Key insight:** TO already implements core ASL patterns. Rather than building ASL first and porting TO to it, we should:
1. Ship TO with production-grade patterns
2. Extract what works into ASL v0.1
3. Onboard the next agent using those patterns
4. Iterate toward full ASL

This approach de-risks ASL by proving patterns with real business value first.

---

## TO Architecture Already Maps to ASL Concepts

| ASL Concept | TO Implementation | Status |
|-------------|-------------------|--------|
| **Domain Tool Gateway** | MCP Tools (`get_customer()`, `get_flight()`, `get_ml_scores()`) | ✅ Working |
| **Agent Contract** | Structured output: `{decision, reasoning, data_used}` | ✅ Working |
| **Typed Tools** | Tool schemas with validation | ✅ Working |
| **Multi-runtime** | Workflows (4) + Agent (1) + LLM Call (1) | ✅ Working |
| **Durable Workflows** | LangGraph now, Temporal planned | 🔄 In Progress |
| **Audit/Observability** | Reasoning traces, decision logging | 🔄 In Progress |
| **Policy Enforcement** | Suppression rules, consent checks | ✅ Working |
| **Retrieval with Provenance** | Data sources tracked in reasoning | ✅ Working |

**Bottom line:** TO is 60-70% of an ASL-compliant agent already.

---

## Architecture Alignment: TO → ASL

### Current TO Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    TO Offer Prototype                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ Customer │  │ Flight   │  │ Offer    │  │ Personal-│    │
│  │ Intel    │  │ Optim    │  │ Orchestr │  │ ization  │    │
│  │ WORKFLOW │  │ WORKFLOW │  │ AGENT    │  │ LLM CALL │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
│       │             │             │             │           │
│       └─────────────┴──────┬──────┴─────────────┘           │
│                            │                                │
│                    ┌───────▼───────┐                        │
│                    │   MCP Tools   │ ← ASL "Domain Tool     │
│                    │   (Typed,     │   Gateway" pattern     │
│                    │   Validated)  │                        │
│                    └───────┬───────┘                        │
│                            │                                │
└────────────────────────────┼────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
        ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐
        │ Customer  │  │ Flight    │  │ ML Model  │
        │ 360 / AADV│  │ Ops/DCSID │  │ Serving   │
        └───────────┘  └───────────┘  └───────────┘
              │              │              │
              └──────────────┴──────────────┘
                    Systems of Record
```

### Mapped to ASL Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 ASL Enterprise Control Plane                 │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │
│  │Agent        │ │Policy       │ │Model        │            │
│  │Registry     │ │Authority    │ │Gateway      │            │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘            │
└─────────┼───────────────┼───────────────┼───────────────────┘
          │               │               │
          ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────┐
│              TO Agent (ASL-Compliant)                        │
│                                                             │
│  Phase: Ingest → Context → Plan → Act → Verify → Commit     │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Offer Orchestration Agent                            │    │
│  │ Returns: {decision, reasoning, data_used}            │    │
│  │ ← This IS the ASL "Agent Contract"                   │    │
│  └─────────────────────────────────────────────────────┘    │
│                            │                                │
│                    ┌───────▼───────┐                        │
│                    │  Tool Router  │ ← Central (future)     │
│                    └───────┬───────┘                        │
└────────────────────────────┼────────────────────────────────┘
                             │
┌────────────────────────────┼────────────────────────────────┐
│            Customer/PNR Domain Execution Cell                │
│                    ┌───────▼───────┐                        │
│                    │ Domain Tool   │                        │
│                    │ Gateway       │ ← MCP Tools today      │
│                    │ (MCP Server)  │                        │
│                    └───────┬───────┘                        │
│                            │                                │
│              ┌─────────────┼─────────────┐                  │
│              ▼             ▼             ▼                  │
│         Customer 360   Flight Ops    ML Models              │
└─────────────────────────────────────────────────────────────┘
```

---

## What TO Validates for ASL

### 1. Domain Tool Gateway Pattern ✅

**ASL Concept:**
> "Domain Tool Gateway: typed tools, authz, rate limits, circuit breakers, idempotency, tool audit"

**TO Implementation:**
```python
# tools/data_tools.py - This IS a Domain Tool Gateway

def get_customer(customer_id: str) -> Dict[str, Any]:
    """
    Typed interface to Customer 360.
    - Schema validated (returns dict with known structure)
    - Abstracted from SOR (JSON today, API tomorrow)
    - Auditable (can add logging)
    """
    # Today: JSON file
    # Production: Customer 360 API call
    return _load_from_source("customers", customer_id)

def get_ml_scores(pnr: str) -> Dict[str, Any]:
    """
    Typed interface to ML Model Serving.
    - Schema validated
    - Can add rate limits, circuit breakers
    - Can add caching
    """
    return _call_ml_service(pnr)
```

**What TO proves:** MCP Tools pattern works. Just add rate limits + circuit breakers for production.

---

### 2. Agent Contract (Structured Output) ✅

**ASL Concept:**
> "All tools are typed, permissioned, audited"
> "Agent Contract: structured plan with steps, tools, required data"

**TO Implementation:**
```python
# Only Offer Orchestration is an "Agent" - returns structured contract

def analyze(self, state: AgentState) -> Dict[str, Any]:
    return {
        "decision": "OFFER_BUSINESS_CLASS",
        "reasoning": "Customer is price-sensitive but high-value...",
        "data_used": {
            "customer_profile": "AADV DB",
            "ml_scores": "Propensity Model v2",
            "inventory": "DCSID"
        },
        "confidence": 0.85,
        "alternatives_considered": ["MCE", "NO_OFFER"]
    }
```

**What TO proves:** Agent contract pattern works for complex decisions. Simple checks don't need it (workflows).

---

### 3. Multi-Runtime Support ✅

**ASL Concept:**
> "Interactive (K8s), Workflow (workflow engine), Event-driven (event bus), Batch"

**TO Implementation:**
```
┌─────────────────────────────────────────────────────────┐
│  TO uses ONE agent contract across multiple runtimes:   │
│                                                         │
│  ⚡ Workflows (4)     - Simple, deterministic           │
│  🧠 Agent (1)         - Complex, needs explainability   │
│  ✨ LLM Call (1)      - Generative output               │
│                                                         │
│  All share the same State Object (LangGraph)            │
│  All route through same MCP Tools                       │
└─────────────────────────────────────────────────────────┘
```

**What TO proves:** You don't need different "agent types" - you need different COMPONENT types within one workflow.

---

### 4. Policy Enforcement ✅

**ASL Concept:**
> "Enterprise baseline (mandatory): PII/PCI rules, logging/redaction, disallowed actions"
> "Domain overlays (mandatory): domain-specific constraints"

**TO Implementation:**
```python
# Customer Intelligence Workflow - Policy checks

def analyze(self, state: AgentState) -> Dict[str, Any]:
    customer = state.get("customer_data", {})

    # Policy check 1: Suppression (enterprise baseline)
    if customer.get("is_suppressed"):
        return {"eligible": False, "reason": "Customer suppressed"}

    # Policy check 2: Consent (domain overlay)
    consent = customer.get("marketing_consent", {})
    if not consent.get("email") and not consent.get("push"):
        return {"eligible": False, "reason": "No marketing consent"}

    # Policy check 3: Recent complaint (domain overlay)
    if customer.get("complaint_reason"):
        return {"eligible": False, "reason": "Recent complaint"}

    return {"eligible": True}
```

**What TO proves:** Policy checks work at workflow level. Don't need complex "Policy Authority" for v1.

---

### 5. Retrieval with Provenance ✅

**ASL Concept:**
> "Domain Context/Retrieval: domain-indexes + row/field security + provenance"

**TO Implementation:**
```python
# Every agent decision includes data provenance

return {
    "decision": "OFFER_BUSINESS_CLASS",
    "data_used": {
        "get_customer()": "AADV DB → Customer 360",
        "get_flight()": "DCSID → Flight Operations",
        "get_ml_scores()": "ML Model Serving → Propensity v2"
    },
    "reasoning": "Based on customer profile from AADV and ML scores..."
}
```

**What TO proves:** Provenance can be tracked in agent output. Don't need separate "retrieval service" for v1.

---

## Proposed Execution: TO-First Approach

### Phase 1: Ship TO with Production Patterns (Weeks 1-4)

**Goal:** Get TO working end-to-end with ASL-compatible patterns.

| Week | Deliverable |
|------|-------------|
| 1-2 | MCP Tools with proper error handling, timeouts, retries |
| 3-4 | Add structured audit logging to all tool calls |
| 3-4 | Add basic policy enforcement (suppression, consent) |

**Outcome:** TO is production-ready AND validates ASL tool gateway pattern.

### Phase 2: Add Observability & Governance (Weeks 5-8)

**Goal:** Add the "enterprise" pieces that TO needs anyway.

| Week | Deliverable |
|------|-------------|
| 5-6 | OpenTelemetry tracing for full request flow |
| 5-6 | Decision audit log (immutable, searchable) |
| 7-8 | Basic approval workflow for high-value offers |
| 7-8 | Kill switch (disable offers by segment/tier) |

**Outcome:** TO has enterprise-grade observability. Extract patterns for ASL.

### Phase 3: Extract ASL v0.1 (Weeks 9-10)

**Goal:** Generalize what worked in TO.

| Deliverable | Source |
|-------------|--------|
| Domain Tool Gateway template | TO's `tools/data_tools.py` |
| Agent Contract schema | TO's Offer Orchestration output |
| Audit event schema | TO's decision logs |
| Policy check patterns | TO's Customer Intelligence |

**Outcome:** ASL v0.1 is battle-tested, not theoretical.

### Phase 4: Second Lighthouse - IRROPS (Weeks 11-16)

**Goal:** Validate ASL patterns with a different domain.

- Use ASL v0.1 patterns
- Build IRROPS Domain Tool Gateway
- Implement durable workflow (Temporal) for rebooking
- Add approval workflow for high-risk actions

**Outcome:** ASL works for 2 domains. Now it's a platform.

---

## What TO Doesn't Need from ASL v1

Be honest about what's over-engineering for TO:

| ASL Component | TO Needs It? | Why/Why Not |
|---------------|--------------|-------------|
| Agent Registry | ❌ No | TO is one agent. Registry is for many. |
| Model Gateway | ⚠️ Maybe | Simple: just call OpenAI/Anthropic directly |
| Tool Router | ❌ No | TO only has one domain (Customer/PNR) |
| Identity Broker | ⚠️ Maybe | Service accounts work for now |
| Policy Authority | ❌ No | Hardcode policies in workflows for v1 |
| Approvals Service | ⚠️ Maybe | Simple Slack/email approval for v1 |
| PCI Controls | ❌ No | TO doesn't handle payments |
| Eval Gatekeeper | ⚠️ Maybe | Manual testing for v1 |

**Key insight:** TO needs ~30% of ASL. Build that 30% well.

---

## Risk Comparison

### Risk: Build ASL First, Then TO

```
Weeks 1-12: Build ASL platform
  ├── Risk: No real users validating design
  ├── Risk: Scope creep ("let's add X for future agents")
  ├── Risk: Integration surprises with real SORs
  └── Risk: 12 weeks, nothing in production

Weeks 13-20: Port TO to ASL
  ├── Risk: ASL doesn't fit TO's actual needs
  ├── Risk: Rework required
  └── Risk: Still no business value delivered
```

### Risk: TO First, Extract ASL

```
Weeks 1-4: Ship TO with good patterns
  ├── Benefit: Real users, real feedback
  ├── Benefit: Validates tool gateway pattern
  └── Benefit: Business value delivered

Weeks 5-8: Add enterprise features to TO
  ├── Benefit: Only build what TO actually needs
  └── Benefit: Patterns proven before generalizing

Weeks 9-12: Extract ASL v0.1 from TO
  ├── Benefit: ASL is battle-tested
  ├── Benefit: Second agent (IRROPS) validates generalization
  └── Benefit: Platform built from reality, not theory
```

---

## Recommendation to Leadership

### The Ask

> "Fund TO as the ASL lighthouse project. We'll deliver business value
> (tailored offers) while simultaneously validating the ASL architecture.
>
> After TO ships, we'll extract the patterns that worked into ASL v0.1,
> then use IRROPS as the second validation before full platform investment."

### The Commitment

| Milestone | Timeline | Outcome |
|-----------|----------|---------|
| TO Prototype | Week 4 | Working demo, validates tool gateway |
| TO Production-Ready | Week 8 | Observability, audit, policy checks |
| ASL v0.1 Extracted | Week 10 | Reusable patterns documented |
| IRROPS Proof Point | Week 16 | ASL validated across 2 domains |
| ASL v1 Platform | Week 24+ | Full platform, justified by proven value |

### The Trade-off

**We're trading:** Theoretical completeness of ASL v1 in 12 weeks

**For:** Proven patterns, real business value, lower risk

---

## Appendix: TO Component → ASL Mapping

```
TO Component                    ASL Equivalent
─────────────────────────────────────────────────────────────
tools/data_tools.py          → Domain Tool Gateway
                               (Customer/PNR Execution Cell)

agents/offer_orchestration.py → Agent Runtime
                               (implements Agent Contract)

agents/workflow.py           → Central Agent Runtime
                               (state machine: ingest→act→verify)

LangGraph StateGraph         → Agent Run State Machine
                               (shared state, conditional routing)

Reasoning traces             → Observability/Audit Sink
                               (immutable decision log)

Suppression/consent checks   → Policy Authority
                               (enterprise baseline + domain overlay)

MCP tool schemas             → Tool Manifest
                               (typed, validated interfaces)

frontend/ SSE streaming      → Agent Runtime streaming
                               (real-time status updates)
```

---

## Next Steps

1. **Align with ASL team** - Share this mapping, get buy-in on TO as lighthouse
2. **Identify gaps** - What does TO need that isn't built yet?
3. **Prioritize** - Which ASL patterns should TO implement first?
4. **Ship** - Get TO to production, prove the patterns work

---

*Document prepared for American Airlines AI Engineering*
*TO Offer Prototype Team*
