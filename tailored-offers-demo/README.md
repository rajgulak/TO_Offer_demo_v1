# Tailored Offers - Agentic AI Demo

This demo application showcases a 6-agent architecture for American Airlines' Tailored Offers system, demonstrating how agentic AI adds value beyond ML models alone.

## Quick Start

### Option 1: Docker (Recommended)

```bash
# Build and run everything (mock mode - no API keys needed)
docker-compose up --build

# Open browser to http://localhost:3000
```

**With LLM Reasoning (optional):**
```bash
# Create .env file with your API key
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY or ANTHROPIC_API_KEY

# Run with LLM
docker-compose up --build
```

### Option 2: Local Development

**Terminal 1 - Start API:**
```bash
# Install Python dependencies
pip install -r requirements.txt
pip install -r api/requirements.txt

# Optional: Set API key for real LLM reasoning
export OPENAI_API_KEY=sk-your-key-here
# OR
export ANTHROPIC_API_KEY=sk-ant-your-key-here

# Start the API server
python -m uvicorn api.main:app --port 8000
```

**Terminal 2 - Start Frontend:**
```bash
cd frontend
npm install
npm run dev

# Open browser to http://localhost:5173
```

### Option 3: CLI Demo (No UI)

```bash
pip install -r requirements.txt
python run_demo.py --pnr ABC123
python run_demo.py --all  # Run all scenarios
```

---

## Hybrid Architecture: Rules + LLM Reasoning

This demo showcases a **hybrid approach** - combining fast rules-based agents with LLM-powered reasoning agents:

### Agent Types

| Agent | Type | Why |
|-------|------|-----|
| **Customer Intelligence** | ⚡ Rules | Fast eligibility checks, deterministic |
| **Flight Optimization** | ⚡ Rules | Inventory analysis, business rules |
| **Offer Orchestration** | 🧠 LLM | Strategic reasoning about optimal offers |
| **Personalization** | 🧠 LLM | GenAI for personalized messaging |
| **Channel & Timing** | ⚡ Rules | Channel selection rules |
| **Measurement** | ⚡ Rules | Deterministic A/B assignment |

### Why Hybrid?

| Benefit | Explanation |
|---------|-------------|
| **Performance** | Rules agents run in milliseconds |
| **Intelligence** | LLM agents handle complex decisions |
| **Cost Efficient** | Only use LLM where it adds value |
| **Graceful Degradation** | Works without API keys (mock mode) |

### LLM Configuration

```bash
# Option 1: OpenAI
export OPENAI_API_KEY=sk-your-key-here

# Option 2: Anthropic (Claude)
export ANTHROPIC_API_KEY=sk-ant-your-key-here

# No key = Mock mode (simulated LLM responses)
```

---

## What This Demo Shows

### MVP1 Key Messages

1. **Existing Systems Unchanged** - Agents call existing systems via MCP Tools
2. **Hybrid Architecture** - Rules for speed, LLM for intelligence
3. **Full Explainability** - Every decision has a traceable reasoning chain

### The 5 Demo Scenarios

| PNR | Customer | What It Demonstrates | Expected Outcome |
|-----|----------|---------------------|------------------|
| **ABC123** | Sarah (Gold) | Full happy path - all 6 agents | ✅ Business @ $171 |
| **XYZ789** | John (Platinum Pro) | Behavioral adaptation - price adjustment | ✅ Business @ $165 |
| **LMN456** | Emily (Exec Platinum) | High-value treatment - premium channel | ✅ Business @ $770 |
| **DEF321** | Michael (General) | Cold start + inventory constraint | ❌ No offer |
| **GHI654** | Lisa (Platinum) | Suppression - customer protection | ❌ No offer |

### Recommended Demo Flow

1. **Start with ABC123** - Show the full happy path with all 6 agents
2. **Show GHI654** - Pipeline stops early (suppressed customer)
3. **Show DEF321** - Cold start handling + inventory awareness
4. **Show XYZ789** - Behavioral adaptation (follow-up pricing)
5. **Show LMN456** - High-value treatment

---

## Architecture: State-Based Choreography

