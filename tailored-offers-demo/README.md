# Tailored Offers - Agentic AI Demo

A 3-phase pipeline demonstrating **agentic AI** for American Airlines upgrade offers. Shows how a single AI agent (using the ReWOO pattern) adds value beyond ML models alone, supported by deterministic workflow steps.

## Quick Start

### Docker (Recommended)

```bash
# Build and run (mock mode - no API keys needed)
docker-compose up --build

# Open http://localhost:3000
```

**With Real LLM:**
```bash
cp .env.example .env
# Add OPENAI_API_KEY or ANTHROPIC_API_KEY to .env
docker-compose up --build
```

### Local Development

```bash
# Terminal 1 - API
pip install -r requirements.txt && pip install -r api/requirements.txt
export OPENAI_API_KEY=sk-your-key  # Optional
python -m uvicorn api.main:app --port 8000

# Terminal 2 - Frontend
cd frontend && npm install && npm run dev
# Open http://localhost:5173
```

---

## Architecture: 3-Phase Pipeline (1 Agent + 2 Workflows)

```
┌──────────────┐     ┌─────────────────────────┐     ┌──────────────┐
│  Pre-checks  │ ──► │      Offer Agent         │ ──► │   Delivery   │
│  (Workflow)  │     │       (ReWOO)            │     │  (Workflow)  │
├──────────────┤     ├─────────────────────────┤     ├──────────────┤
│ • Customer   │     │ • Planner: picks evals  │     │ • Message    │
│   Eligibility│     │ • Worker: runs evals    │     │   Generation │
│ • Inventory  │     │ • Solver: makes decision│     │ • Channel    │
│   Check      │     │                         │     │   Selection  │
│              │     │   15+ factor decision   │     │ • Tracking   │
│   ⚡ Rules   │     │   with audit trail      │     │   Setup      │
└──────┬───────┘     └───────────┬─────────────┘     └──────┬───────┘
       │                         │                          │
       ▼                         ▼                          ▼
   Gate: eligible?          Gate: offer?              Done: deliver
   No → STOP               No → STOP                 offer to customer
```

### Why This Pattern?

**ReWOO (Reasoning Without Observation)** is ideal for this use case because:

1. **Plan once, execute all** - The Planner decides upfront which evaluations are needed (confidence check, price sensitivity, disruption history, etc.) rather than going back to the LLM after each step
2. **Deterministic pre/post steps** - Eligibility and inventory don't need LLM reasoning; they're yes/no checks
3. **Single LLM call** - Only the Offer Agent uses the LLM. Pre-checks and delivery are pure workflow
4. **Auditable** - Every evaluation step produces structured output for compliance

### Phase Breakdown

| Phase | Type | What It Does |
|-------|------|-------------|
| **Pre-checks** | ⚡ Workflow | Customer eligibility (suppression, consent) + inventory availability. Gate: stops pipeline if ineligible or no seats. |
| **Offer Agent** | 🧠 Agent (ReWOO) | **Planner** picks which evaluations to run (confidence, price sensitivity, disruption, relationship). **Worker** executes each evaluation. **Solver** synthesizes results into a final offer decision. |
| **Delivery** | ⚡ Workflow + LLM | Message generation (LLM for personalized copy, template fallback), channel selection (rules-based), A/B tracking setup. |

### How It Works (Plain English)

1. **Pre-checks** - "Can we contact this customer? Are there seats to sell?"
   - If customer is suppressed or no inventory → pipeline stops immediately
   - No LLM needed, just data lookups and rules

2. **Offer Agent (the brain)** - "Which upgrade should we offer, and at what price?"
   - Planner: "For this customer, I need to check: ML confidence, price sensitivity, and recent disruption history"
   - Worker: Runs each evaluation and gets structured results
   - Solver: "Business Class at $249, no discount needed. Here's why..."

3. **Delivery** - "How do we get this offer to the customer?"
   - Generates a personalized message (LLM or template)
   - Picks the best channel (push vs email) based on consent and engagement
   - Assigns A/B test group and tracking ID

---

## Demo Scenarios

