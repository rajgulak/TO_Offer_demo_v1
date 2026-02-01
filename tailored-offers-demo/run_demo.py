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
        from agents.prechecks import check_customer_eligibility, check_inventory_availability
        from agents.delivery import generate_message, select_channel, setup_tracking

        customer = enriched["customer"]
        flight_data = enriched["flight"]
        reservation = enriched["pnr"]
        ml_scores = enriched["ml_scores"]

        # Step 1
        print("🧠 Step 1: Customer Eligibility...")
        eligible, suppression_reason, segment, details = check_customer_eligibility(
            customer, reservation, ml_scores
        )
        print(f"   → Eligible: {eligible}")
        print(f"   → Segment: {segment}")

        if not eligible:
            print(f"\n❌ RESULT: No offer - {suppression_reason}")
            return

        # Step 2
        print("\n📊 Step 2: Inventory Availability...")
        has_inventory, recommended_cabins, inventory_status = check_inventory_availability(
            flight_data, reservation.get("current_cabin", "")
        )
        print(f"   → Has Inventory: {has_inventory}")
        print(f"   → Recommended Cabins: {recommended_cabins}")

        if not has_inventory:
            print(f"\n❌ RESULT: No offer - no inventory available")
            return

        # Step 3: Determine offer type and price from inventory
        offer_type = recommended_cabins[0] if recommended_cabins else "MCE"
        offer_price = 0  # Would be calculated by pricing logic

        # Step 4
        print("\n✨ Step 4: Personalization (GenAI)...")
        message_result = generate_message(customer, flight_data, offer_type, offer_price)
        print(f"   → Tone: {message_result.get('message_tone')}")
        print(f"   → Subject: {message_result.get('message_subject', '')[:50]}...")

        # Step 5
        print("\n📱 Step 5: Channel & Timing...")
        channel_result = select_channel(customer, reservation.get("hours_to_departure", 72))
        print(f"   → Channel: {channel_result.get('selected_channel')}")
        print(f"   → Send Time: {channel_result.get('send_time')}")

        # Step 6
        print("\n📈 Step 6: Measurement & Learning...")
        tracking_result = setup_tracking(reservation.get("pnr_locator", pnr_locator), offer_type)
        print(f"   → Experiment Group: {tracking_result.get('experiment_group')}")
        print(f"   → Tracking ID: {tracking_result.get('tracking_id')}")

        # Combine results into state for final display
        state = {}
        state.update(message_result)
        state.update(channel_result)
        state.update(tracking_result)
        state["selected_offer"] = offer_type
        state["offer_price"] = offer_price

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
