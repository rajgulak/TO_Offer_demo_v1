"""
FastAPI Backend for Tailored Offers Demo

Provides REST API and SSE streaming for the React frontend.
"""
import sys
import asyncio
import json
import time
import random
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

# Add parent directory to path to import agents and tools
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.data_tools import get_enriched_pnr, get_all_reservations, get_customer
from agents.state import create_initial_state, OfferDecision
from agents.customer_intelligence import CustomerIntelligenceAgent
from agents.flight_optimization import FlightOptimizationAgent
# ReWOO Pattern: Planner-Worker-Solver for Offer Orchestration
from agents.offer_orchestration_rewoo import OfferOrchestrationReWOO as OfferOrchestrationAgent, ORCHESTRATION_SYSTEM_PROMPT
from agents.personalization import PersonalizationAgent, PERSONALIZATION_SYSTEM_PROMPT
from agents.channel_timing import ChannelTimingAgent
from agents.measurement_learning import MeasurementLearningAgent
from agents.llm_service import get_llm_provider_name, is_llm_available
from agents.workflow import USE_MCP

# Feedback loop system
from infrastructure.feedback import (
    get_feedback_manager,
    OutcomeType,
    record_offer_outcome,
    get_calibration_report,
)

# MCP client for async data loading (only import if USE_MCP is enabled)
if USE_MCP:
    from tools.mcp_client import MCPDataClient


app = FastAPI(
    title="Tailored Offers API",
    description="Backend API for the Agentic AI Demo",
    version="1.0.0"
)

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ Pydantic Models ============

class PNRSummary(BaseModel):
    pnr: str
    customer_name: str
    customer_tier: str
    route: str
    hours_to_departure: int
    scenario_tag: str


class CustomerProfile(BaseModel):
    customer_id: str
    name: str
    loyalty_tier: str
    tenure_days: int
    travel_pattern: str
    annual_revenue: float
    is_suppressed: bool
    complaint_reason: Optional[str] = None


class FlightInfo(BaseModel):
    flight_id: str
    route: str
    departure_date: str
    departure_time: str
    cabins: Dict[str, Any]


class EnrichedPNR(BaseModel):
    pnr_locator: str
    customer: CustomerProfile
    flight: FlightInfo
    hours_to_departure: int
    current_cabin: str
    ml_scores: Optional[Dict[str, Any]] = None


# ============ Agent Configuration ============

AGENT_CONFIG = [
    {
        "id": "customer_intelligence",
        "name": "Customer Intelligence",
        "short_name": "Customer",
        "icon": "brain",
        "description": "Analyzes customer eligibility and segmentation",
        "reasoning_key": "customer_reasoning",
        "phase": "decision"
    },
    {
        "id": "flight_optimization",
        "name": "Flight Optimization",
        "short_name": "Flight",
        "icon": "chart",
        "description": "Evaluates cabin inventory and flight priority",
        "reasoning_key": "flight_reasoning",
        "phase": "decision"
    },
    {
        "id": "offer_orchestration",
        "name": "Offer Orchestration",
        "short_name": "Offer",
        "icon": "scale",
        "description": "Selects optimal offer using expected value calculation",
        "reasoning_key": "offer_reasoning",
        "phase": "decision"
    },
    {
        "id": "personalization",
        "name": "Personalization",
        "short_name": "Message",
        "icon": "sparkles",
        "description": "Generates personalized messaging with GenAI",
        "reasoning_key": "personalization_reasoning",
        "phase": "decision"
    },
    {
        "id": "channel_timing",
        "name": "Channel & Timing",
        "short_name": "Channel",
        "icon": "phone",
        "description": "Optimizes delivery channel and send time",
        "reasoning_key": "channel_reasoning",
        "phase": "decision"
    },
    {
        "id": "measurement",
        "name": "Tracking Setup",
        "short_name": "Track",
        "icon": "tag",
        "description": "Attaches A/B test group and tracking ID for ROI measurement",
        "reasoning_key": "measurement_reasoning",
        "phase": "post-decision"
    }
]

# Initialize agents
agents = {
    "customer_intelligence": CustomerIntelligenceAgent(),
    "flight_optimization": FlightOptimizationAgent(),
    "offer_orchestration": OfferOrchestrationAgent(),
    "personalization": PersonalizationAgent(),
    "channel_timing": ChannelTimingAgent(),
    "measurement": MeasurementLearningAgent()
}