| PNR | Customer | What It Shows | Outcome |
|-----|----------|---------------|---------|
| **ABC123** | Sarah (Gold, T-96hrs) | Full happy path - clear Business EV winner | ✅ Business @ $249 |
| **XYZ789** | John (Platinum Pro, T-72hrs) | Confidence trade-off - high EV but unreliable ML | ✅ Adjusted offer |
| **LMN456** | Emily (Exec Platinum, T-120hrs) | Relationship trade-off - recent service issue | ✅ Gentle approach |
| **DEF321** | Michael (Gold, T-48hrs) | Guardrail: no inventory (0 seats) | ❌ Stopped at Pre-checks |
| **GHI654** | Lisa (Platinum, T-96hrs) | Guardrail: suppressed customer | ❌ Stopped at Pre-checks |
| **JKL789** | David (Gold, T-84hrs) | Price sensitive + recent 3hr delay | ✅ MCE @ discounted |

---

## Key Features

### 1. Bounded Autonomy with Guardrails

The agent can reason about discounts but operates within business-defined limits:

```python
# GUARDRAILS (Agent CANNOT exceed these)
OFFER_CONFIG = {
    "business":    { "max_discount": 0.20 },  # Never exceed 20% off
    "mce":         { "max_discount": 0.25 },  # Never exceed 25% off
}

# TIME-BASED POLICY (Agent can add urgency discount)
URGENCY_DISCOUNT_POLICY = {
    "TOO_LATE":  { "max_hours": 6,   "send_offer": False },  # Stop at T-6hrs
    "URGENT":    { "max_hours": 24,  "discount_boost": 0.10 },  # +10%
    "SOON":      { "max_hours": 48,  "discount_boost": 0.05 },  # +5%
    "NORMAL":    { "max_hours": 168, "discount_boost": 0 },
}
```

**Result:** Agent can propose 15% base + 10% urgency = 25%, but Business max is 20%, so **final = 20% (capped)**.

### 2. Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA LOADING                              │
│                                                                  │
│  USE_MCP=false (default)          USE_MCP=true (optional)       │
│  ┌─────────────────────┐          ┌─────────────────────┐       │
│  │  Direct Function    │          │   MCP Client        │       │
│  │  Calls (fast)       │          │   (langchain-mcp)   │       │
│  └──────────┬──────────┘          └──────────┬──────────┘       │
│             │                                │ stdio            │
│             │                                ▼                  │
│             │                     ┌─────────────────────┐       │
│             │                     │   MCP Server        │       │
│             │                     │   (tools/mcp_server)│       │
│             │                     └──────────┬──────────┘       │
│             │                                │                  │
│             └────────────┬───────────────────┘                  │
│                          ▼                                      │
│               ┌─────────────────────┐                           │
│               │  tools/data_tools   │                           │
│               │  (JSON files now,   │                           │
│               │   APIs in prod)     │                           │
│               └─────────────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
```

**Data Sources (simulated in demo, real APIs in production):**
```
get_reservation() → Reservation System → state.hours_to_departure
get_ml_scores()   → ML Model API      → state.ml_scores
get_customer()    → Customer 360      → state.customer_data
get_flight()      → Flight Ops        → state.flight_data
```

Agents read from shared state, not files directly. Swap to production by changing `tools/data_tools.py` only.

**MCP Mode** (optional - for demonstrating MCP protocol):
```bash
# Enable MCP client/server architecture
export USE_MCP=true

# Test MCP server standalone with Inspector
mcp dev tools/mcp_server.py
```

| Mode | Data Flow | Use Case |
|------|-----------|----------|
| `USE_MCP=false` | Direct Python calls | Development (fast) |
| `USE_MCP=true` | MCP client → server | Production pattern |

### 3. Expected Value Optimization

```
EV = P(buy) × Price × Margin

