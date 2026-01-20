# Tailored Offers - Agentic AI Demo

A 6-step pipeline demonstrating **agentic AI** for American Airlines upgrade offers. Shows how AI agents add value beyond ML models alone.

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

## Architecture: 1 Agent + 4 Workflows + 1 LLM Call

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DECISION PIPELINE                               │
│                                                                              │
│  ┌──────────┐   ┌──────────┐   ┌──────────────┐   ┌──────────┐   ┌────────┐ │
│  │ Customer │ → │  Flight  │ → │    Offer     │ → │ Personal-│ → │Channel │ │
│  │  Intel   │   │  Optim   │   │ Orchestration│   │ ization  │   │ Timing │ │
│  │    ⚡    │   │    ⚡    │   │     🧠       │   │    ✨    │   │   ⚡   │ │
│  │ WORKFLOW │   │ WORKFLOW │   │   AGENT      │   │LLM CALL  │   │WORKFLOW│ │
│  └──────────┘   └──────────┘   └──────────────┘   └──────────┘   └────────┘ │
│                                       │                                      │
│                                       ▼                                      │
│                              ┌──────────────┐                                │
│                              │   Tracking   │  ← POST-DECISION               │
│                              │    Setup     │    (A/B test + tracking ID)    │
│                              │     🏷️      │                                │
│                              └──────────────┘                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Why Only 1 Agent?

| Component | Type | Why? |
|-----------|------|------|
| Customer Intelligence | ⚡ Workflow | Simple yes/no eligibility check |
| Flight Optimization | ⚡ Workflow | Data lookup, not a decision |
| **Offer Orchestration** | 🧠 **Agent** | Complex 15+ factor decision with audit trail |
| Personalization | ✨ LLM Call | Text generation, not decision-making |
| Channel & Timing | ⚡ Workflow | Simple rules (has consent? → which channel) |
| Tracking Setup | 🏷️ Post-Decision | Just attaches A/B group + tracking ID |

**Key insight:** Use agents where they add value, not everywhere for consistency.

---

## Demo Scenarios

| PNR | Customer | What It Shows | Outcome |
|-----|----------|---------------|---------|
| **ABC123** | Sarah (Gold, T-96hrs) | Full happy path | ✅ Business @ $199 |
| **XYZ789** | John (Platinum Pro, T-72hrs) | Price adjustment | ✅ Business @ $249 |
| **LMN456** | Emily (Exec Platinum, T-120hrs) | Premium treatment | ✅ Business @ $770 |
| **DEF321** | Michael (General, T-48hrs) | Cold start + no inventory | ❌ No offer |
| **GHI654** | Lisa (Platinum, T-96hrs) | Suppressed customer | ❌ No offer |
| **JKL789** | Budget (T-84hrs) | Price-sensitive | ✅ MCE @ discounted |

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
├── agents/                # The 6 pipeline steps
│   ├── customer_intelligence.py   # ⚡ Eligibility check
│   ├── flight_optimization.py     # ⚡ Inventory lookup
│   ├── offer_orchestration.py     # 🧠 THE AGENT (15+ factors)
│   ├── personalization.py         # ✨ LLM message generation
│   ├── channel_timing.py          # ⚡ Channel selection
│   ├── measurement_learning.py    # 🏷️ Tracking setup
│   └── workflow.py                # LangGraph pipeline
├── tools/                 # MCP tool abstraction layer
│   ├── data_tools.py      # get_customer(), get_flight(), etc.
│   ├── mcp_server.py      # MCP server (FastMCP) exposing data tools
│   └── mcp_client.py      # MCP client wrapper (langchain-mcp-adapters)
├── data/                  # Mock data (JSON files)
├── docker-compose.yml
└── requirements.txt
```

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Workflow Orchestration | LangGraph (StateGraph) |
| LLM | OpenAI GPT-4o-mini / Anthropic Claude 3.5 |
| Data Protocol | MCP (Model Context Protocol) with langchain-mcp-adapters |
| Backend | FastAPI + SSE |
| Frontend | React + Vite + Tailwind |
| Deployment | Docker Compose |

---

## Architecture Highlights

### Sequential Pipeline with Conditional Routing

```python
workflow = StateGraph(AgentState)
workflow.add_edge("customer_intelligence", "flight_optimization")
workflow.add_conditional_edges(
    "customer_intelligence",
    should_continue,  # If suppressed → END, else → continue
    {"continue": "flight_optimization", "stop": END}
)
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

1. **Start with ABC123** - Shows full happy path with all steps
2. **Show GHI654** - Pipeline stops early (suppressed customer)
3. **Click "View State"** - Shows LangGraph state passing between nodes
4. **Click each node** - See detailed reasoning in right panel
5. **Try "Take the Tour"** - Interactive tutorial in Architecture section

---

## Business Value

| What | How |
|------|-----|
| **Explainability** | Every decision has traceable reasoning |
| **Auditability** | 15+ factors documented for compliance |
| **Guardrails** | Business rules enforced in code, not prompts |
| **Hybrid AI** | Rules for speed, LLM for intelligence |
| **Future-proof** | Same architecture scales to real-time scenarios |