# Default prompts for LLM agents (for display and editing)
DEFAULT_PROMPTS = {
    "offer_orchestration": {
        "system_prompt": ORCHESTRATION_SYSTEM_PROMPT,
        "type": "llm",
        "description": "Strategic reasoning about which offer to select"
    },
    "personalization": {
        "system_prompt": PERSONALIZATION_SYSTEM_PROMPT,
        "type": "llm",
        "description": "Generates personalized messaging for the offer"
    },
    "customer_intelligence": {
        "type": "rules",
        "description": "Rules-based eligibility checks"
    },
    "flight_optimization": {
        "type": "rules",
        "description": "Rules-based inventory analysis"
    },
    "channel_timing": {
        "type": "rules",
        "description": "Rules-based channel selection"
    },
    "measurement": {
        "type": "rules",
        "description": "Deterministic A/B assignment"
    }
}

# Store for custom prompts (in production, this would be in a database)
custom_prompts: Dict[str, str] = {}


# ============ Data Loading (MCP-aware) ============

async def load_enriched_pnr(pnr_locator: str) -> Optional[Dict[str, Any]]:
    """
    Load enriched PNR data using the appropriate method.

    - USE_MCP=true: Calls MCP server via langchain-mcp-adapters
    - USE_MCP=false: Direct Python function calls (default)

    This ensures the architecture diagram matches actual data flow.
    """
    if USE_MCP:
        # Use MCP client to load data via MCP server
        client = MCPDataClient()
        return await client.get_enriched_pnr(pnr_locator)
    else:
        # Direct function call (default, faster for development)
        return get_enriched_pnr(pnr_locator)


# ============ Helper Functions ============

def get_scenario_tag(pnr: str, customer: Dict, reservation: Dict) -> str:
    """Determine scenario tag for a PNR - maps to frontend scenario descriptions"""
    # Direct mapping based on PNR to match our 6 demo scenarios
    scenario_map = {
        "ABC123": "Easy Choice",           # Baseline: clear Business EV winner
        "XYZ789": "Confidence Trade-off",  # Agent trade-off: high EV but low ML confidence
        "LMN456": "Relationship Trade-off", # Agent trade-off: high value customer with recent issue
        "DEF321": "Guardrail: Inventory",  # Guardrail blocks: 0 seats available
        "GHI654": "Guardrail: Customer",   # Guardrail blocks: customer suppressed
        "JKL789": "Price Trade-off",       # Agent trade-off: discount level decision
    }
    return scenario_map.get(pnr, "Unknown")


def extract_agent_summary(agent_id: str, state: Dict) -> str:
    """Extract a short summary for an agent's result"""
    if agent_id == "customer_intelligence":
        if state.get("customer_eligible"):
            segment = state.get("customer_segment", "unknown")
            return f"ELIGIBLE - {segment}"
        return f"NOT ELIGIBLE - {state.get('suppression_reason', 'criteria not met')}"

    elif agent_id == "flight_optimization":
        priority = state.get("flight_priority", "unknown")
        cabins = state.get("recommended_cabins", [])
        return f"{priority.upper()} priority - {', '.join(cabins) if cabins else 'no cabins'}"

    elif agent_id == "offer_orchestration":
        if state.get("should_send_offer"):
            offer = state.get("selected_offer", "")
            price = state.get("offer_price", 0)
            ev = state.get("expected_value", 0)
            return f"{offer} @ ${price:.0f} (EV: ${ev:.2f})"
        return "NO OFFER - criteria not met"

    elif agent_id == "personalization":
        tone = state.get("message_tone", "")
        return f"{tone.title()} tone - message generated"

    elif agent_id == "channel_timing":
        channel = state.get("selected_channel", "")
        send_time = state.get("send_time", "")
        return f"{channel.upper()} at {send_time}"

    elif agent_id == "measurement":
        group = state.get("experiment_group", "")
        return f"Group: {group}"

    return "Completed"


