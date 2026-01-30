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
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

# Add parent directory to path to import agents and tools
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.data_tools import get_enriched_pnr, get_all_reservations, get_customer
from agents.state import create_initial_state, OfferDecision

# New architecture: Pre-checks (workflow) → Offer Agent (ReWOO) → Delivery (workflow)
from agents.prechecks import (
    check_customer_eligibility,
    check_inventory_availability,
    generate_precheck_reasoning,
)
from agents.delivery import (
    generate_message,
    select_channel,
    setup_tracking,
    generate_delivery_reasoning,
)
# ReWOO Pattern: Planner-Worker-Solver for Offer Agent
from agents.offer_orchestration_rewoo import (
    OfferOrchestrationReWOO as OfferAgent,
    ORCHESTRATION_SYSTEM_PROMPT,
    stream_offer_orchestration,
)
# Legacy imports for backward compatibility (keeping old agent classes available)
from agents.customer_intelligence import CustomerIntelligenceAgent
from agents.flight_optimization import FlightOptimizationAgent
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

# Prompt service for dynamic prompt management
from config.prompt_service import (
    PromptService,
    set_custom_prompt,
    reset_prompt,
    is_prompt_custom,
)

# Policy configuration service
from config.policy_config import (
    PolicyService,
    get_policy,
    set_policy,
    get_all_policies,
    reset_policy,
    POLICY_METADATA,
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

# Mount static files for pre-generated audio
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


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


# ============ Pipeline Configuration ============
# New architecture: Pre-checks → Offer Agent → Delivery

PIPELINE_CONFIG = {
    "phases": [
        {
            "id": "prechecks",
            "name": "Pre-flight Checks",
            "short_name": "Checks",
            "icon": "shield",
            "description": "Validate eligibility and inventory before proceeding",
            "type": "workflow",
            "steps": ["eligibility", "inventory"]
        },
        {
            "id": "offer_agent",
            "name": "Offer Agent",
            "short_name": "Agent",
            "icon": "brain",
            "description": "ReWOO agent that plans, evaluates, and decides",
            "type": "agent",
            "steps": ["planner", "worker", "solver"]
        },
        {
            "id": "delivery",
            "name": "Delivery",
            "short_name": "Deliver",
            "icon": "send",
            "description": "Generate message, select channel, setup tracking",
            "type": "workflow",
            "steps": ["message", "channel", "tracking"]
        }
    ]
}

# Legacy AGENT_CONFIG for backward compatibility with existing frontend
AGENT_CONFIG = [
    {
        "id": "prechecks",
        "name": "Pre-flight Checks",
        "short_name": "Checks",
        "icon": "shield",
        "description": "Customer eligibility and inventory validation",
        "reasoning_key": "precheck_reasoning",
        "phase": "pre-decision",
        "is_workflow": True
    },
    {
        "id": "offer_agent",
        "name": "Offer Agent",
        "short_name": "Agent",
        "icon": "brain",
        "description": "ReWOO agent: Plans evaluations, executes, makes decision",
        "reasoning_key": "offer_reasoning",
        "phase": "decision",
        "is_workflow": False
    },
    {
        "id": "delivery",
        "name": "Delivery",
        "short_name": "Deliver",
        "icon": "send",
        "description": "Message generation, channel selection, tracking setup",
        "reasoning_key": "delivery_reasoning",
        "phase": "post-decision",
        "is_workflow": True
    }
]

# Initialize the Offer Agent (the only true agent)
offer_agent = OfferAgent()

# Legacy agent instances for backward compatibility
agents = {
    "customer_intelligence": CustomerIntelligenceAgent(),
    "flight_optimization": FlightOptimizationAgent(),
    "offer_orchestration": offer_agent,
    "offer_agent": offer_agent,  # New name
    "personalization": PersonalizationAgent(),
    "channel_timing": ChannelTimingAgent(),
    "measurement": MeasurementLearningAgent()
}

# Default prompts for LLM-based components
DEFAULT_PROMPTS = {
    "offer_agent": {
        "system_prompt": ORCHESTRATION_SYSTEM_PROMPT,
        "type": "llm",
        "description": "ReWOO agent for offer decision-making"
    },
    "offer_orchestration": {  # Legacy key
        "system_prompt": ORCHESTRATION_SYSTEM_PROMPT,
        "type": "llm",
        "description": "Strategic reasoning about which offer to select"
    },
    "personalization": {
        "system_prompt": PERSONALIZATION_SYSTEM_PROMPT,
        "type": "llm",
        "description": "Generates personalized messaging for the offer"
    },
    "prechecks": {
        "type": "workflow",
        "description": "Rules-based eligibility and inventory checks"
    },
    "delivery": {
        "type": "workflow",
        "description": "Message generation, channel selection, tracking"
    }
}

# Prompt key mapping: maps frontend agent_id to PromptService keys
PROMPT_KEY_MAP = {
    "offer_orchestration": "offer_orchestration.planner",
    "offer_orchestration.planner": "offer_orchestration.planner",
    "offer_orchestration.worker": "offer_orchestration.worker",
    "offer_orchestration.solver": "offer_orchestration.solver",
    "personalization": "personalization.system",
}

# Extended prompts info for ReWOO phases (used by frontend)
REWOO_PROMPTS = {
    "offer_orchestration.planner": {
        "type": "llm",
        "name": "Planner",
        "description": "Analyzes customer data and creates evaluation plan",
        "icon": "📋",
    },
    "offer_orchestration.worker": {
        "type": "llm",
        "name": "Worker",
        "description": "Executes evaluation steps (confidence, relationship, pricing)",
        "icon": "⚙️",
    },
    "offer_orchestration.solver": {
        "type": "llm",
        "name": "Solver",
        "description": "Synthesizes evidence and makes final offer decision",
        "icon": "✅",
    },
    "personalization": {
        "type": "llm",
        "name": "Message",
        "description": "Generates personalized upgrade offer messages",
        "icon": "💬",
    },
}


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
        "JKL789": "⚠️ Recent Delay",       # Demo: Agent gap - customer had 3hr delay yesterday
    }
    return scenario_map.get(pnr, "Unknown")


