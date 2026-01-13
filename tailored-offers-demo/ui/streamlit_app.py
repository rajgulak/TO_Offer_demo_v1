"""
Tailored Offers Agentic Demo - Streamlit UI

This application demonstrates the 6-agent architecture for
American Airlines Tailored Offers.
"""
import streamlit as st
import sys
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.data_tools import (
    get_all_customers,
    get_all_flights,
    get_all_reservations,
    get_enriched_pnr
)
from agents.state import create_initial_state
from agents.customer_intelligence import CustomerIntelligenceAgent
from agents.flight_optimization import FlightOptimizationAgent
from agents.offer_orchestration import OfferOrchestrationAgent
from agents.personalization import PersonalizationAgent
from agents.channel_timing import ChannelTimingAgent
from agents.measurement_learning import MeasurementLearningAgent


# Page config
st.set_page_config(
    page_title="Tailored Offers - Agentic AI Demo",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .agent-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
        border-left: 4px solid #1f77b4;
    }
    .agent-name {
        font-weight: bold;
        color: #1f77b4;
        font-size: 1.1em;
    }
    .reasoning-box {
        background-color: #262730;
        color: #fafafa;
        padding: 15px;
        border-radius: 5px;
        font-family: monospace;
        font-size: 0.85em;
        white-space: pre-wrap;
    }
    .decision-box {
        background-color: #d4edda;
        border: 1px solid #28a745;
        border-radius: 10px;
        padding: 20px;
        margin: 15px 0;
    }
    .no-offer-box {
        background-color: #f8d7da;
        border: 1px solid #dc3545;
        border-radius: 10px;
        padding: 20px;
        margin: 15px 0;
    }
    .metric-card {
        background-color: #e7f1ff;
        border-radius: 8px;
        padding: 10px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)