def extract_agent_outputs(agent_id: str, state: Dict) -> Dict:
    """Extract key outputs for an agent"""
    if agent_id == "customer_intelligence":
        return {
            "customer_eligible": state.get("customer_eligible"),
            "customer_segment": state.get("customer_segment"),
            "suppression_reason": state.get("suppression_reason")
        }
    elif agent_id == "flight_optimization":
        return {
            "flight_priority": state.get("flight_priority"),
            "recommended_cabins": state.get("recommended_cabins"),
            "inventory_status": state.get("inventory_status")
        }
    elif agent_id == "offer_orchestration":
        return {
            "selected_offer": state.get("selected_offer"),
            "offer_price": state.get("offer_price"),
            "discount_applied": state.get("discount_applied"),
            "expected_value": state.get("expected_value"),
            "should_send_offer": state.get("should_send_offer"),
            "fallback_offer": state.get("fallback_offer")
        }
    elif agent_id == "personalization":
        return {
            "message_subject": state.get("message_subject"),
            "message_tone": state.get("message_tone"),
            "personalization_elements": state.get("personalization_elements")
        }
    elif agent_id == "channel_timing":
        return {
            "selected_channel": state.get("selected_channel"),
            "send_time": state.get("send_time"),
            "backup_channel": state.get("backup_channel")
        }
    elif agent_id == "measurement":
        return {
            "experiment_group": state.get("experiment_group"),
            "tracking_id": state.get("tracking_id")
        }
    return {}


# ============ API Endpoints ============

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "tailored-offers-api"}


@app.get("/api/agents")
async def get_agents():
    """Get agent configuration and metadata"""
    return {"agents": AGENT_CONFIG}


@app.get("/api/llm-status")
async def get_llm_status():
    """Get LLM configuration status"""
    return {
        "llm_available": is_llm_available(),
        "provider": get_llm_provider_name()
    }


@app.get("/api/mcp-status")
async def get_mcp_status():
    """Get MCP (Model Context Protocol) status"""
    return {
        "mcp_enabled": USE_MCP,
        "data_source": "MCP Server" if USE_MCP else "Direct Function Calls",
        "description": (
            "Data loaded via MCP client/server using langchain-mcp-adapters"
            if USE_MCP else
            "Data loaded via direct Python function calls (default)"
        )
    }


@app.get("/api/system-status")
async def get_system_status():
    """Get combined system status (LLM + MCP)"""
    return {
        "llm": {
            "available": is_llm_available(),
            "provider": get_llm_provider_name()
        },
        "mcp": {
            "enabled": USE_MCP,
            "data_source": "MCP Server" if USE_MCP else "Direct"
        }
    }


@app.get("/api/agents/{agent_id}/prompt")
async def get_agent_prompt(agent_id: str):
    """Get the prompt configuration for an agent"""
    if agent_id not in DEFAULT_PROMPTS:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    prompt_config = DEFAULT_PROMPTS[agent_id]

    # If it's a rules-based agent, return that info
    if prompt_config.get("type") == "rules":
        return {
            "agent_id": agent_id,
            "type": "rules",
            "description": prompt_config["description"],
            "editable": False
        }

    # For LLM agents, return the prompt
    return {
        "agent_id": agent_id,
        "type": "llm",
        "description": prompt_config["description"],
        "system_prompt": custom_prompts.get(agent_id, prompt_config.get("system_prompt", "")),
        "is_custom": agent_id in custom_prompts,
        "default_prompt": prompt_config.get("system_prompt", ""),
        "editable": True,
        "llm_provider": get_llm_provider_name()
    }


class PromptUpdate(BaseModel):
    system_prompt: str


@app.put("/api/agents/{agent_id}/prompt")
async def update_agent_prompt(agent_id: str, update: PromptUpdate):
    """Update the prompt for an LLM agent"""
    if agent_id not in DEFAULT_PROMPTS:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    prompt_config = DEFAULT_PROMPTS[agent_id]
    if prompt_config.get("type") != "llm":
        raise HTTPException(status_code=400, detail=f"Agent {agent_id} is rules-based, not LLM")

    custom_prompts[agent_id] = update.system_prompt

    return {
        "agent_id": agent_id,
        "status": "updated",
        "message": f"Custom prompt saved for {agent_id}"
    }


