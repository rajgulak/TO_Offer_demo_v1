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
from agents.offer_orchestration import OfferOrchestrationAgent, ORCHESTRATION_SYSTEM_PROMPT
from agents.personalization import PersonalizationAgent, PERSONALIZATION_SYSTEM_PROMPT
from agents.channel_timing import ChannelTimingAgent
from agents.measurement_learning import MeasurementLearningAgent
from agents.llm_service import get_llm_provider_name, is_llm_available


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
        "reasoning_key": "customer_reasoning"
    },
    {
        "id": "flight_optimization",
        "name": "Flight Optimization",
        "short_name": "Flight",
        "icon": "chart",
        "description": "Evaluates cabin inventory and flight priority",
        "reasoning_key": "flight_reasoning"
    },
    {
        "id": "offer_orchestration",
        "name": "Offer Orchestration",
        "short_name": "Offer",
        "icon": "scale",
        "description": "Selects optimal offer using expected value calculation",
        "reasoning_key": "offer_reasoning"
    },
    {
        "id": "personalization",
        "name": "Personalization",
        "short_name": "Message",
        "icon": "sparkles",
        "description": "Generates personalized messaging with GenAI",
        "reasoning_key": "personalization_reasoning"
    },
    {
        "id": "channel_timing",
        "name": "Channel & Timing",
        "short_name": "Channel",
        "icon": "phone",
        "description": "Optimizes delivery channel and send time",
        "reasoning_key": "channel_reasoning"
    },
    {
        "id": "measurement",
        "name": "Measurement & Learning",
        "short_name": "Measure",
        "icon": "trending",
        "description": "Assigns A/B test groups and tracking",
        "reasoning_key": "measurement_reasoning"
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


# ============ Helper Functions ============

def get_scenario_tag(pnr: str, customer: Dict, reservation: Dict) -> str:
    """Determine scenario tag for a PNR"""
    if customer.get("suppression", {}).get("is_suppressed"):
        return "Suppressed"
    if customer.get("tenure_days", 0) < 60:
        return "Cold Start"
    if reservation.get("offer_history", {}).get("offers_sent", 0) > 0:
        return "Follow-up"
    if reservation.get("is_international"):
        return "International"
    return "Standard"


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
    """List all available PNRs with summary info"""
    reservations = get_all_reservations()
    result = []

    for res in reservations:
        enriched = get_enriched_pnr(res["pnr_locator"])
        if enriched:
            customer = enriched["customer"]
            flight = enriched["flight"]

            result.append(PNRSummary(
                pnr=res["pnr_locator"],
                customer_name=f"{customer['first_name']} {customer['last_name']}",
                customer_tier=customer["loyalty_tier"],
                route=f"{flight['origin']} → {flight['destination']}",
                hours_to_departure=res["hours_to_departure"],
                scenario_tag=get_scenario_tag(res["pnr_locator"], customer, res)
            ))

    return result


@app.get("/api/pnrs/{pnr_locator}")
async def get_pnr(pnr_locator: str):
    """Get enriched PNR data"""
    enriched = get_enriched_pnr(pnr_locator)
    if not enriched:
        raise HTTPException(status_code=404, detail=f"PNR {pnr_locator} not found")

    customer = enriched["customer"]
    flight = enriched["flight"]
    reservation = enriched["pnr"]

    return {
        "pnr_locator": pnr_locator,
        "customer": {
            "customer_id": customer["customer_id"],
            "name": f"{customer['first_name']} {customer['last_name']}",
            "loyalty_tier": customer["loyalty_tier"],
            "tenure_days": customer["tenure_days"],
            "travel_pattern": customer["travel_pattern"],
            "annual_revenue": customer["annual_revenue"],
            "is_suppressed": customer.get("suppression", {}).get("is_suppressed", False),
            "complaint_reason": customer.get("suppression", {}).get("complaint_reason"),
            "marketing_consent": customer.get("marketing_consent", {}),
            "historical_upgrades": customer.get("historical_upgrades", {})
        },
        "flight": {
            "flight_id": flight["flight_id"],
            "route": f"{flight['origin_city']} ({flight['origin']}) → {flight['destination_city']} ({flight['destination']})",
            "departure_date": flight["departure_date"],
            "departure_time": flight["departure_time"],
            "aircraft_type": flight.get("aircraft_type", ""),
            "cabins": flight.get("cabins", {})
        },
        "reservation": {
            "hours_to_departure": reservation["hours_to_departure"],
            "current_cabin": reservation["current_cabin"],
            "fare_class": reservation.get("fare_class", ""),
            "checked_in": reservation.get("checked_in", False)
        },
        "ml_scores": enriched.get("ml_scores")
    }


@app.get("/api/pnrs/{pnr_locator}/evaluate")
async def evaluate_pnr_stream(pnr_locator: str):
    """
    Stream agent evaluation results using Server-Sent Events.

    Each agent's result is streamed as it completes, allowing
    real-time visualization in the frontend.
    """
    enriched = get_enriched_pnr(pnr_locator)
    if not enriched:
        async def error_generator():
            yield {
                "event": "error",
                "data": json.dumps({"error": f"PNR {pnr_locator} not found"})
            }
        return EventSourceResponse(error_generator())

    async def event_generator():
        # Initialize state
        state = create_initial_state(pnr_locator)
        state["customer_data"] = enriched["customer"]
        state["flight_data"] = enriched["flight"]
        state["reservation_data"] = enriched["pnr"]
        state["ml_scores"] = enriched.get("ml_scores")

        total_steps = 6
        start_time = time.time()

        # Send initial event
        yield {
            "event": "pipeline_start",
            "data": json.dumps({
                "pnr": pnr_locator,
                "total_steps": total_steps
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

            # Add artificial delay for demo effect (800-1500ms)
            await asyncio.sleep(random.uniform(0.8, 1.5))

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
