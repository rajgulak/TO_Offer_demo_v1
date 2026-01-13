#!/usr/bin/env python3
"""
Tailored Offers Agentic Demo - CLI Runner

Usage:
    python run_demo.py --ui          # Launch Streamlit UI
    python run_demo.py --pnr ABC123  # Run single PNR evaluation
    python run_demo.py --all         # Run all PNRs
"""
import argparse
import subprocess
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from tools.data_tools import get_all_reservations, get_enriched_pnr
from agents.workflow import run_offer_evaluation


def run_streamlit():
    """Launch the Streamlit UI"""
    ui_path = Path(__file__).parent / "ui" / "streamlit_app.py"
    subprocess.run(["streamlit", "run", str(ui_path)])


def run_single_pnr(pnr_locator: str):
    """Run evaluation for a single PNR"""
    print(f"\n{'='*60}")
    print(f"  TAILORED OFFERS - AGENTIC EVALUATION")
    print(f"  PNR: {pnr_locator}")
    print(f"{'='*60}\n")

    # Get enriched data first to show context
    enriched = get_enriched_pnr(pnr_locator)
    if not enriched:
        print(f"❌ PNR {pnr_locator} not found!")
        return

    cust = enriched["customer"]
    flight = enriched["flight"]
    res = enriched["pnr"]

    print(f"👤 Customer: {cust['first_name']} {cust['last_name']} ({cust['loyalty_tier']})")
    print(f"✈️  Flight: {flight['flight_id']} {flight['origin']}→{flight['destination']}")
    print(f"📅 Departure: {res['departure_date']} (T-{res['hours_to_departure']} hours)")
    print()

    # Run the workflow
    print("🤖 Running Agent Evaluation...\n")

    try:
        # Import and run agents manually to show progress
        from agents.state import create_initial_state
        from agents.customer_intelligence import CustomerIntelligenceAgent
        from agents.flight_optimization import FlightOptimizationAgent
        from agents.offer_orchestration import OfferOrchestrationAgent
        from agents.personalization import PersonalizationAgent
        from agents.channel_timing import ChannelTimingAgent
        from agents.measurement_learning import MeasurementLearningAgent

        state = create_initial_state(pnr_locator)
        state["customer_data"] = enriched["customer"]
        state["flight_data"] = enriched["flight"]
        state["reservation_data"] = enriched["pnr"]
        state["ml_scores"] = enriched["ml_scores"]

        # Agent 1
        print("🧠 Agent 1: Customer Intelligence...")
        agent1 = CustomerIntelligenceAgent()
        result = agent1.analyze(state)
        state.update(result)
        print(f"   → Eligible: {state.get('customer_eligible')}")
        print(f"   → Segment: {state.get('customer_segment')}")

        if not state.get("customer_eligible"):
            print(f"\n❌ RESULT: No offer - {state.get('suppression_reason')}")
            return

        # Agent 2
        print("\n📊 Agent 2: Flight Optimization...")
        agent2 = FlightOptimizationAgent()
        result = agent2.analyze(state)
        state.update(result)
        print(f"   → Flight Priority: {state.get('flight_priority')}")
        print(f"   → Recommended Cabins: {state.get('recommended_cabins')}")

        # Agent 3
        print("\n⚖️  Agent 3: Offer Orchestration...")
        agent3 = OfferOrchestrationAgent()
        result = agent3.analyze(state)
        state.update(result)
        print(f"   → Selected Offer: {state.get('selected_offer')}")
        print(f"   → Price: ${state.get('offer_price', 0):.0f}")
        print(f"   → Expected Value: ${state.get('expected_value', 0):.2f}")

        if not state.get("should_send_offer"):
            print(f"\n❌ RESULT: No offer - criteria not met")
            return

        # Agent 4
        print("\n✨ Agent 4: Personalization (GenAI)...")
        agent4 = PersonalizationAgent()
        result = agent4.analyze(state)
        state.update(result)
        print(f"   → Tone: {state.get('message_tone')}")
        print(f"   → Subject: {state.get('message_subject')[:50]}...")

        # Agent 5
        print("\n📱 Agent 5: Channel & Timing...")
        agent5 = ChannelTimingAgent()
        result = agent5.analyze(state)
        state.update(result)
        print(f"   → Channel: {state.get('selected_channel')}")
        print(f"   → Send Time: {state.get('send_time')}")

        # Agent 6
        print("\n📈 Agent 6: Measurement & Learning...")
        agent6 = MeasurementLearningAgent()
        result = agent6.analyze(state)
        state.update(result)
        print(f"   → Experiment Group: {state.get('experiment_group')}")
        print(f"   → Tracking ID: {state.get('tracking_id')}")

        # Final result
        print(f"\n{'='*60}")
        print("✅ FINAL DECISION: SEND OFFER")
        print(f"{'='*60}")
        print(f"   Offer: {state.get('selected_offer')} @ ${state.get('offer_price', 0):.0f}")
        print(f"   Channel: {state.get('selected_channel').upper()}")
        print(f"   Time: {state.get('send_time')}")
        print(f"   Tracking: {state.get('tracking_id')}")
        print()

        # Show message
        print("📧 MESSAGE PREVIEW:")
        print("-" * 40)
        print(f"Subject: {state.get('message_subject')}")
        print("-" * 40)
        print(state.get("message_body"))
        print("-" * 40)

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


def run_all_pnrs():
    """Run evaluation for all PNRs"""
    reservations = get_all_reservations()

    print(f"\n{'='*60}")
    print(f"  TAILORED OFFERS - BATCH EVALUATION")
    print(f"  Processing {len(reservations)} PNRs")
    print(f"{'='*60}\n")

    for res in reservations:
        run_single_pnr(res["pnr_locator"])
        print("\n" + "="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Tailored Offers Agentic Demo"
    )
    parser.add_argument(
        "--ui",
        action="store_true",
        help="Launch Streamlit UI"
    )
    parser.add_argument(
        "--pnr",
        type=str,
        help="Evaluate a specific PNR"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Evaluate all PNRs"
    )

    args = parser.parse_args()

    if args.ui:
        run_streamlit()
    elif args.pnr:
        run_single_pnr(args.pnr)
    elif args.all:
        run_all_pnrs()
    else:
        # Default: show help and run ABC123 as example
        print("Tailored Offers Agentic Demo")
        print("-" * 40)
        print("Usage:")
        print("  python run_demo.py --ui          # Launch Streamlit UI")
        print("  python run_demo.py --pnr ABC123  # Run single PNR")
        print("  python run_demo.py --all         # Run all PNRs")
        print()
        print("Running example evaluation for PNR ABC123...")
        run_single_pnr("ABC123")


if __name__ == "__main__":
    main()