@app.delete("/api/agents/{agent_id}/prompt")
async def reset_agent_prompt(agent_id: str):
    """Reset an agent's prompt to default"""
    if agent_id in custom_prompts:
        del custom_prompts[agent_id]

    return {
        "agent_id": agent_id,
        "status": "reset",
        "message": f"Prompt reset to default for {agent_id}"
    }


@app.get("/api/pnrs", response_model=List[PNRSummary])
async def list_pnrs():
    """
    List all available PNRs with summary info.

    Note: Uses direct data loading for performance (loading 6+ PNRs via MCP
    would spawn multiple server processes). The evaluate endpoint uses MCP.
    """
    reservations = get_all_reservations()
    result = []

    for res in reservations:
        # Direct call for performance in list view
        enriched = get_enriched_pnr(res["pnr_loctr_id"])
        if enriched:
            customer = enriched["customer"]
            flight = enriched["flight"]

            result.append(PNRSummary(
                pnr=res["pnr_loctr_id"],
                customer_name=f"{customer['first_name']} {customer['last_name']}",
                customer_tier=customer["loyalty_tier"],
                route=f"{flight['schd_leg_dep_airprt_iata_cd']} → {flight['schd_leg_arvl_airprt_iata_cd']}",
                hours_to_departure=res["hours_to_departure"],
                scenario_tag=get_scenario_tag(res["pnr_loctr_id"], customer, res)
            ))

    return result


@app.get("/api/pnrs/{pnr_locator}")
async def get_pnr(pnr_locator: str):
    """
    Get enriched PNR data.

    Uses MCP-aware loading (respects USE_MCP environment variable).
    """
    enriched = await load_enriched_pnr(pnr_locator)
    if not enriched:
        raise HTTPException(status_code=404, detail=f"PNR {pnr_locator} not found")

    customer = enriched["customer"]
    flight = enriched["flight"]
    reservation = enriched["pnr"]

    return {
        "pnr_locator": pnr_locator,
        "customer": {
            "lylty_acct_id": customer["lylty_acct_id"],
            "name": f"{customer['first_name']} {customer['last_name']}",
            "loyalty_tier": customer["loyalty_tier"],
            "aadv_tenure_days": customer["aadv_tenure_days"],
            "business_trip_likelihood": customer.get("business_trip_likelihood", 0),
            "flight_revenue_amt_history": customer.get("flight_revenue_amt_history", 0),
            "is_suppressed": customer.get("suppression", {}).get("is_suppressed", False),
            "complaint_reason": customer.get("suppression", {}).get("complaint_reason"),
            "marketing_consent": customer.get("marketing_consent", {}),
            "historical_upgrades": customer.get("historical_upgrades", {})
        },
        "flight": {
            "operat_flight_nbr": flight["operat_flight_nbr"],
            "route": f"{flight['schd_leg_dep_airprt_iata_cd']} → {flight['schd_leg_arvl_airprt_iata_cd']}",
            "leg_dep_dt": flight["leg_dep_dt"],
            "schd_leg_dep_lcl_tms": flight["schd_leg_dep_lcl_tms"],
            "equipment_model": flight.get("equipment_model", ""),
            "cabins": flight.get("cabins", {})
        },
        "reservation": {
            "hours_to_departure": reservation["hours_to_departure"],
            "max_bkd_cabin_cd": reservation["max_bkd_cabin_cd"],
            "fare_class": reservation.get("fare_class", ""),
            "checked_in": reservation.get("checked_in", False)
        },
        "ml_scores": enriched.get("ml_scores")
    }