def display_agent_output(agent_name: str, reasoning: str, icon: str = "🤖"):
    """Display agent output in a styled card"""
    st.markdown(f"""
    <div class="agent-card">
        <div class="agent-name">{icon} {agent_name}</div>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("View Reasoning", expanded=True):
        st.markdown(f'<div class="reasoning-box">{reasoning}</div>', unsafe_allow_html=True)


def main():
    # Header
    st.title("✈️ Tailored Offers - Agentic AI Demo")
    st.markdown("""
    **Demonstrating how 6 AI Agents work together to optimize upgrade offers**

    This demo showcases an agentic architecture where specialized agents collaborate
    to make intelligent offer decisions - going beyond what ML models alone can provide.
    """)

    # Sidebar - PNR Selection
    st.sidebar.header("📋 Select Scenario")

    reservations = get_all_reservations()
    customers = {c["customer_id"]: c for c in get_all_customers()}

    # Create selection options
    pnr_options = {}
    for res in reservations:
        cust = customers.get(res["customer_id"], {})
        label = (
            f"{res['pnr_locator']} - {cust.get('first_name', 'Unknown')} "
            f"({res['origin']}→{res['destination']}, T-{res['hours_to_departure']}hrs)"
        )
        pnr_options[label] = res["pnr_locator"]

    selected_label = st.sidebar.selectbox(
        "Choose a PNR to evaluate:",
        options=list(pnr_options.keys())
    )
    selected_pnr = pnr_options[selected_label]

    # Scenario descriptions
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📝 Available Scenarios")
    st.sidebar.markdown("""
    - **ABC123**: Gold member, leisure, 72hrs out
    - **XYZ789**: Platinum Pro, business, 48hrs (follow-up)
    - **LMN456**: Executive Platinum, international
    - **DEF321**: New customer (cold start)
    - **GHI654**: Suppressed customer (complaint)
    """)

    # Load data button
    if st.sidebar.button("🚀 Run Agent Evaluation", type="primary"):
        run_evaluation(selected_pnr)

    # Show current data
    st.sidebar.markdown("---")
    if st.sidebar.checkbox("Show Raw Data"):
        enriched = get_enriched_pnr(selected_pnr)
        if enriched:
            st.sidebar.json(enriched)


def run_evaluation(pnr_locator: str):
    """Run the full agent evaluation and display results"""

    st.markdown("---")
    st.header(f"🔄 Evaluating PNR: {pnr_locator}")

    # Load data
    enriched = get_enriched_pnr(pnr_locator)
    if not enriched:
        st.error(f"PNR {pnr_locator} not found!")
        return

    # Display customer and flight info
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("👤 Customer Profile")
        cust = enriched["customer"]
        st.markdown(f"""
        - **Name**: {cust['first_name']} {cust['last_name']}
        - **Loyalty**: {cust['loyalty_tier']} ({cust['tenure_days'] // 365} years)
        - **Travel Pattern**: {cust['travel_pattern'].title()}
        - **Annual Revenue**: ${cust['annual_revenue']:,}
        """)

        if cust.get("suppression", {}).get("is_suppressed"):
            st.warning(f"⚠️ Customer Suppressed: {cust['suppression'].get('complaint_reason', 'Unknown')}")

    with col2:
        st.subheader("✈️ Flight Details")
        flight = enriched["flight"]
        res = enriched["pnr"]
        st.markdown(f"""
        - **Flight**: {flight['flight_id']} ({flight['origin']} → {flight['destination']})
        - **Date**: {res['departure_date']} at {flight['departure_time']}
        - **Current Cabin**: {res['current_cabin'].replace('_', ' ').title()}
        - **Hours to Departure**: {res['hours_to_departure']}
        """)

    # Initialize state
    state = create_initial_state(pnr_locator)
    state["customer_data"] = enriched["customer"]
    state["flight_data"] = enriched["flight"]
    state["reservation_data"] = enriched["pnr"]
    state["ml_scores"] = enriched["ml_scores"]

    st.markdown("---")
    st.header("🤖 Agent Processing")

    # Progress bar
    progress = st.progress(0)
    status = st.empty()

    # Run agents sequentially with display
    agents_results = []

    # Agent 1: Customer Intelligence
    status.text("Running Customer Intelligence Agent...")
    progress.progress(15)

    customer_agent = CustomerIntelligenceAgent()
    result = customer_agent.analyze(state)
    state.update(result)
    agents_results.append(("Customer Intelligence Agent", result.get("customer_reasoning", ""), "🧠"))

    with st.container():
        display_agent_output(
            "Agent 1: Customer Intelligence",
            result.get("customer_reasoning", "No reasoning available"),
            "🧠"
        )

    # Check if should continue
    if not state.get("customer_eligible", False):
        progress.progress(100)
        status.text("Evaluation complete - Customer not eligible")
        display_no_offer(state)
        return

    # Agent 2: Flight Optimization
    status.text("Running Flight Optimization Agent...")
    progress.progress(30)

    flight_agent = FlightOptimizationAgent()
    result = flight_agent.analyze(state)
    state.update(result)

    with st.container():
        display_agent_output(
            "Agent 2: Flight Optimization",
            result.get("flight_reasoning", "No reasoning available"),
            "📊"
        )

    # Agent 3: Offer Orchestration
    status.text("Running Offer Orchestration Agent...")
    progress.progress(50)

    offer_agent = OfferOrchestrationAgent()
    result = offer_agent.analyze(state)
    state.update(result)

    with st.container():
        display_agent_output(
            "Agent 3: Offer Orchestration",
            result.get("offer_reasoning", "No reasoning available"),
            "⚖️"
        )

    # Check if should continue
    if not state.get("should_send_offer", False):
        progress.progress(100)
        status.text("Evaluation complete - No offer selected")
        display_no_offer(state)
        return

    # Agent 4: Personalization
    status.text("Running Personalization Agent...")
    progress.progress(65)

    personalization_agent = PersonalizationAgent()
    result = personalization_agent.analyze(state)
    state.update(result)

    with st.container():
        display_agent_output(
            "Agent 4: Personalization (GenAI)",
            result.get("personalization_reasoning", "No reasoning available"),
            "✨"
        )

    # Agent 5: Channel & Timing
    status.text("Running Channel & Timing Agent...")
    progress.progress(80)

    channel_agent = ChannelTimingAgent()
    result = channel_agent.analyze(state)
    state.update(result)

    with st.container():
        display_agent_output(
            "Agent 5: Channel & Timing",
            result.get("channel_reasoning", "No reasoning available"),
            "📱"
        )

    # Agent 6: Measurement & Learning
    status.text("Running Measurement & Learning Agent...")
    progress.progress(95)

    measurement_agent = MeasurementLearningAgent()
    result = measurement_agent.analyze(state)
    state.update(result)

    with st.container():
        display_agent_output(
            "Agent 6: Measurement & Learning",
            result.get("measurement_reasoning", "No reasoning available"),
            "📈"
        )

    progress.progress(100)
    status.text("Evaluation complete!")

    # Display final decision
    display_final_decision(state)


def display_no_offer(state: dict):
    """Display when no offer is made"""
    st.markdown("---")
    st.header("📋 Final Decision")

    reason = state.get("suppression_reason") or "Offer criteria not met"

    st.markdown(f"""
    <div class="no-offer-box">
        <h3>❌ No Offer Sent</h3>
        <p><strong>Reason:</strong> {reason}</p>
    </div>
    """, unsafe_allow_html=True)


def display_final_decision(state: dict):
    """Display the final offer decision"""
    st.markdown("---")
    st.header("📋 Final Decision")

    offer_names = {
        "IU_BUSINESS": "Business Class Upgrade",
        "IU_PREMIUM_ECONOMY": "Premium Economy Upgrade",
        "MCE": "Main Cabin Extra"
    }

    offer_type = state.get("selected_offer", "")
    offer_name = offer_names.get(offer_type, offer_type)
    price = state.get("offer_price", 0)
    channel = state.get("selected_channel", "")
    send_time = state.get("send_time", "")

    st.markdown(f"""
    <div class="decision-box">
        <h3>✅ Offer Approved</h3>
        <p><strong>Offer:</strong> {offer_name} @ ${price:.0f}</p>
        <p><strong>Channel:</strong> {channel.upper()}</p>
        <p><strong>Send Time:</strong> {send_time}</p>
        <p><strong>Experiment Group:</strong> {state.get('experiment_group', 'N/A')}</p>
        <p><strong>Tracking ID:</strong> <code>{state.get('tracking_id', 'N/A')}</code></p>
    </div>
    """, unsafe_allow_html=True)

    # Show the message
    st.subheader("📧 Generated Message")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("**Subject:**")
        st.info(state.get("message_subject", ""))

    with col2:
        st.markdown("**Body:**")
        st.text_area(
            "Message Preview",
            state.get("message_body", ""),
            height=300,
            disabled=True,
            label_visibility="collapsed"
        )

    # Fallback offer
    fallback = state.get("fallback_offer")
    if fallback:
        st.markdown(f"""
        **Fallback Offer:** {fallback.get('display_name')} @ ${fallback.get('price', 0):.0f}
        (if primary declined)
        """)

    # Show reasoning trace
    st.markdown("---")
    st.subheader("🔍 Complete Reasoning Trace")

    trace = state.get("reasoning_trace", [])
    if trace:
        trace_text = "\n".join([f"→ {t}" for t in trace])
        st.code(trace_text, language="text")


if __name__ == "__main__":
    main()