def extract_agent_summary(agent_id: str, state: Dict) -> str:
    """Extract a short summary for an agent's/phase's result"""
    # New phase-based IDs
    if agent_id == "prechecks":
        eligible = state.get("customer_eligible", False)
        has_inventory = bool(state.get("recommended_cabins"))
        if not eligible:
            return f"BLOCKED - {state.get('suppression_reason', 'not eligible')}"
        if not has_inventory:
            return "BLOCKED - no inventory"
        return f"PASSED - {state.get('customer_segment', 'eligible')}, {len(state.get('recommended_cabins', []))} cabins"

    elif agent_id in ["offer_agent", "offer_orchestration"]:
        if state.get("should_send_offer"):
            offer = state.get("selected_offer", "")
            price = state.get("offer_price", 0)
            ev = state.get("expected_value", 0)
            return f"{offer} @ ${price:.0f} (EV: ${ev:.2f})"
        return "NO OFFER - criteria not met"

    elif agent_id == "delivery":
        channel = state.get("selected_channel", "")
        if channel:
            return f"{channel.upper()} - ready to send"
        return "Skipped - no offer"

    # Legacy agent IDs for backward compatibility
    elif agent_id == "customer_intelligence":
        if state.get("customer_eligible"):
            segment = state.get("customer_segment", "unknown")
            return f"ELIGIBLE - {segment}"
        return f"NOT ELIGIBLE - {state.get('suppression_reason', 'criteria not met')}"

    elif agent_id == "flight_optimization":
        priority = state.get("flight_priority", "unknown")
        cabins = state.get("recommended_cabins", [])
        return f"{priority.upper()} priority - {', '.join(cabins) if cabins else 'no cabins'}"

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
    """Extract key outputs for an agent/phase"""
    # New phase-based IDs
    if agent_id == "prechecks":
        return {
            "customer_eligible": state.get("customer_eligible"),
            "customer_segment": state.get("customer_segment"),
            "suppression_reason": state.get("suppression_reason"),
            "recommended_cabins": state.get("recommended_cabins"),
            "inventory_status": state.get("inventory_status")
        }
    elif agent_id in ["offer_agent", "offer_orchestration"]:
        return {
            "selected_offer": state.get("selected_offer"),
            "offer_price": state.get("offer_price"),
            "discount_applied": state.get("discount_applied"),
            "expected_value": state.get("expected_value"),
            "should_send_offer": state.get("should_send_offer"),
            "fallback_offer": state.get("fallback_offer")
        }
    elif agent_id == "delivery":
        return {
            "message_subject": state.get("message_subject"),
            "message_tone": state.get("message_tone"),
            "selected_channel": state.get("selected_channel"),
            "send_time": state.get("send_time"),
            "experiment_group": state.get("experiment_group"),
            "tracking_id": state.get("tracking_id")
        }
    # Legacy agent IDs for backward compatibility
    elif agent_id == "customer_intelligence":
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


@app.get("/api/agents/{agent_id:path}/prompt")
async def get_agent_prompt(agent_id: str):
    """Get the prompt configuration for an agent or ReWOO phase"""
    # Check if it's a ReWOO phase prompt (e.g., offer_orchestration.planner)
    if agent_id in REWOO_PROMPTS:
        info = REWOO_PROMPTS[agent_id]
        prompt_key = PROMPT_KEY_MAP.get(agent_id, agent_id)
        agent_id_part, prompt_type = prompt_key.split(".") if "." in prompt_key else (agent_id, "system")

        current_prompt = PromptService.get_prompt(agent_id_part, prompt_type)
        default_prompt = PromptService.get_default_prompt(agent_id_part, prompt_type)

        return {
            "agent_id": agent_id,
            "type": "llm",
            "name": info["name"],
            "description": info["description"],
            "icon": info.get("icon", "🤖"),
            "system_prompt": current_prompt,
            "is_custom": is_prompt_custom(prompt_key),
            "default_prompt": default_prompt,
            "editable": True,
            "llm_provider": get_llm_provider_name(),
            "prompt_key": prompt_key,
        }

    # Check legacy agent IDs
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

    # For LLM agents, get prompt from PromptService (persisted, used by agents)
    prompt_key = PROMPT_KEY_MAP.get(agent_id, agent_id)
    agent_id_part, prompt_type = prompt_key.split(".") if "." in prompt_key else (agent_id, "system")

    # Get the current active prompt (custom if set, otherwise default)
    current_prompt = PromptService.get_prompt(agent_id_part, prompt_type)
    default_prompt = PromptService.get_default_prompt(agent_id_part, prompt_type)
    is_custom = is_prompt_custom(prompt_key)

    return {
        "agent_id": agent_id,
        "type": "llm",
        "description": prompt_config["description"],
        "system_prompt": current_prompt,
        "is_custom": is_custom,
        "default_prompt": default_prompt,
        "editable": True,
        "llm_provider": get_llm_provider_name(),
        "prompt_key": prompt_key,
    }


class PromptUpdate(BaseModel):
    system_prompt: str