@app.get("/api/pnrs/{pnr_locator}/evaluate")
async def evaluate_pnr_stream(pnr_locator: str, execution_mode: str = "choreography"):
    """
    Stream agent evaluation results using Server-Sent Events.

    Each agent's result is streamed as it completes, allowing
    real-time visualization in the frontend.

    Query params:
        execution_mode: "choreography" (default) or "planner-worker"
            - choreography: Sequential flow, each node knows next step
            - planner-worker: LLM planner decides next step dynamically

    Data loading respects USE_MCP environment variable:
    - USE_MCP=true: Data loaded via MCP client → MCP server
    - USE_MCP=false: Data loaded via direct function calls (default)
    """
    # Load data using MCP-aware loader
    enriched = await load_enriched_pnr(pnr_locator)
    if not enriched:
        async def error_generator():
            yield {
                "event": "error",
                "data": json.dumps({"error": f"PNR {pnr_locator} not found"})
            }
        return EventSourceResponse(error_generator())

    async def event_generator():
        # Initialize state with data from MCP or direct load
        state = create_initial_state(pnr_locator)
        state["customer_data"] = enriched["customer"]
        state["flight_data"] = enriched["flight"]
        state["reservation_data"] = enriched["pnr"]
        state["ml_scores"] = enriched.get("ml_scores")

        total_steps = 6
        start_time = time.time()
        data_source = "MCP" if USE_MCP else "Direct"
        is_planner_worker = execution_mode == "planner-worker"

        # Send initial event with actual data source and execution mode
        yield {
            "event": "pipeline_start",
            "data": json.dumps({
                "pnr": pnr_locator,
                "total_steps": total_steps,
                "mcp_enabled": USE_MCP,
                "data_source": data_source,
                "execution_mode": execution_mode
            })
        }

        # For planner-worker mode, emit planner events
        if is_planner_worker:
            yield {
                "event": "planner_start",
                "data": json.dumps({
                    "message": "Planner analyzing state and deciding execution plan..."
                })
            }
            await asyncio.sleep(0.3)  # Simulate planner thinking
            yield {
                "event": "planner_decision",
                "data": json.dumps({
                    "plan": ["customer_intelligence", "flight_optimization", "offer_orchestration", "personalization", "channel_timing", "measurement"],
                    "reasoning": "Standard evaluation flow - no errors detected, proceeding with full pipeline"
                })
            }

        # Process each agent
        agent_sequence = [
            ("customer_intelligence", agents["customer_intelligence"], "customer_reasoning"),
            ("flight_optimization", agents["flight_optimization"], "flight_reasoning"),
            ("offer_orchestration", agents["offer_orchestration"], "offer_reasoning"),
            ("personalization", agents["personalization"], "personalization_reasoning"),
            ("channel_timing", agents["channel_timing"], "channel_reasoning"),
            ("measurement", agents["measurement"], "measurement_reasoning"),
        ]

        for step, (agent_id, agent, reasoning_key) in enumerate(agent_sequence, 1):
            config = next((a for a in AGENT_CONFIG if a["id"] == agent_id), {})

            # Send agent_start event
            yield {
                "event": "agent_start",
                "data": json.dumps({
                    "agent_id": agent_id,
                    "agent_name": config.get("name", agent_id),
                    "step": step,
                    "total_steps": total_steps
                })
            }

            # Minimal delay for visual feedback (workflows are instant)
            # Note: Personalization agent has real LLM latency when API key is set
            await asyncio.sleep(0.15)  # 150ms - just enough for UI to show "processing"

            # Run agent
            agent_start = time.time()
            try:
                result = agent.analyze(state)
                state.update(result)
                duration_ms = int((time.time() - agent_start) * 1000)

                # Send agent_complete event
                yield {
                    "event": "agent_complete",
                    "data": json.dumps({
                        "agent_id": agent_id,
                        "agent_name": config.get("name", agent_id),
                        "step": step,
                        "status": "complete",
                        "duration_ms": duration_ms,
                        "summary": extract_agent_summary(agent_id, state),
                        "reasoning": state.get(reasoning_key, ""),
                        "outputs": extract_agent_outputs(agent_id, state)
                    })
                }

                # Check for early termination conditions
                if agent_id == "customer_intelligence" and not state.get("customer_eligible"):
                    # Skip remaining agents
                    for skip_step, (skip_id, _, _) in enumerate(agent_sequence[step:], step + 1):
                        skip_config = next((a for a in AGENT_CONFIG if a["id"] == skip_id), {})
                        yield {
                            "event": "agent_skip",
                            "data": json.dumps({
                                "agent_id": skip_id,
                                "agent_name": skip_config.get("name", skip_id),
                                "step": skip_step,
                                "reason": "Customer not eligible"
                            })
                        }
                    break

                if agent_id == "offer_orchestration" and not state.get("should_send_offer"):
                    # Skip remaining agents
                    for skip_step, (skip_id, _, _) in enumerate(agent_sequence[step:], step + 1):
                        skip_config = next((a for a in AGENT_CONFIG if a["id"] == skip_id), {})
                        yield {
                            "event": "agent_skip",
                            "data": json.dumps({
                                "agent_id": skip_id,
                                "agent_name": skip_config.get("name", skip_id),
                                "step": skip_step,
                                "reason": "No offer to send"
                            })
                        }
                    break

            except Exception as e:
                yield {
                    "event": "agent_error",
                    "data": json.dumps({
                        "agent_id": agent_id,
                        "step": step,
                        "error": str(e)
                    })
                }
                break

        # Compile final decision
        total_duration = int((time.time() - start_time) * 1000)

        final_decision = None
        if state.get("should_send_offer"):
            final_decision = {
                "should_send_offer": True,
                "offer_type": state.get("selected_offer"),
                "price": state.get("offer_price"),
                "discount_percent": state.get("discount_applied"),
                "channel": state.get("selected_channel"),
                "send_time": state.get("send_time"),
                "message_subject": state.get("message_subject"),
                "message_body": state.get("message_body"),
                "fallback_offer": state.get("fallback_offer"),
                "experiment_group": state.get("experiment_group"),
                "tracking_id": state.get("tracking_id")
            }
        else:
            final_decision = {
                "should_send_offer": False,
                "suppression_reason": state.get("suppression_reason", "Offer criteria not met")
            }

        yield {
            "event": "pipeline_complete",
            "data": json.dumps({
                "success": True,
                "final_decision": final_decision,
                "total_duration_ms": total_duration,
                "reasoning_trace": state.get("reasoning_trace", [])
            })
        }

    return EventSourceResponse(event_generator())