Business: 68% × $199 × 90% = $121.79  ← WINNER
MCE:      82% × $49  × 85% = $34.18
```

Agent selects offer with highest EV, not highest acceptance rate.

### 4. LLM Modes

| Mode | Decision | Explanation |
|------|----------|-------------|
| **Mock** (no API key) | Rules ⚡ | Pre-written templates |
| **With LLM** | Rules ⚡ | LLM generates natural explanation |
| **Personalization** | N/A | LLM generates customer message |

---

## Project Structure

```
tailored-offers-demo/
├── api/                    # FastAPI backend
│   └── main.py            # Endpoints + SSE streaming
├── frontend/              # React + Vite + Tailwind
│   └── src/components/    # UI components
├── agents/                # Pipeline phases
│   ├── prechecks.py       # ⚡ Phase 1: Eligibility + Inventory (workflow)
│   ├── offer_orchestration.py  # 🧠 Phase 2: ReWOO Offer Agent
│   ├── delivery.py        # ⚡ Phase 3: Message + Channel + Tracking (workflow)
│   ├── llm_service.py     # LLM provider abstraction
│   └── workflow.py        # LangGraph pipeline
├── tools/                 # MCP tool abstraction layer
│   ├── data_tools.py      # get_customer(), get_flight(), etc.
│   ├── mcp_server.py      # MCP server (FastMCP) exposing data tools
│   └── mcp_client.py      # MCP client wrapper (langchain-mcp-adapters)
├── data/                  # Mock data (JSON files)
├── config/                # Custom prompt configurations
├── docker-compose.yml
└── requirements.txt
```

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Agent Pattern | ReWOO (Planner → Worker → Solver) |
| Workflow Orchestration | LangGraph (StateGraph) |
| LLM | OpenAI GPT-4o-mini / Anthropic Claude 3.5 |
| Data Protocol | MCP (Model Context Protocol) with langchain-mcp-adapters |
| Backend | FastAPI + SSE |
| Frontend | React + Vite + Tailwind |
| Deployment | Docker Compose |

---

## Architecture Highlights

### 3-Phase Pipeline with Conditional Routing

```python
# Phase 1: Pre-checks (workflow)
eligible, reason, segment, details = check_customer_eligibility(customer)
if not eligible:
    return  # STOP - customer not eligible

has_inventory, cabins, status = check_inventory_availability(flight)
if not has_inventory:
    return  # STOP - no seats to sell

# Phase 2: Offer Agent (ReWOO)
# Planner → Worker → Solver
offer_decision = offer_agent.invoke(state)

# Phase 3: Delivery (workflow + LLM)
message = generate_message(customer, flight, offer_type, price)
channel = select_channel(customer, hours_to_departure)
tracking = setup_tracking(pnr, offer_type)
```

### Agent Contract

Every agent returns structured output for auditability:

```python
{
    "decision": "OFFER_BUSINESS_CLASS",
    "reasoning": "EV $121.79 > MCE $34.18, customer tier supports price",
    "data_used": ["ml_scores", "customer_data", "flight_data"]
}
```

### Guardrails Enforcement

```python
# Agent proposes discount
proposed = base_discount + urgency_boost  # e.g., 5% + 10% = 15%

# ⛔ GUARDRAIL: Cap at max
final = min(proposed, max_discount)  # min(15%, 20%) = 15%
```

---

## Environment Variables

```bash
# LLM (optional - runs in mock mode without)
OPENAI_API_KEY=sk-...
# OR
ANTHROPIC_API_KEY=sk-ant-...

# MCP Mode (optional - uses direct calls by default)
USE_MCP=true  # Enable MCP client/server for data loading

# Dynamic reasoning (optional)
USE_DYNAMIC_REASONING=true  # LLM generates explanations for all agents
```

---

## Demo Tips

1. **Start with ABC123** - Shows full happy path with all 3 phases
2. **Show GHI654** - Pipeline stops at Pre-checks (suppressed customer)
3. **Show DEF321** - Pipeline stops at Pre-checks (no inventory)
4. **Show JKL789** - Agent considers recent disruption + price sensitivity
5. **Click "View Details"** - Shows sub-steps within each phase
6. **Click each phase** - See detailed reasoning in right panel

---

## Business Value

| What | How |
|------|-----|
| **Explainability** | Every decision has traceable reasoning |
| **Auditability** | 15+ factors documented for compliance |
| **Guardrails** | Business rules enforced in code, not prompts |
| **Hybrid AI** | Workflows for speed, Agent for intelligence |
| **Clean Architecture** | 1 Agent where it matters, workflows everywhere else |
| **Future-proof** | Same architecture scales to real-time scenarios |
