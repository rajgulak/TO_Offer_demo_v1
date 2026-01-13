# Tailored Offers - Agentic AI Demo

This demo application showcases a 6-agent architecture for American Airlines' Tailored Offers system, demonstrating how agentic AI adds value beyond ML models alone.

## Quick Start

### Option 1: Docker (Recommended)

```bash
# Build and run everything
docker-compose up --build

# Open browser to http://localhost:3000
```

### Option 2: Local Development

**Terminal 1 - Start API:**
```bash
# Install Python dependencies
pip install -r requirements.txt
pip install -r api/requirements.txt

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

## What This Demo Shows

### MVP1 Key Messages

1. **Existing Systems Unchanged** - Agents call existing systems via MCP Tools
2. **Agent Reasoning** - Not just rules, but contextual decision-making
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

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         AGENT LAYER (Reasoning)                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────┐ ┌──────┐ │
│  │ Customer │→│  Flight  │→│  Offer   │→│ Personal-│→│Channel│→│Measure│ │
│  │  Intel   │ │  Optim.  │ │  Orch.   │ │ ization  │ │Timing │ │Learn  │ │
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

### The 6 Agents

| Agent | Purpose | MCP Tools Used |
|-------|---------|----------------|
| **Customer Intelligence** | Eligibility & segmentation | `get_customer_profile`, `get_suppression_status` |
| **Flight Optimization** | Capacity analysis | `get_flight_inventory`, `get_pricing` |
| **Offer Orchestration** | Multi-offer arbitration | `get_propensity_scores`, `get_pricing` |
| **Personalization** | GenAI messaging | `get_customer_profile` |
| **Channel & Timing** | Delivery optimization | `get_consent_status`, `get_engagement_history` |
| **Measurement** | A/B testing & feedback | `assign_experiment` |

---

## Why Agents vs Rule Engine?

| Rule Engine | Agent Reasoning |
|-------------|-----------------|
| `if P(buy) > 0.5: send_offer()` | "Business EV ($122) > MCE EV ($29), lead with Business" |
| Fixed thresholds | Context-aware decisions |
| Can't explain WHY | Full audit trail |
| Breaks on edge cases | Graceful fallbacks |

**Key insight:** ML gives you a score. Agents give you decisions + explanations.

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
│   ├── customer_intelligence.py
│   ├── flight_optimization.py
│   ├── offer_orchestration.py
│   ├── personalization.py
│   ├── channel_timing.py
│   ├── measurement_learning.py
│   ├── state.py
│   └── workflow.py
├── tools/                 # Data access (MCP tool simulation)
│   └── data_tools.py
├── data/                  # Mock data (JSON)
├── docker-compose.yml     # Run everything with Docker
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