# ============ Outcome Capture API (Feedback Loop) ============

class OutcomeRequest(BaseModel):
    """Request to record an offer outcome."""
    pnr: str
    customer_id: str
    offer_type: str
    offer_price: float
    expected_probability: float
    expected_value: float
    outcome: str  # "accepted", "rejected", "expired", "clicked"
    channel: str = "unknown"
    discount_percent: float = 0.0
    customer_tier: Optional[str] = None
    experiment_group: Optional[str] = None
    customer_feedback: Optional[str] = None


class OutcomeUpdateRequest(BaseModel):
    """Request to update an existing outcome."""
    outcome: str  # "accepted", "rejected", "expired"
    customer_feedback: Optional[str] = None


@app.post("/api/outcomes")
async def record_outcome(request: OutcomeRequest):
    """
    Record the outcome of an offer.

    This is the critical feedback loop endpoint.
    Call this when a customer accepts, rejects, or ignores an offer.

    Example:
        POST /api/outcomes
        {
            "pnr": "ABC123",
            "customer_id": "CUST456",
            "offer_type": "IU_BUSINESS",
            "offer_price": 299.00,
            "expected_probability": 0.25,
            "expected_value": 74.75,
            "outcome": "accepted",
            "channel": "email"
        }
    """
    try:
        outcome_type = OutcomeType(request.outcome)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid outcome: {request.outcome}. Must be one of: accepted, rejected, expired, clicked, pending"
        )

    feedback = get_feedback_manager()

    outcome = feedback.record_outcome(
        pnr=request.pnr,
        customer_id=request.customer_id,
        offer_type=request.offer_type,
        offer_price=request.offer_price,
        expected_probability=request.expected_probability,
        expected_value=request.expected_value,
        outcome=outcome_type,
        channel=request.channel,
        discount_percent=request.discount_percent,
        customer_tier=request.customer_tier,
        experiment_group=request.experiment_group,
        customer_feedback=request.customer_feedback,
    )

    return {
        "status": "recorded",
        "outcome_id": outcome.outcome_id,
        "pnr": outcome.pnr,
        "outcome": outcome.actual_outcome.value,
        "actual_value": outcome.actual_value,
        "prediction_error": outcome.prediction_error,
    }


@app.get("/api/outcomes/{pnr}")
async def get_outcome(pnr: str):
    """
    Get the recorded outcome for a specific PNR.

    Returns the complete outcome record including prediction vs actual.
    """
    feedback = get_feedback_manager()
    outcome = feedback.get_outcome(pnr)

    if not outcome:
        raise HTTPException(status_code=404, detail=f"No outcome recorded for PNR {pnr}")

    return outcome.to_dict()