**Key Concept**: There is NO "boss" agent. Instead, agents pass a **Shared State Object** like a baton in a relay race.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     STATE-BASED CHOREOGRAPHY                             │
│         LangGraph manages the State Object + Agent Sequence              │
│                                                                          │
│   📦 State → [Agent 1] → 📦 State → [Agent 2] → 📦 State → ...          │
│                                                                          │
│   • Each agent reads state, does ONE focused job, updates state          │
│   • Short, accurate prompts (no complex "orchestrator" prompt)           │
│   • Easy to test, debug, and modify individual agents                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         AGENT LAYER (Reasoning)                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────┐ ┌──────┐ │
│  │ Customer │→│  Flight  │→│  Offer   │→│ Personal-│→│Channel│→│Measure│ │
│  │  Intel   │ │  Optim.  │ │  Orch.   │ │ ization  │ │Timing │ │Learn  │ │
│  │  ⚡Rules │ │  ⚡Rules │ │  🧠 LLM  │ │  🧠 LLM  │ │⚡Rules│ │⚡Rules│ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────┘ └──────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                          Agents call MCP Tools
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         MCP TOOL LAYER (Interface)                       │
│   get_customer_profile() │ get_propensity_scores() │ get_inventory()    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    EXISTING SYSTEMS (UNCHANGED)                          │
│        AADV DB    │    ML Model    │    DCSID    │    RM Engine         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Why State-Based Choreography (not Central Orchestration)?

| Central Orchestration ❌ | State-Based Choreography ✅ |
|--------------------------|----------------------------|
| One "supervisor" agent calls all shots | Each agent has ONE focused job |
| Requires huge, complex prompts | Short, accurate prompts |
| Single point of failure | Agents are independent & testable |
| Hard to debug and maintain | Easy to add/modify agents |

### The 6 Agents

| Agent | Type | Purpose | MCP Tools Used |
|-------|------|---------|----------------|
| **Customer Intelligence** | ⚡ Rules | Eligibility & segmentation | `get_customer_profile`, `get_suppression_status` |
| **Flight Optimization** | ⚡ Rules | Capacity analysis | `get_flight_inventory`, `get_pricing` |
| **Offer Orchestration** | 🧠 LLM | Multi-offer arbitration | `get_propensity_scores`, `get_pricing` |
| **Personalization** | 🧠 LLM | GenAI messaging | `get_customer_profile` |
| **Channel & Timing** | ⚡ Rules | Delivery optimization | `get_consent_status`, `get_engagement_history` |
| **Measurement** | ⚡ Rules | A/B testing & feedback | `assign_experiment` |

---

## Why Agents vs Rule Engine?

| Rule Engine | LLM Agent Reasoning |
|-------------|---------------------|
| `if P(buy) > 0.5: send_offer()` | "Given price sensitivity + inventory needs, Business EV ($122) > MCE EV ($29)" |
| Fixed thresholds | Holistic context-aware decisions |
| Can't explain WHY | Full audit trail with reasoning |
| Breaks on edge cases | Graceful fallbacks |

**Key insight:** ML gives you a score. LLM Agents give you decisions + explanations.

---

## Feedback Loop Patterns

### How Do Agents Learn?

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        FORWARD FLOW                                      │
│   Agent 1 → Agent 2 → Agent 3 (LLM) → Agent 4 → Decision                │
└─────────────────────────────────────────────────────────────────────────┘
                    ↑                                  │
                    │         FEEDBACK LOOPS           │
                    │                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Intra-Pipeline    │    Post-Decision      │    Continuous Learning    │
│  (Agent Conflict)  │    (Customer Action)  │    (ML Retraining)        │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1. Intra-Pipeline Feedback (Agent Disagreement)

**Question:** *"What if Agent 3 disagrees with Agent 2's recommendation?"*

| Mechanism | How It Works |
|-----------|--------------|
| **Shared State** | Each agent sees all prior decisions + reasoning in the state object |
| **LangGraph Routing** | Conditional edges can loop back to earlier agents if conflict detected |
| **Example** | Offer Orchestration recommends Business, but Channel Agent sees no email consent → State updated → Could trigger re-evaluation |

**Code Pattern (LangGraph):**
```python
# Conditional routing based on agent output
workflow.add_conditional_edges(
    "channel_timing",
    should_reconsider_offer,  # Returns "offer_orchestration" if conflict
    {
        "continue": "measurement",
        "reconsider": "offer_orchestration"  # Loop back!
    }
)
```