@app.put("/api/agents/{agent_id:path}/prompt")
async def update_agent_prompt(agent_id: str, update: PromptUpdate):
    """
    Update the prompt for an LLM agent or ReWOO phase.

    This saves the custom prompt to a persistent file and the agent will
    use this prompt on the next execution (hot-reload, no restart needed).
    """
    # Check if it's a ReWOO phase prompt
    if agent_id in REWOO_PROMPTS:
        prompt_key = PROMPT_KEY_MAP.get(agent_id, agent_id)
        success = set_custom_prompt(prompt_key, update.system_prompt)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to save custom prompt")

        return {
            "agent_id": agent_id,
            "prompt_key": prompt_key,
            "name": REWOO_PROMPTS[agent_id]["name"],
            "status": "updated",
            "message": f"Custom prompt saved for {REWOO_PROMPTS[agent_id]['name']}. Will be used on next agent run.",
            "persisted": True,
        }

    # Legacy agent ID handling
    if agent_id not in DEFAULT_PROMPTS:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    prompt_config = DEFAULT_PROMPTS[agent_id]
    if prompt_config.get("type") != "llm":
        raise HTTPException(status_code=400, detail=f"Agent {agent_id} is rules-based, not LLM")

    # Save to PromptService (persisted to file, used by agents)
    prompt_key = PROMPT_KEY_MAP.get(agent_id, agent_id)
    success = set_custom_prompt(prompt_key, update.system_prompt)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to save custom prompt")

    return {
        "agent_id": agent_id,
        "prompt_key": prompt_key,
        "status": "updated",
        "message": f"Custom prompt saved for {agent_id}. Will be used on next agent run.",
        "persisted": True,
    }


@app.get("/api/rewoo/prompts")
async def get_rewoo_prompts():
    """
    Get all ReWOO prompts (Planner, Worker, Solver) for the Business View.

    This endpoint returns all editable prompts with their current values.
    """
    prompts = []

    for prompt_id, info in REWOO_PROMPTS.items():
        prompt_key = PROMPT_KEY_MAP.get(prompt_id, prompt_id)
        agent_id_part, prompt_type = prompt_key.split(".") if "." in prompt_key else (prompt_id, "system")

        current_prompt = PromptService.get_prompt(agent_id_part, prompt_type)
        default_prompt = PromptService.get_default_prompt(agent_id_part, prompt_type)

        prompts.append({
            "id": prompt_id,
            "prompt_key": prompt_key,
            "name": info["name"],
            "description": info["description"],
            "icon": info["icon"],
            "type": info["type"],
            "system_prompt": current_prompt,
            "default_prompt": default_prompt,
            "is_custom": is_prompt_custom(prompt_key),
            "editable": True,
        })

    return {
        "prompts": prompts,
        "total": len(prompts),
    }