@app.put("/api/outcomes/{pnr}")
async def update_outcome(pnr: str, request: OutcomeUpdateRequest):
    """
    Update the outcome for a pending offer.

    Use this when outcome information arrives later (e.g., async conversion tracking).
    """
    try:
        outcome_type = OutcomeType(request.outcome)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid outcome: {request.outcome}"
        )

    feedback = get_feedback_manager()
    outcome = feedback.update_outcome(
        pnr=pnr,
        outcome=outcome_type,
        customer_feedback=request.customer_feedback,
    )

    if not outcome:
        raise HTTPException(status_code=404, detail=f"No outcome found for PNR {pnr}")

    return {
        "status": "updated",
        "pnr": pnr,
        "outcome": outcome.actual_outcome.value,
    }


@app.get("/api/outcomes/customer/{customer_id}")
async def get_customer_outcomes(customer_id: str):
    """
    Get all recorded outcomes for a specific customer.

    Useful for understanding customer behavior patterns.
    """
    feedback = get_feedback_manager()
    outcomes = feedback.get_customer_history(customer_id)

    return {
        "customer_id": customer_id,
        "total_outcomes": len(outcomes),
        "outcomes": [o.to_dict() for o in outcomes],
    }


@app.get("/api/outcomes/stats")
async def get_outcome_stats(days: int = 30):
    """
    Get summary statistics for outcomes.

    Query params:
        days: Number of days to analyze (default: 30)

    Returns aggregate metrics including acceptance rate, revenue, and value capture.
    """
    feedback = get_feedback_manager()
    stats = feedback.get_summary_stats(days=days)

    return stats


@app.get("/api/calibration")
async def get_calibration(days: int = 30):
    """
    Get a calibration report for agent predictions.

    Calibration measures how well predicted probabilities match actual outcomes.
    A well-calibrated model predicting 30% acceptance should see ~30% actual.

    Query params:
        days: Number of days to analyze (default: 30)

    Returns:
        - Calibration buckets with predicted vs actual rates
        - Overall calibration metrics (ECE, Brier score)
        - Value capture analysis
        - Segmented analysis by offer type, tier, channel
    """
    report = get_calibration_report(days=days)
    return report.to_dict()


@app.get("/api/feedback/{agent_name}")
async def get_agent_feedback(agent_name: str, prompt_version: Optional[str] = None, days: int = 30):
    """
    Get feedback for a specific agent to improve.

    This endpoint provides actionable recommendations based on actual outcomes.

    Query params:
        prompt_version: Specific prompt version to analyze (optional)
        days: Number of days to analyze (default: 30)

    Returns:
        - Success rate and calibration metrics
        - Whether agent is overconfident or underconfident
        - Confidence adjustment recommendation
        - Specific improvement recommendations
        - Best/worst performing segments
    """
    feedback = get_feedback_manager()
    agent_feedback = feedback.get_agent_feedback(
        agent_name=agent_name,
        prompt_version=prompt_version,
        days=days,
    )

    return agent_feedback.to_dict()


# ============ Human-in-the-Loop (HITL) API ============
#
# These endpoints enable true human-in-the-loop workflows:
# 1. Pending approvals queue
# 2. Approve/deny actions
# 3. Resume workflow after approval
#
# Flow:
#   1. POST /api/pnrs/{pnr}/evaluate-hitl → May return "pending_approval"
#   2. GET /api/approvals/pending → List pending approvals
#   3. POST /api/approvals/{id}/approve or /api/approvals/{id}/deny
#   4. POST /api/approvals/{id}/resume → Complete the workflow
# ============

from infrastructure.human_in_loop import (
    get_hitl_manager,
    ApprovalStatus,
)
from agents.workflow import (
    run_offer_evaluation_with_hitl,
    resume_after_approval,
    handle_denial,
)


class ApprovalDecisionRequest(BaseModel):
    """Request to approve or deny a pending approval."""
    decided_by: str  # User ID or email
    notes: Optional[str] = None
    modified_offer: Optional[Dict[str, Any]] = None  # Human can modify the offer