### 2. Post-Decision Feedback (Customer Response)

**Question:** *"How do agents learn from what customers actually do?"*

| Stage | What Happens |
|-------|--------------|
| **Offer Sent** | Measurement Agent assigns tracking ID, experiment group |
| **Customer Action** | Accept / Reject / Ignore → logged to analytics |
| **Outcome Captured** | Revenue, conversion, engagement metrics stored |
| **Model Update** | P(buy) scores refined with new outcome data |

### 3. Continuous Learning Cycle

```
Offer Sent → Customer Action → Outcome Logged → ML Retrained → Better P(buy) → Better Decisions
     ↑                                                                              │
     └──────────────────────────────────────────────────────────────────────────────┘
```

**Key Components:**

| Component | Role in Feedback |
|-----------|------------------|
| **Measurement Agent** | Assigns A/B test groups, generates tracking IDs |
| **Analytics Pipeline** | Captures outcomes (accept/reject/revenue) |
| **ML Training** | Retrains propensity models with new data |
| **LLM Context** | Can include historical outcomes in prompts for better reasoning |

### Future: Reinforcement Learning

For MVP-2+, agents could learn directly from outcomes:

```python
# Pseudo-code for RL feedback
def update_agent_policy(offer_made, customer_response, revenue):
    if customer_response == "accepted":
        reward = revenue
    elif customer_response == "rejected":
        reward = -cost_of_rejection
    else:
        reward = -cost_of_annoyance

    agent.update_policy(reward)  # Reinforce good decisions
```

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Workflow Orchestration** | LangGraph | Agent graph, conditional routing |
| **LLM Integration** | OpenAI / Anthropic | Reasoning & generation |
| **Durable Execution** | Temporal (future) | Reliability, retries |
| **Backend** | FastAPI + SSE | Real-time streaming |
| **Frontend** | React + Vite + Tailwind | Modern UI |
| **Deployment** | Docker Compose | Easy setup |

---

## Project Structure

```
tailored-offers-demo/
├── api/                    # FastAPI backend
│   ├── main.py            # API endpoints + SSE streaming
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/              # React + Vite UI
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── hooks/         # SSE hook
│   │   └── types/         # TypeScript types
│   ├── package.json
│   └── Dockerfile
├── agents/                # The 6 agents
│   ├── customer_intelligence.py   # ⚡ Rules
│   ├── flight_optimization.py     # ⚡ Rules
│   ├── offer_orchestration.py     # 🧠 LLM
│   ├── personalization.py         # 🧠 LLM
│   ├── channel_timing.py          # ⚡ Rules
│   ├── measurement_learning.py    # ⚡ Rules
│   ├── llm_service.py             # LLM provider abstraction
│   ├── state.py
│   └── workflow.py
├── tools/                 # Data access (MCP tool simulation)
│   └── data_tools.py
├── data/                  # Mock data (JSON)
├── docker-compose.yml     # Run everything with Docker
├── .env.example           # Environment variable template
├── run_demo.py           # CLI entry point
└── requirements.txt
```

---

## Deployment Options

### For Demo on Organization Laptop

**Option A: Docker (Easiest)**
```bash
# Requires: Docker Desktop installed
git clone <repo-url>
cd tailored-offers-demo

# Without LLM (mock mode)
docker-compose up --build

# With LLM reasoning
cp .env.example .env
# Edit .env and add OPENAI_API_KEY or ANTHROPIC_API_KEY
docker-compose up --build

# Open http://localhost:3000
```

**Option B: Manual Setup**
```bash
# Requires: Python 3.10+, Node.js 18+
git clone <repo-url>
cd tailored-offers-demo

# Backend
pip install -r requirements.txt
pip install -r api/requirements.txt

# Optional: Enable LLM
export OPENAI_API_KEY=sk-your-key

# Frontend
cd frontend && npm install && cd ..

# Run (2 terminals)
python -m uvicorn api.main:app --port 8000
cd frontend && npm run dev
```

---

## Key Business Value

1. **Immediate (Tier 1)**: Arbitration, personalization, channel optimization at T-72/48/24 hours
2. **Future (Tier 2)**: Real-time scenarios (lounge offers, IROP handling) when infrastructure exists

The agent architecture built for MVP-1 is **future-proof** - same architecture enables real-time scenarios when business invests in infrastructure.
