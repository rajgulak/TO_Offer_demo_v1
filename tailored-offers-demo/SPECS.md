# Tailored Offers Demo - Specifications

> **Spec-Driven Development**: Write specs first, then use any GenAI tool to implement.
> Contributors can add specs and use Claude, Copilot, Cursor, or any AI coding assistant.

---

## Table of Contents
- [How to Use This Document](#how-to-use-this-document)
- [Spec Template](#spec-template)
- [Implemented Specs](#implemented-specs)
- [Pending Specs](#pending-specs)
- [Future Ideas](#future-ideas)

---

## How to Use This Document

### For Contributors
1. **Find a spec** in [Pending Specs](#pending-specs) or [Future Ideas](#future-ideas)
2. **Copy the spec** into your AI tool of choice
3. **Implement** following the spec requirements
4. **Test** against the acceptance criteria
5. **Submit PR** referencing the spec ID

### For Adding New Specs
1. Use the [Spec Template](#spec-template) below
2. Add to appropriate section (Pending or Future)
3. Assign a unique SPEC-ID (e.g., `SPEC-042`)
4. Submit PR with just the spec (no implementation required)

---

## Spec Template

```markdown
### SPEC-XXX: [Feature Name]

**Status**: `pending` | `in-progress` | `implemented` | `deprecated`
**Priority**: `P0` (critical) | `P1` (high) | `P2` (medium) | `P3` (low)
**Complexity**: `S` (small, <2hrs) | `M` (medium, 2-8hrs) | `L` (large, 1-3 days) | `XL` (epic)

#### Description
[What does this feature do? Why is it needed?]

#### User Story
As a [role], I want [feature] so that [benefit].

#### Requirements
- [ ] Requirement 1
- [ ] Requirement 2
- [ ] Requirement 3

#### Technical Details
- **Files to modify**: `path/to/file.py`, `path/to/component.tsx`
- **Dependencies**: [any new packages needed]
- **Data sources**: [what data is needed]

#### Acceptance Criteria
- [ ] Criteria 1 that can be tested
- [ ] Criteria 2 that can be tested
- [ ] Criteria 3 that can be tested

#### Example Usage
[Code snippet or API example showing expected behavior]

#### References
- Related specs: SPEC-XXX
- Architecture decisions: ADR-XXX
- External docs: [links]
```

---

## Implemented Specs

### SPEC-001: ReWOO Pattern for Offer Orchestration

**Status**: `implemented`
**Priority**: `P0`
**Complexity**: `L`

#### Description
Implement the ReWOO (Reasoning WithOut Observation) pattern for the Offer Orchestration agent. This separates planning from execution, allowing the agent to create a full plan before executing any tools.

#### Requirements
- [x] Planner phase: LLM creates evaluation plan based on context
- [x] Worker phase: Execute each evaluation step (confidence, relationship, price sensitivity)
- [x] Solver phase: Synthesize results and make final decision
- [x] Support for dynamic plan generation based on context
- [x] Fallback to default plan if LLM planning fails

#### Technical Details
- **Files**: `agents/offer_orchestration_rewoo.py`
- **Pattern**: Planner → Worker → Solver
- **LLM calls**: 2 (planning + solving) or 1 (solving only with default plan)

#### Acceptance Criteria
- [x] Agent produces structured reasoning trace
- [x] Each evaluation step is logged with results
- [x] Final decision includes discount, price, and expected value
- [x] Graceful fallback when planning fails

---

### SPEC-002: Pre-Approved Discount Policies

**Status**: `implemented`
**Priority**: `P0`
**Complexity**: `M`

#### Description
Replace autonomous agent discount decisions with pre-approved policies from Revenue Management. Agent applies policies, doesn't decide them.

#### Requirements
- [x] Create `config/discount_policies.json` with policy definitions
- [x] Each policy has: ID, name, discount percentage, approval authority
- [x] Agent references policy ID in reasoning output
- [x] Segment caps limit maximum discounts per customer type

#### Technical Details
- **Files**:
  - `config/discount_policies.json` (new)
  - `agents/offer_orchestration_rewoo.py` (modified)

#### Policy Structure
```json
{
  "policies": {
    "GOODWILL_RECOVERY": {
      "policy_id": "POL-GW-001",
      "discount_percent": 10,
      "approved_by": "Customer Experience Team",
      "triggers": ["recent_service_issue", "high_value_customer"]
    }
  },
  "segment_caps": {
    "elite_business": { "max_total_discount": 20 }
  }
}
```

#### Acceptance Criteria
- [x] Reasoning output shows "Applying pre-approved policy [POL-XXX]"
- [x] No autonomous discount decisions by agent
- [x] Policy IDs traceable in logs

---

### SPEC-003: Interactive Tutorial Component

**Status**: `implemented`
**Priority**: `P1`
**Complexity**: `L`

#### Description
Multi-step interactive tutorial with Business and Technical tracks. Explains architecture, patterns, and features with animations.

#### Requirements
- [x] Two audience tracks: Business (6 steps) and Technical (11 steps)
- [x] Animated transitions between phases
- [x] Step navigation with progress indicators
- [x] Technical track covers all ADRs

#### Technical Details
- **Files**: `frontend/src/components/InteractiveTutorial.tsx`
- **Steps (Technical)**: Intro, Decision Framework, LangGraph, MCP, Data Decisions, EDD, Guardrails, HITL Concept, HITL Demo, Production Safety, Summary

#### Acceptance Criteria
- [x] Smooth animations on step transitions
- [x] All technical concepts explained with visuals
- [x] Works on different screen sizes

---

### SPEC-004: Human-in-the-Loop (HITL) Approval Flow

**Status**: `implemented`
**Priority**: `P0`
**Complexity**: `XL`

#### Description
Deferred execution pattern where high-value offers pause for human approval before proceeding.

#### Requirements
- [x] Backend escalation rules (not LLM decisions)
- [x] State persistence using LangGraph checkpointing
- [x] Approval queue UI with Approve/Deny/Modify actions
- [x] Resume workflow after approval
- [x] Full context preserved across pause/resume

#### Technical Details
- **Files**:
  - `agents/workflow.py` - HITL workflow variant
  - `api/main.py` - Approval endpoints
  - `frontend/src/components/ApprovalsQueue.tsx`
  - `infrastructure/human_in_loop.py`

#### Escalation Rules
```python
ESCALATION_RULES = {
    "high_value_threshold": 500,  # Offer > $500
    "vip_tiers": ["ConciergeKey", "ExecutivePlatinum"],
    "anomaly_threshold": 0.8,
    "regulatory_routes": ["EU", "UK"]
}
```

#### API Endpoints
- `GET /api/approvals/pending` - List pending approvals
- `POST /api/approvals/{id}/approve` - Approve offer
- `POST /api/approvals/{id}/deny` - Deny offer
- `POST /api/approvals/{id}/resume` - Resume workflow

#### Acceptance Criteria
- [x] High-value offers automatically escalate
- [x] Approval queue shows full context
- [x] Workflow resumes correctly after approval
- [x] Denied offers are logged with reason

---

### SPEC-005: 3-Layer Guardrail Architecture

**Status**: `implemented`
**Priority**: `P0`
**Complexity**: `L`

#### Description
Defense-in-depth guardrails: synchronous pre-checks, async parallel validation, and triggered post-decision checks.

#### Requirements
- [x] Layer 1 (Sync): Eligibility, inventory, recent complaints (~60ms)
- [x] Layer 2 (Async): Fraud detection, compliance, rate limiting (parallel)
- [x] Layer 3 (Triggered): High-value escalation, VIP handling, anomalies

#### Technical Details
- **Files**: `infrastructure/guardrails.py`

#### Acceptance Criteria
- [x] Sync checks block before agent execution
- [x] Async checks run in parallel
- [x] Any layer can halt the request
- [x] Clear logging of which guardrail triggered

---

### SPEC-006: Eval-Driven Development Framework

**Status**: `implemented`
**Priority**: `P1`
**Complexity**: `M`

#### Description
Test framework for validating agent behavior across scenarios. Like TDD but for AI agents.

#### Requirements
- [x] Define expected behaviors for each test scenario
- [x] Automated test execution
- [x] Calibration tracking over time
- [x] Clear pass/fail criteria

#### Test Scenarios
| Scenario | Test Case | Expected Behavior |
|----------|-----------|-------------------|
| ABC123 | High EV, confident ML | Offer Business @ full price |
| XYZ789 | Low confidence ML | Fall back to safer offer |
| LMN456 | Recent service issue | Apply goodwill policy |
| DEF321 | Zero inventory | Skip offer gracefully |
| GHI654 | Customer suppressed | Block at guardrail |
| JKL789 | High price sensitivity | Apply discount policy |

#### Technical Details
- **Files**: `tests/test_agent_scenarios.py`
- **API**: `/api/calibration`

#### Acceptance Criteria
- [x] All 6 scenarios have automated tests
- [x] Tests validate both decision AND reasoning
- [x] Calibration endpoint returns accuracy metrics

---

## Pending Specs

### SPEC-007: MCP Tools for Enterprise Systems

**Status**: `pending`
**Priority**: `P1`
**Complexity**: `M`

#### Description
Create explicit MCP tools for Merch Catalog, Policy Gateway, and ML API to better represent the production architecture.

#### Requirements
- [ ] `get_offers_catalog()` - Fetch available offers from Merch Catalog
- [ ] `get_policy_rules()` - Fetch filtering rules from Policy Gateway
- [ ] `call_ml_api()` - Get propensity scores from ML Platform
- [ ] Update agent to use these tools explicitly

#### Technical Details
- **Files to create**:
  - `data/offers_catalog.json`
  - `data/policy_rules.json`
  - `tools/merch_catalog.py`
  - `tools/policy_gateway.py`
- **Files to modify**:
  - `tools/data_tools.py`
  - `agents/offer_orchestration_rewoo.py`

#### Data Structure - Offers Catalog
```json
{
  "offers": [
    {
      "offer_id": "IU_BUSINESS",
      "name": "Business Class Upgrade",
      "base_price": 770,
      "cabin": "F",
      "eligible_origin_cabins": ["Y", "W"],
      "benefits": ["lie-flat seat", "priority boarding", "premium dining"]
    }
  ]
}
```

#### Data Structure - Policy Rules
```json
{
  "eligibility_rules": [
    {
      "rule_id": "RULE-001",
      "name": "Minimum Loyalty Tier",
      "condition": "loyalty_tier IN ['G', 'P', 'E', 'K']",
      "action": "allow"
    }
  ],
  "discount_policies": { ... },
  "suppression_rules": [ ... ]
}
```

#### Acceptance Criteria
- [ ] Agent reasoning shows "Fetched 3 offers from Merch Catalog"
- [ ] Agent reasoning shows "Applied RULE-001 from Policy Gateway"
- [ ] ML API call is explicit in trace
- [ ] Demo data maps to production system names

---

### SPEC-008: Decision Ledger / Audit Trail

**Status**: `pending`
**Priority**: `P1`
**Complexity**: `M`

#### Description
Record every decision with full context for audit, debugging, and ML feedback loops.

#### Requirements
- [ ] Log every offer decision with timestamp
- [ ] Include: inputs, reasoning trace, outputs, model versions
- [ ] Queryable by PNR, customer, date range
- [ ] Export capability for compliance

#### Technical Details
- **Files to create**:
  - `infrastructure/decision_ledger.py`
  - `data/decisions/` (storage directory)
- **Files to modify**:
  - `agents/workflow.py`
  - `api/main.py`

#### Decision Record Schema
```json
{
  "decision_id": "DEC-20260120-ABC123",
  "timestamp": "2026-01-20T18:30:00Z",
  "pnr": "ABC123",
  "customer_id": "1234567890",
  "inputs": {
    "customer_data": { ... },
    "flight_data": { ... },
    "ml_scores": { ... }
  },
  "agent_reasoning": "...",
  "decision": {
    "offer_type": "IU_BUSINESS",
    "price": 693,
    "discount_policy": "POL-GW-001"
  },
  "model_versions": {
    "orchestration_agent": "rewoo-v2",
    "ml_propensity": "xgb-v1.2"
  }
}
```

#### Acceptance Criteria
- [ ] Every decision creates a ledger entry
- [ ] API endpoint to query decisions
- [ ] Export to JSON/CSV for compliance

---

### SPEC-009: A/B Test Comparison Dashboard

**Status**: `pending`
**Priority**: `P2`
**Complexity**: `M`

#### Description
Visual dashboard comparing control vs AI experiment groups with statistical significance.

#### Requirements
- [ ] Show conversion rates by experiment group
- [ ] Calculate statistical significance (p-value)
- [ ] Revenue impact visualization
- [ ] Filter by date range, segment, offer type

#### Technical Details
- **Files to create**:
  - `frontend/src/components/ABTestDashboard.tsx`
- **Files to modify**:
  - `api/main.py` (add stats endpoint)

#### Mockup
```
┌─────────────────────────────────────────────────────┐
│ A/B Test Results                                    │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Control (Rules)     vs     Test (AI Model v2)     │
│  ────────────────          ─────────────────────   │
│  Conversion: 2.3%          Conversion: 3.8%        │
│  n = 1,234                 n = 1,198               │
│                                                     │
│  Lift: +65% ✓ Significant (p < 0.01)              │
│                                                     │
│  Projected Annual Impact: +$2.4M revenue           │
└─────────────────────────────────────────────────────┘
```

#### Acceptance Criteria
- [ ] Real-time stats from tracking data
- [ ] Statistical significance calculation
- [ ] Clear visualization of lift

---

### SPEC-010: Multi-Language Message Generation

**Status**: `pending`
**Priority**: `P2`
**Complexity**: `S`

#### Description
Generate personalized offer messages in customer's preferred language.

#### Requirements
- [ ] Detect customer language preference
- [ ] Generate message in target language
- [ ] Support: English, Spanish, French, German, Japanese
- [ ] Fallback to English if unsupported

#### Technical Details
- **Files to modify**:
  - `agents/personalization_agent.py`
  - `data/customers.json` (add language_preference field)

#### Acceptance Criteria
- [ ] Spanish customer gets Spanish message
- [ ] Language noted in reasoning trace
- [ ] Graceful fallback for unsupported languages

---

### SPEC-011: Real-Time Inventory Refresh

**Status**: `pending`
**Priority**: `P2`
**Complexity**: `M`

#### Description
Simulate real-time inventory updates that affect offer availability during evaluation.

#### Requirements
- [ ] WebSocket connection for inventory updates
- [ ] UI shows live seat counts
- [ ] Agent re-checks inventory before final decision
- [ ] Handle "sold out during evaluation" scenario

#### Technical Details
- **Files to create**:
  - `api/websocket.py`
  - `frontend/src/hooks/useInventoryStream.ts`

#### Acceptance Criteria
- [ ] Inventory updates appear in real-time
- [ ] Agent handles inventory changes gracefully
- [ ] Demo can trigger inventory changes manually

---

## Future Ideas

These are rough ideas that need full spec definition:

### IDEA-001: Voice-Based Offer Presentation
Use text-to-speech to present offers in call center scenarios.

### IDEA-002: Competitive Pricing Intelligence
Factor in competitor pricing when setting upgrade prices.

### IDEA-003: Weather-Based Offer Timing
Delay offers when destination has bad weather (customer less excited).

### IDEA-004: Group Booking Offers
Handle PNRs with multiple passengers - offer upgrades to the group.

### IDEA-005: Post-Flight Feedback Loop
Track actual customer satisfaction after upgrades to improve models.

### IDEA-006: Slack/Teams Integration for HITL
Send approval requests to Slack/Teams instead of custom UI.

### IDEA-007: Cost Optimization Mode
Budget-constrained mode that optimizes for ROI within daily LLM spend limit.

### IDEA-008: Explanation Generator
Generate natural language explanations of why a specific offer was made.

---

## Contributing

1. **Pick a spec** from Pending or Future Ideas
2. **Claim it** by updating status to `in-progress` and adding your name
3. **Implement** using your preferred AI coding tool
4. **Test** against acceptance criteria
5. **PR** with spec ID in title (e.g., "SPEC-007: MCP Tools Implementation")

### Spec Quality Guidelines
- Be specific about inputs/outputs
- Include data structures
- Define clear acceptance criteria
- Reference related files
- Consider error cases

---

## Prompt Editing Guide

### How Prompts Affect Agent Behavior

Prompts are the "instructions" that control how LLM-powered agents reason and respond. Editing prompts is the primary way to tune agent behavior.

### Prompt Locations

```
config/prompts/
├── planner.txt              # ReWOO planner - creates evaluation plan
├── solver.txt               # ReWOO solver - makes final decision
├── personalization.txt      # Message generation
└── reasoning_explanation.txt # Natural language explanations
```

### API Endpoints for Prompt Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/prompts` | GET | List all prompts with metadata |
| `/api/prompts/{name}` | GET | Get full prompt content |
| `/api/prompts/{name}` | PUT | Update prompt content |
| `/api/prompts/{name}/test` | POST | Test prompt with variables |

### Prompt File Format

```txt
# PROMPT NAME
# Version: 1.0
# Last Modified: 2026-01-20
# Purpose: What this prompt does
#
# Variables available:
#   - {customer_name}: Description
#   - {offer_price}: Description
#
# How changes affect behavior:
#   - Change X → Effect Y
#   - Change A → Effect B

[Actual prompt content starts here...]
```

### Common Edits and Their Effects

#### 1. Planner Prompt (`planner.txt`)
Controls what factors the agent evaluates.

| Edit | Effect |
|------|--------|
| Add new evaluation type | Agent considers additional factor |
| Remove evaluation type | Agent skips that check |
| Change JSON format | Must update parser code |

**Example - Add new evaluation type:**
```diff
Available evaluation types:
- CONFIDENCE: Compare ML confidence levels
- RELATIONSHIP: Check recent service issues
+ - WEATHER: Consider destination weather impact
- PRICE_SENSITIVITY: Evaluate discount needs
```

#### 2. Solver Prompt (`solver.txt`)
Controls how the agent weighs trade-offs.

| Edit | Effect |
|------|--------|
| Change confidence threshold | Different offer selection |
| Add discount rules | More/less aggressive discounting |
| Modify output format | Must update response parser |

**Example - Make agent more conservative:**
```diff
Consider:
- If CONFIDENCE evaluation shows low confidence for high-EV offer,
-  prefer the safer option
+  ALWAYS prefer the safer option (prioritize customer trust)
```

#### 3. Personalization Prompt (`personalization.txt`)
Controls message tone and content.

| Edit | Effect |
|------|--------|
| Change tone guidelines | Different message style |
| Add/remove benefits | Changes value proposition |
| Modify urgency rules | Affects call-to-action strength |

**Example - Make messages more urgent:**
```diff
Remember:
- Use customer's name naturally
- Reference their specific route
-- Match urgency to time-to-departure
+- ALWAYS emphasize limited availability
+- Include countdown: "Only X hours left to upgrade!"
- Keep it concise but compelling
```

### Testing Prompt Changes

```bash
# 1. Get current prompt
curl http://localhost:8000/api/prompts/planner

# 2. Test with variables
curl -X POST http://localhost:8000/api/prompts/personalization/test \
  -H "Content-Type: application/json" \
  -d '{"customer_name": "Sarah", "offer_price": 499}'

# 3. Update prompt
curl -X PUT http://localhost:8000/api/prompts/planner \
  -H "Content-Type: application/json" \
  -d '{"content": "... new prompt content ..."}'

# 4. Run scenario to see effect
curl http://localhost:8000/api/pnrs/ABC123/evaluate
```

### Hot Reload

Prompts are hot-reloaded - changes take effect immediately without restarting the server. The PromptManager checks file modification times and reloads when changed.

### Version Control

- Each prompt file includes version metadata
- Version auto-increments on API update
- Use git to track prompt changes over time
- `/api/prompts/compare/{name}` shows diff from original

---

## LLM Configuration

### The demo works with OR without LLM configured!

**With LLM (OpenAI or Anthropic):**
```bash
export OPENAI_API_KEY=sk-xxx
# or
export ANTHROPIC_API_KEY=sk-xxx
```
- Dynamic plan generation by LLM
- Natural language reasoning
- Personalized message generation

**Without LLM (Demo/Mock Mode):**
- Default rule-based plans (same logic, just pre-defined)
- Templated reasoning output
- Mock message templates
- **Full functionality preserved** - just less dynamic text

### How It Works

```python
# In agents/llm_service.py
def get_llm():
    if os.getenv("OPENAI_API_KEY"):
        return ChatOpenAI(...)
    elif os.getenv("ANTHROPIC_API_KEY"):
        return ChatAnthropic(...)
    else:
        return MockLLM()  # Pre-defined responses
```

The `MockLLM` class provides sensible pre-defined responses that simulate LLM reasoning. This allows:
- **Demo without API keys** - anyone can run the demo
- **Faster development** - no LLM latency during testing
- **Cost control** - no API charges for basic testing

### Check Current Mode

The UI shows current LLM status:
- **API:** `/api/llm-status`
- **Response:** `{"provider": "OpenAI (GPT-4)" | "Anthropic (Claude)" | "Mock (Demo Mode)"}`

---

*Last updated: 2026-01-20*