@app.get("/api/pnrs/{pnr_locator}/evaluate-hitl")
async def evaluate_pnr_with_hitl(pnr_locator: str, force_approval: bool = False):
    """
    Evaluate a PNR with Human-in-the-Loop support.

    This endpoint runs the full evaluation but may halt for human approval
    if the offer triggers escalation rules (high-value, VIP, etc.).

    Query params:
        force_approval: Force human approval regardless of rules (for testing)

    Returns:
        - If approval needed: {"status": "pending_approval", "approval_request_id": "..."}
        - If no approval needed: Normal evaluation result
    """
    result = run_offer_evaluation_with_hitl(
        pnr_locator=pnr_locator,
        force_approval=force_approval,
    )
    return result


@app.get("/api/approvals/pending")
async def get_pending_approvals():
    """
    Get all pending approval requests.

    Returns a list of approval requests waiting for human decision.
    Use this to populate an approval queue UI.
    """
    hitl = get_hitl_manager()
    pending = hitl.get_pending_requests()

    return {
        "pending_count": len(pending),
        "approvals": [req.to_dict() for req in pending],
    }


@app.get("/api/approvals/{request_id}")
async def get_approval_request(request_id: str):
    """
    Get details of a specific approval request.

    Returns full details including proposed offer, risk factors, and status.
    """
    hitl = get_hitl_manager()
    request = hitl.get_request(request_id)

    if not request:
        raise HTTPException(status_code=404, detail=f"Approval request {request_id} not found")

    return request.to_dict()


@app.post("/api/approvals/{request_id}/approve")
async def approve_request(request_id: str, decision: ApprovalDecisionRequest):
    """
    Approve a pending approval request.

    After approval, call /api/approvals/{request_id}/resume to complete the workflow.

    Body:
        decided_by: User ID or email of approver
        notes: Optional approval notes
        modified_offer: Optional modified offer (human can adjust)
    """
    hitl = get_hitl_manager()
    request = hitl.approve(
        request_id=request_id,
        decided_by=decision.decided_by,
        notes=decision.notes,
        modified_offer=decision.modified_offer,
    )

    if not request:
        raise HTTPException(
            status_code=400,
            detail="Could not approve request - may not exist, already resolved, or expired"
        )

    return {
        "status": "approved",
        "request_id": request_id,
        "approved_by": decision.decided_by,
        "message": "Request approved. Call /api/approvals/{request_id}/resume to complete workflow.",
    }


@app.post("/api/approvals/{request_id}/deny")
async def deny_request(request_id: str, decision: ApprovalDecisionRequest):
    """
    Deny a pending approval request.

    The offer will not be delivered. Workflow state is cleaned up.

    Body:
        decided_by: User ID or email of denier
        notes: Optional denial reason
    """
    hitl = get_hitl_manager()
    request = hitl.deny(
        request_id=request_id,
        decided_by=decision.decided_by,
        notes=decision.notes,
    )

    if not request:
        raise HTTPException(
            status_code=400,
            detail="Could not deny request - may not exist, already resolved, or expired"
        )

    # Handle denial and get final result
    result = handle_denial(request_id)

    return {
        "status": "denied",
        "request_id": request_id,
        "denied_by": decision.decided_by,
        "pnr": request.pnr,
        "result": result,
    }


@app.post("/api/approvals/{request_id}/resume")
async def resume_approved_workflow(request_id: str):
    """
    Resume a workflow after approval.

    This loads the saved workflow state and completes the offer delivery.
    Only works for approved requests.

    Returns the final workflow result with offer delivered.
    """
    result = resume_after_approval(request_id)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@app.get("/api/approvals/stats")
async def get_approval_stats():
    """
    Get statistics about approval requests.

    Returns counts by status and by reason.
    """
    hitl = get_hitl_manager()
    stats = hitl.get_stats()
    return stats


@app.get("/api/approvals/pnr/{pnr}")
async def get_approvals_by_pnr(pnr: str):
    """
    Get all approval requests for a specific PNR.

    Returns historical approval requests including resolved ones.
    """
    hitl = get_hitl_manager()
    requests = hitl.get_requests_by_pnr(pnr)

    return {
        "pnr": pnr,
        "total": len(requests),
        "approvals": [req.to_dict() for req in requests],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