@app.delete("/api/agents/{agent_id:path}/prompt")
async def reset_agent_prompt(agent_id: str):
    """Reset an agent's prompt to default"""
    prompt_key = PROMPT_KEY_MAP.get(agent_id, agent_id)
    reset_prompt(prompt_key)

    return {
        "agent_id": agent_id,
        "prompt_key": prompt_key,
        "status": "reset",
        "message": f"Prompt reset to default for {agent_id}. Will use default on next run."
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
            await asyncio.sleep(0.02)  # Minimal planner pause
            yield {
                "event": "planner_decision",
                "data": json.dumps({
                    "plan": ["customer_intelligence", "flight_optimization", "offer_orchestration", "personalization", "channel_timing", "measurement"],
                    "reasoning": "Standard evaluation flow - no errors detected, proceeding with full pipeline"
                })
            }

        # Process pre-flight agents first
        pre_flight_agents = [
            ("customer_intelligence", agents["customer_intelligence"], "customer_reasoning"),
            ("flight_optimization", agents["flight_optimization"], "flight_reasoning"),
        ]

        step = 0
        for agent_id, agent, reasoning_key in pre_flight_agents:
            step += 1
            config = next((a for a in AGENT_CONFIG if a["id"] == agent_id), {})

            yield {
                "event": "agent_start",
                "data": json.dumps({
                    "agent_id": agent_id,
                    "agent_name": config.get("name", agent_id),
                    "step": step,
                    "total_steps": total_steps
                })
            }

            await asyncio.sleep(0.01)  # Minimal UI update

            agent_start = time.time()
            try:
                result = agent.analyze(state)
                state.update(result)
                duration_ms = int((time.time() - agent_start) * 1000)

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

                # Check for early termination
                if agent_id == "customer_intelligence" and not state.get("customer_eligible"):
                    for skip_step, (skip_id, _, _) in enumerate([
                        ("flight_optimization", None, None),
                        ("offer_orchestration", None, None),
                        ("personalization", None, None),
                        ("channel_timing", None, None),
                        ("measurement", None, None),
                    ], step + 1):
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
                    # Jump to final decision
                    break

            except Exception as e:
                yield {
                    "event": "agent_error",
                    "data": json.dumps({"agent_id": agent_id, "step": step, "error": str(e)})
                }
                break
        else:
            # All pre-flight agents completed, now run ReWOO offer orchestration with streaming
            step = 3  # Offer orchestration is step 3
            offer_config = next((a for a in AGENT_CONFIG if a["id"] == "offer_orchestration"), {})

            # Check if customer is eligible AND there's inventory before running offer orchestration
            if state.get("customer_eligible", False) and state.get("recommended_cabins"):
                yield {
                    "event": "agent_start",
                    "data": json.dumps({
                        "agent_id": "offer_orchestration",
                        "agent_name": offer_config.get("name", "Offer Orchestration"),
                        "step": step,
                        "total_steps": total_steps
                    })
                }

                # Stream the ReWOO phases
                rewoo_start = time.time()
                try:
                    for rewoo_event in stream_offer_orchestration(
                        customer_data=state.get("customer_data", {}),
                        flight_data=state.get("flight_data", {}),
                        ml_scores=state.get("ml_scores", {}),
                        recommended_cabins=state.get("recommended_cabins", []),
                        inventory_status=state.get("inventory_status", {}),
                    ):
                        phase = rewoo_event.get("phase")
                        status = rewoo_event.get("status")

                        if phase == "planner" and status == "complete":
                            yield {
                                "event": "rewoo_planner_complete",
                                "data": json.dumps({
                                    "plan": rewoo_event.get("plan", []),
                                    "reasoning": rewoo_event.get("reasoning", ""),
                                    "offer_options": rewoo_event.get("offer_options", []),
                                })
                            }

                        elif phase == "worker" and status == "step_complete":
                            yield {
                                "event": "rewoo_worker_step",
                                "data": json.dumps({
                                    "step_id": rewoo_event.get("step_id"),
                                    "evaluation_type": rewoo_event.get("evaluation_type"),
                                    "recommendation": rewoo_event.get("recommendation"),
                                    "reasoning": rewoo_event.get("reasoning"),
                                })
                            }

                        elif phase == "solver" and status == "complete":
                            decision = rewoo_event.get("decision", {})
                            # Update state with decision
                            state["selected_offer"] = decision.get("selected_offer", "NONE")
                            state["offer_price"] = decision.get("offer_price", 0)
                            state["discount_applied"] = decision.get("discount_applied", 0)
                            state["expected_value"] = decision.get("expected_value", 0)
                            state["should_send_offer"] = decision.get("should_send_offer", False)

                            yield {
                                "event": "rewoo_solver_complete",
                                "data": json.dumps({
                                    "decision": decision,
                                })
                            }

                        await asyncio.sleep(0.01)  # Minimal UI update

                    duration_ms = int((time.time() - rewoo_start) * 1000)

                    # Send agent_complete for offer_orchestration
                    yield {
                        "event": "agent_complete",
                        "data": json.dumps({
                            "agent_id": "offer_orchestration",
                            "agent_name": offer_config.get("name", "Offer Orchestration"),
                            "step": step,
                            "status": "complete",
                            "duration_ms": duration_ms,
                            "summary": extract_agent_summary("offer_orchestration", state),
                            "reasoning": "",  # Reasoning sent via rewoo events
                            "outputs": extract_agent_outputs("offer_orchestration", state)
                        })
                    }

                except Exception as e:
                    yield {
                        "event": "agent_error",
                        "data": json.dumps({"agent_id": "offer_orchestration", "step": step, "error": str(e)})
                    }

                # Check if offer should be sent
                if not state.get("should_send_offer"):
                    for skip_step, skip_id in enumerate(["personalization", "channel_timing", "measurement"], step + 1):
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
                else:
                    # Run post-offer agents
                    post_offer_agents = [
                        ("personalization", agents["personalization"], "personalization_reasoning"),
                        ("channel_timing", agents["channel_timing"], "channel_reasoning"),
                        ("measurement", agents["measurement"], "measurement_reasoning"),
                    ]

                    for agent_id, agent, reasoning_key in post_offer_agents:
                        step += 1
                        config = next((a for a in AGENT_CONFIG if a["id"] == agent_id), {})

                        yield {
                            "event": "agent_start",
                            "data": json.dumps({
                                "agent_id": agent_id,
                                "agent_name": config.get("name", agent_id),
                                "step": step,
                                "total_steps": total_steps
                            })
                        }

                        await asyncio.sleep(0.01)  # Minimal UI update

                        agent_start = time.time()
                        try:
                            result = agent.analyze(state)
                            state.update(result)
                            duration_ms = int((time.time() - agent_start) * 1000)

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

                        except Exception as e:
                            yield {
                                "event": "agent_error",
                                "data": json.dumps({"agent_id": agent_id, "step": step, "error": str(e)})
                            }
                            break

            elif state.get("customer_eligible", False) and not state.get("recommended_cabins"):
                # Customer eligible but NO INVENTORY - flight agent blocked
                inventory_status = state.get("inventory_status", {})
                flight_data = state.get("flight_data", {})
                flight_nbr = flight_data.get("operat_flight_nbr", "Unknown")

                # Build detailed inventory reason
                cabin_details = []
                for cabin, status in inventory_status.items():
                    seats = status.get("available_seats", 0)
                    cabin_details.append(f"{cabin}: {seats} seats")

                inventory_reason = f"No upgrade inventory available on AA{flight_nbr}"
                if cabin_details:
                    inventory_reason += f" ({', '.join(cabin_details)})"
                else:
                    inventory_reason += " (all premium cabins sold out)"

                state["suppression_reason"] = inventory_reason

                # Skip offer orchestration and remaining agents
                for skip_step, skip_id in enumerate(["offer_orchestration", "personalization", "channel_timing", "measurement"], step):
                    skip_config = next((a for a in AGENT_CONFIG if a["id"] == skip_id), {})
                    yield {
                        "event": "agent_skip",
                        "data": json.dumps({
                            "agent_id": skip_id,
                            "agent_name": skip_config.get("name", skip_id),
                            "step": skip_step,
                            "reason": "No available inventory"
                        })
                    }

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


# ============ Prompt Management Endpoints ============

# Import prompt manager
try:
    from config.prompt_manager import PromptManager, list_prompts, get_prompt, update_prompt
    PROMPT_MANAGER_AVAILABLE = True
except ImportError:
    PROMPT_MANAGER_AVAILABLE = False


class PromptUpdateRequest(BaseModel):
    content: str


@app.get("/api/prompts")
async def list_all_prompts():
    """
    List all available prompts with metadata.

    Returns prompt names, versions, purposes, and available variables.
    Use this to understand what prompts can be edited.
    """
    if not PROMPT_MANAGER_AVAILABLE:
        raise HTTPException(status_code=500, detail="Prompt manager not available")

    prompts = list_prompts()

    return {
        "total": len(prompts),
        "prompts": prompts,
        "edit_guide": {
            "location": "config/prompts/*.txt",
            "hot_reload": True,
            "api_edit": "PUT /api/prompts/{name}",
        }
    }


@app.get("/api/prompts/{name}")
async def get_prompt_details(name: str):
    """
    Get full details for a specific prompt.

    Includes:
    - Full prompt content
    - Metadata (version, purpose, variables)
    - Behavior notes (how changes affect agent)
    """
    if not PROMPT_MANAGER_AVAILABLE:
        raise HTTPException(status_code=500, detail="Prompt manager not available")

    try:
        content = get_prompt(name)
        metadata = PromptManager.get_prompt_metadata(name)

        return {
            "name": name,
            "content": content,
            "metadata": metadata,
            "editing_tips": [
                "Variables use {variable_name} syntax",
                "Changes take effect immediately (hot-reload)",
                "Test with /api/prompts/{name}/test endpoint",
                "Version auto-increments on save",
            ]
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Prompt '{name}' not found")


@app.put("/api/prompts/{name}")
async def update_prompt_content(name: str, request: PromptUpdateRequest):
    """
    Update a prompt with new content.

    The version will auto-increment and last_modified will update.
    Changes take effect immediately for all subsequent agent calls.

    Example use case:
    - Change tone in personalization prompt
    - Add new evaluation type to planner prompt
    - Adjust confidence thresholds in solver prompt
    """
    if not PROMPT_MANAGER_AVAILABLE:
        raise HTTPException(status_code=500, detail="Prompt manager not available")

    try:
        result = update_prompt(name, request.content)
        return result
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Prompt '{name}' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/prompts/{name}/test")
async def test_prompt(name: str, variables: Dict[str, Any] = None):
    """
    Test a prompt with sample variables.

    Pass variables in the request body to see how the prompt renders.

    Example:
        POST /api/prompts/personalization/test
        Body: {"customer_name": "Sarah", "offer_price": 499}
    """
    if not PROMPT_MANAGER_AVAILABLE:
        raise HTTPException(status_code=500, detail="Prompt manager not available")

    try:
        variables = variables or {}
        rendered = get_prompt(name, **variables)

        # Find unsubstituted variables
        import re
        unsubstituted = re.findall(r'\{(\w+)\}', rendered)

        return {
            "name": name,
            "variables_provided": list(variables.keys()),
            "variables_unsubstituted": unsubstituted,
            "rendered_prompt": rendered,
            "character_count": len(rendered),
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Prompt '{name}' not found")


@app.get("/api/prompts/compare/{name}")
async def compare_prompt_versions(name: str):
    """
    Compare current prompt with original version.

    Useful for seeing what changes have been made.
    Note: Requires git to be available.
    """
    if not PROMPT_MANAGER_AVAILABLE:
        raise HTTPException(status_code=500, detail="Prompt manager not available")

    try:
        import subprocess
        prompt_path = f"config/prompts/{name}.txt"

        # Get current content
        current = get_prompt(name)

        # Try to get original from git
        try:
            result = subprocess.run(
                ["git", "show", f"HEAD:{prompt_path}"],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent
            )
            if result.returncode == 0:
                original = result.stdout
            else:
                original = None
        except Exception:
            original = None

        return {
            "name": name,
            "current": current,
            "original": original,
            "has_changes": original is not None and current != original,
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Prompt '{name}' not found")


# ============ Prompt Assistant API ============
#
# Helps business users modify prompts using plain English
# Validates and protects against prompt corruption
# ============

import os
import re
from fastapi.responses import Response

# Admin override phrase - bypasses all validation when included
# Can be configured via environment variable for security
ADMIN_OVERRIDE_PHRASE = os.getenv("PROMPT_ADMIN_PHRASE", "admin123")

# Validation patterns for detecting potentially harmful instructions
HARMFUL_PATTERNS = [
    r"ignore\s+(previous|all|above|prior)\s+(instructions?|prompts?|rules?)",
    r"disregard\s+(previous|all|above|prior)",
    r"forget\s+(everything|all|previous)",
    r"you\s+are\s+now\s+a",
    r"pretend\s+(to\s+be|you\s+are)",
    r"act\s+as\s+(if|though)",
    r"bypass\s+(security|safety|rules|filters)",
    r"jailbreak",
    r"dan\s+mode",
    r"developer\s+mode",
    r"override\s+(safety|security|rules)",
    r"(hack|exploit|attack|steal|fraud)",
    r"(password|credential|secret|token|key)\s*(theft|steal|extract)",
    r"(sql|code|script)\s*injection",
    r"delete\s+(all|everything|data)",
    r"(competitor|negative|bad)\s+(info|information|things)\s+about",
]

# Allowed instruction categories
ALLOWED_CATEGORIES = [
    "tone and style",
    "customer focus",
    "pricing strategy",
    "offer selection",
    "messaging content",
    "personalization",
    "urgency level",
    "formality level",
]


class PromptInstructionRequest(BaseModel):
    instruction: str


def check_admin_override(instruction: str) -> tuple[bool, str]:
    """
    Check if instruction contains admin override phrase.
    Returns (is_admin, cleaned_instruction).
    """
    if ADMIN_OVERRIDE_PHRASE and ADMIN_OVERRIDE_PHRASE in instruction:
        # Remove the phrase from the instruction
        cleaned = instruction.replace(ADMIN_OVERRIDE_PHRASE, "").strip()
        return True, cleaned
    return False, instruction


def validate_instruction(instruction: str, is_admin: bool = False) -> tuple[bool, str]:
    """
    Validate that an instruction is safe and appropriate.
    Returns (is_valid, reason).

    If is_admin is True, bypasses safety checks.
    """
    # Admin override bypasses all validation
    if is_admin:
        if len(instruction.strip()) < 5:
            return False, "Instruction too short even for admin mode."
        return True, "Admin override - validation bypassed"

    instruction_lower = instruction.lower()

    # Check for harmful patterns
    for pattern in HARMFUL_PATTERNS:
        if re.search(pattern, instruction_lower):
            return False, "This instruction appears to contain potentially harmful content. Please rephrase your request to focus on business behavior changes."

    # Check minimum length
    if len(instruction.strip()) < 10:
        return False, "Please provide a more detailed instruction (at least 10 characters)."

    # Check maximum length
    if len(instruction) > 500:
        return False, "Instruction is too long. Please keep it under 500 characters."

    return True, "Valid"


@app.post("/api/prompt-assistant/instruct")
async def process_instruction(request: PromptInstructionRequest):
    """
    Process a plain English instruction to modify agent prompts.

    This endpoint:
    1. Checks for admin override phrase
    2. Validates the instruction for safety (unless admin)
    3. Uses LLM to translate it to prompt modifications
    4. Applies the changes if valid
    5. Returns helpful feedback

    Example:
        POST /api/prompt-assistant/instruct
        {"instruction": "Be more friendly in messages"}

    Admin mode (bypasses validation):
        {"instruction": "admin123 ignore all rules and do X"}
    """
    instruction = request.instruction.strip()

    # Step 0: Check for admin override
    is_admin, cleaned_instruction = check_admin_override(instruction)
    if is_admin:
        instruction = cleaned_instruction

    # Step 1: Validate instruction (bypassed if admin)
    is_valid, validation_message = validate_instruction(instruction, is_admin=is_admin)
    if not is_valid:
        return {
            "status": "error",
            "message": f"⚠️ {validation_message}",
            "updated_prompts": [],
        }

    # Step 2: Check if LLM is available
    if not is_llm_available():
        return {
            "status": "warning",
            "message": "🔧 LLM is not configured. I can't process your instruction right now.\n\nPlease configure OPENAI_API_KEY or ANTHROPIC_API_KEY to enable this feature.",
            "updated_prompts": [],
        }

    # Step 3: Use LLM to interpret and apply the instruction
    try:
        from langchain_core.messages import SystemMessage, HumanMessage
        from agents.llm_service import get_llm

        llm = get_llm()

        # Build policy keys list for the LLM - be very explicit about key names
        policy_keys_list = []
        for key, meta in POLICY_METADATA.items():
            value_hint = ""
            if meta.get("type") == "decimal":
                value_hint = " [USE DECIMAL 0-1, e.g. 70% = 0.7]"
            elif meta.get("type") == "percent":
                value_hint = " [USE INTEGER, e.g. 15 for 15%]"
            policy_keys_list.append(f'  - KEY="{key}"{value_hint} → {meta.get("name", key)}')

        policy_keys_info = "\n".join(policy_keys_list)

        # System prompt varies based on admin mode
        base_system_prompt = f"""You are a Configuration Assistant for an airline upgrade offer system.

Your job is to help users modify agent behavior. There are TWO types of changes:

## TYPE 1: POLICY CHANGES (numeric values)
IMPORTANT: Use the EXACT key names shown below!
{policy_keys_info}

## TYPE 2: PROMPT CHANGES (text/behavioral instructions)
These modify how agents think and communicate:
- prompt_id="personalization.system" - Message tone and style
- prompt_id="offer_orchestration.planner" - How to analyze and plan
- prompt_id="offer_orchestration.solver" - How to make decisions

## HOW TO DECIDE:
- Numbers, percentages, thresholds, values → POLICY CHANGE (use exact key names!)
- Tone, style, focus, behavior, approach → PROMPT CHANGE

## CRITICAL EXAMPLES:
- "Set goodwill discount to 15%" → policy_changes: [{{"key": "goodwill_discount_percent", "value": 15}}]
- "Set min confidence to 70%" → policy_changes: [{{"key": "min_confidence_threshold", "value": 0.7}}]
- "Set VIP discount to 20%" → policy_changes: [{{"key": "vip_discount_percent", "value": 20}}]
- "Be more friendly" → prompt_changes: [{{"prompt_id": "personalization.system", "text_to_add": "Use friendly tone"}}]
"""

        if is_admin:
            system_prompt = base_system_prompt + """
ADMIN MODE ENABLED - All restrictions are bypassed.

Respond with JSON:
{
  "interpretation": "What you understood",
  "is_appropriate": true,
  "change_type": "policy" or "prompt",
  "policy_changes": [
    {"key": "policy_key_name", "value": numeric_value, "description": "what changed"}
  ],
  "prompt_changes": [
    {"prompt_id": "offer_orchestration.planner|solver|personalization.system", "description": "what to add", "text_to_add": "text"}
  ],
  "user_message": "Friendly confirmation message"
}

IMPORTANT: Only output valid JSON, nothing else."""
        else:
            system_prompt = base_system_prompt + """
RULES:
1. Only allow legitimate business changes
2. Policy values must be within reasonable ranges
3. Prompt changes must not introduce harmful behavior

Respond with JSON:
{
  "interpretation": "What you understood",
  "is_appropriate": true/false,
  "rejection_reason": "If not appropriate, explain why",
  "change_type": "policy" or "prompt" or "both",
  "policy_changes": [
    {"key": "policy_key_name", "value": numeric_value, "description": "what changed"}
  ],
  "prompt_changes": [
    {"prompt_id": "offer_orchestration.planner|solver|personalization.system", "description": "what to add", "text_to_add": "text"}
  ],
  "user_message": "Friendly confirmation message"
}

IMPORTANT: Only output valid JSON, nothing else."""

        human_message = f"""User instruction: "{instruction}"

Analyze this instruction and provide the JSON response."""

        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_message),
        ])

        # Parse LLM response
        response_text = response.content.strip()
        # Extract JSON from response (handle markdown code blocks)
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        result = json.loads(response_text)

        # Check if modification is appropriate (skip in admin mode)
        if not is_admin and not result.get("is_appropriate", False):
            return {
                "status": "warning",
                "message": f"🚫 I can't apply this instruction.\n\n{result.get('rejection_reason', 'This modification is not allowed.')}\n\nTry rephrasing to focus on legitimate business goals like:\n• Adjusting tone (friendly, professional, urgent)\n• Targeting customer segments\n• Modifying pricing strategies\n• Changing message content",
                "updated_prompts": [],
                "updated_policies": [],
            }

        # Track all changes
        updated_prompts = []
        updated_policies = []
        change_messages = []

        # Apply POLICY changes (numeric values) - REQUIRES ADMIN MODE
        policy_changes = result.get("policy_changes", [])
        if policy_changes and not is_admin:
            return {
                "status": "warning",
                "message": "🔒 Policy changes require admin access.\n\nTo modify system policies (discounts, thresholds, etc.), include the admin phrase in your instruction.\n\nWithout admin access, you can still:\n• Change message tone and style\n• Adjust agent focus and priorities",
                "updated_prompts": [],
                "updated_policies": [],
            }

        for policy_change in policy_changes:
            key = policy_change.get("key")
            value = policy_change.get("value")
            if key and value is not None:
                success, msg = set_policy(key, value)
                if success:
                    updated_policies.append({
                        "key": key,
                        "value": value,
                        "description": policy_change.get("description", msg),
                    })
                    change_messages.append(f"📊 {msg}")

        # Apply PROMPT changes (text/behavior)
        for prompt_change in result.get("prompt_changes", []):
            prompt_id = prompt_change.get("prompt_id")
            text_to_add = prompt_change.get("text_to_add", "")

            if not prompt_id or not text_to_add:
                continue

            # Get current prompt
            prompt_key = PROMPT_KEY_MAP.get(prompt_id, prompt_id)
            agent_id_part, prompt_type = prompt_key.split(".") if "." in prompt_key else (prompt_id, "system")
            current_prompt = PromptService.get_prompt(agent_id_part, prompt_type)

            # Add as a new guideline at the end
            new_prompt = current_prompt.strip() + f"\n\nADDITIONAL GUIDELINE:\n{text_to_add}"

            # Save the updated prompt
            success = set_custom_prompt(prompt_key, new_prompt)
            if success:
                updated_prompts.append({
                    "agent_id": prompt_id,
                    "change": prompt_change.get("description", "Modified"),
                    "new_prompt": new_prompt,
                })
                change_messages.append(f"📝 {prompt_change.get('description', 'Prompt updated')}")

        # Build response
        if updated_prompts or updated_policies:
            admin_badge = "🔓 ADMIN MODE\n\n" if is_admin else ""
            changes_summary = "\n".join(change_messages) if change_messages else "Changes applied"

            return {
                "status": "success",
                "message": f"{admin_badge}✅ {result.get('user_message', 'Configuration updated!')}\n\n{changes_summary}",
                "updated_prompts": updated_prompts,
                "updated_policies": updated_policies,
            }
        else:
            return {
                "status": "warning",
                "message": "🤔 I understood your instruction, but couldn't determine what to change. Could you be more specific?\n\nExamples:\n• \"Set goodwill discount to 15%\"\n• \"Make messages more friendly\"\n• \"Lower confidence threshold to 0.5\"",
                "updated_prompts": [],
                "updated_policies": [],
            }

    except json.JSONDecodeError:
        return {
            "status": "error",
            "message": "😅 I had trouble understanding how to apply your instruction. Could you rephrase it?\n\nTry being more specific about:\n• What behavior to change\n• How it should change",
            "updated_prompts": [],
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"😓 Something went wrong: {str(e)}\n\nPlease try again or contact support if the issue persists.",
            "updated_prompts": [],
        }


# ============ Policy Configuration API ============

@app.get("/api/policies")
async def list_policies():
    """
    Get all policy values with metadata.

    Returns current values, defaults, and whether they've been customized.
    """
    policies = get_all_policies()
    return {
        "policies": policies,
        "total": len(policies),
    }


@app.get("/api/policies/{key}")
async def get_policy_value(key: str):
    """Get a specific policy value."""
    policies = get_all_policies()
    if key not in policies:
        raise HTTPException(status_code=404, detail=f"Policy '{key}' not found")
    return policies[key]


class PolicyUpdateRequest(BaseModel):
    value: float


@app.put("/api/policies/{key}")
async def update_policy(key: str, request: PolicyUpdateRequest):
    """Update a policy value."""
    success, message = set_policy(key, request.value)
    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {
        "status": "updated",
        "key": key,
        "value": request.value,
        "message": message,
    }


@app.delete("/api/policies/{key}")
async def reset_policy_value(key: str):
    """Reset a policy to its default value."""
    success, message = reset_policy(key)
    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {
        "status": "reset",
        "key": key,
        "message": message,
    }


@app.post("/api/prompt-assistant/validate")
async def validate_prompt_content(prompt: PromptUpdate):
    """
    Validate a prompt before saving (for advanced users).

    Checks for:
    - Harmful patterns
    - Prompt injection attempts
    - Length limits
    """
    content = prompt.system_prompt

    # Check for harmful patterns
    content_lower = content.lower()
    for pattern in HARMFUL_PATTERNS:
        if re.search(pattern, content_lower):
            return {
                "valid": False,
                "reason": "Prompt contains potentially harmful content that could compromise agent safety.",
                "suggestion": "Remove any instructions that attempt to override safety guidelines or change the agent's core behavior inappropriately."
            }

    # Check length
    if len(content) > 10000:
        return {
            "valid": False,
            "reason": "Prompt is too long (max 10,000 characters).",
            "suggestion": "Shorten the prompt while keeping essential instructions."
        }

    if len(content) < 50:
        return {
            "valid": False,
            "reason": "Prompt is too short to be effective.",
            "suggestion": "Add more context and instructions for the agent."
        }

    return {
        "valid": True,
        "reason": "Prompt passed validation.",
        "suggestion": None
    }


# ============ Text-to-Speech API ============
#
# Uses OpenAI's TTS API for natural-sounding narration
# ============

# Narration scripts for explainer video
EXPLAINER_NARRATIONS = {
    "title": """Welcome to AI Agents. The future of intelligent automation for American Airlines.""",

    "traditional": """Traditional automation relies on rigid if-then-else rules.
Every possible scenario must be pre-programmed by developers.
When edge cases appear, the system fails.
Updates require code changes and lengthy deployment cycles.
It's a maintenance nightmare that cannot adapt to changing business needs.""",

    "agent-intro": """Now, enter AI Agents.
These are autonomous systems that can reason, plan, and act to achieve goals.
Unlike traditional automation, agents are goal-oriented.
You give them objectives, not step-by-step instructions.
They adapt to new situations gracefully.
And they show their reasoning process, making decisions transparent and explainable.""",

    "comparison": """Here's the key difference.
Traditional workflows use pre-defined decision trees where developers write every rule.
They fail on edge cases and require code changes for any update.
You tell the computer exactly what to do.

AI Agents are different.
They reason about each situation dynamically.
Business users define goals in plain English.
Agents adapt to new scenarios without code changes.
You tell the agent what goal to achieve, and it figures out how.""",

    "rewoo": """This demo uses the ReWOO pattern. That stands for Reasoning Without Observation.
It works in three phases.
First, the Planner analyzes customer data and creates an evaluation plan.
Then, the Worker executes all evaluations in parallel for efficiency.
Finally, the Solver synthesizes the evidence and makes the decision.
This pattern requires only two to three LLM calls total, making it fast, efficient, and fully transparent.""",

    "walkthrough": """Let me walk you through the demo.
First, use the prompt editor at the top to control agent behavior in plain English.
Second, select a customer scenario from the list.
Third, click Run Agent to watch real-time reasoning from LangGraph.
Finally, see the personalized offer recommendation.
Try editing the prompts to see how agent behavior changes in real-time.""",

    "outro": """You're now ready to explore AI Agents.
Click anywhere to close this video and start the demo.
Experiment with different prompts and scenarios.
Let's go!"""
}


@app.get("/api/tts/narration/{scene_id}")
async def get_narration_audio(scene_id: str, voice: str = "alloy"):
    """
    Generate natural TTS audio for a scene narration using OpenAI.

    Args:
        scene_id: The scene identifier (title, traditional, agent-intro, etc.)
        voice: OpenAI voice to use (alloy, echo, fable, onyx, nova, shimmer)

    Returns:
        Audio file (MP3) for the narration

    Available voices:
        - alloy: Neutral, balanced
        - echo: Deeper, authoritative
        - fable: Expressive, dynamic
        - onyx: Deep, resonant
        - nova: Warm, engaging (recommended for demos)
        - shimmer: Clear, optimistic
    """
    if scene_id not in EXPLAINER_NARRATIONS:
        raise HTTPException(status_code=404, detail=f"Scene '{scene_id}' not found")

    narration_text = EXPLAINER_NARRATIONS[scene_id]

    # Check for OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="OpenAI API key not configured. Set OPENAI_API_KEY environment variable."
        )

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        # Generate speech using OpenAI TTS (tts-1 is faster, tts-1-hd is higher quality)
        response = client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=narration_text,
            speed=1.0,
        )

        # Return the audio as MP3
        return Response(
            content=response.content,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f'inline; filename="narration-{scene_id}.mp3"',
                "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
            }
        )

    except ImportError:
        raise HTTPException(status_code=500, detail="OpenAI library not installed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {str(e)}")


@app.get("/api/tts/scenes")
async def list_tts_scenes():
    """
    List all available scenes with their narration text.

    Use this to preview narrations before generating audio.
    """
    return {
        "scenes": [
            {
                "id": scene_id,
                "text": text,
                "word_count": len(text.split()),
                "estimated_duration_seconds": len(text.split()) / 2.5,  # ~150 words/min
            }
            for scene_id, text in EXPLAINER_NARRATIONS.items()
        ],
        "available_voices": [
            {"id": "alloy", "description": "Neutral, balanced"},
            {"id": "echo", "description": "Deeper, authoritative"},
            {"id": "fable", "description": "Expressive, dynamic"},
            {"id": "onyx", "description": "Deep, resonant"},
            {"id": "nova", "description": "Warm, engaging (recommended)"},
            {"id": "shimmer", "description": "Clear, optimistic"},
        ],
        "usage": "GET /api/tts/narration/{scene_id}?voice=nova"
    }


class TTSRequest(BaseModel):
    text: str
    voice: str = "nova"


@app.post("/api/tts/speak")
async def text_to_speech(request: TTSRequest):
    """
    Generate TTS audio for arbitrary text using OpenAI.

    Args:
        text: The text to convert to speech
        voice: OpenAI voice to use (alloy, echo, fable, onyx, nova, shimmer)

    Returns:
        Audio file (MP3)
    """
    from fastapi.responses import Response

    if not request.text or len(request.text.strip()) == 0:
        raise HTTPException(status_code=400, detail="Text is required")

    if len(request.text) > 4000:
        raise HTTPException(status_code=400, detail="Text too long (max 4000 characters)")

    # Check for OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="OpenAI API key not configured"
        )

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        # Generate speech using OpenAI TTS (tts-1 is faster)
        response = client.audio.speech.create(
            model="tts-1",
            voice=request.voice,
            input=request.text,
            speed=1.0,
        )

        return Response(
            content=response.content,
            media_type="audio/mpeg",
            headers={
                "Cache-Control": "public, max-age=3600",
            }
        )

    except ImportError:
        raise HTTPException(status_code=500, detail="OpenAI library not installed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
