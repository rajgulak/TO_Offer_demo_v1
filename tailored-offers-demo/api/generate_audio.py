#!/usr/bin/env python3
"""
Pre-generate all audio files for the guided demo.
Run this script once to create all MP3 files.
"""
import os
from pathlib import Path

# All demo steps with their narration text
# Note: Use commas for short pauses, periods for longer pauses, ellipsis for dramatic pauses
DEMO_STEPS = [
    # Introduction
    ("intro-1", "Welcome. Let me show you, what makes Agentic AI, different."),
    ("intro-2", "With an Agent, you give it a goal. Not step by step instructions. The agent figures out, how to reach that goal, on its own."),
    ("intro-3", "It plans, like a human would plan. It uses tools via MCP, when it needs data. And it reasons, like a human would reason."),
    ("intro-4", "We've built this, around four pillars. Let me show you, each one."),

    # Pillars Overview
    ("pillars-overview", "Here they are. Planning. Reasoning. Business Control. And, Human plus AI. Together, these give you, full transparency, into every decision."),

    # Pillar 1: Planning
    ("p1-intro", "Pillar One. Planning. We give the agent a goal. Find the best offer, for this customer. The agent creates its own strategy, to achieve that goal."),
    ("p1-customer", "Let me select a customer, and show you."),
    ("p1-run", "Watch the Planner, in action."),
    ("p1-planner", "See this? The Planner figured out, what factors matter, for this specific customer. Loyalty status. Recent history. Current context. Just like a human expert would."),
    ("p1-summary", "This is Pillar One. Planning. The agent decides how to solve the problem. Not us."),

    # Pillar 2: Reasoning
    ("p2-intro", "Pillar Two. Reasoning. Now the Workers execute the plan. When they need data, they use tools via MCP."),
    ("p2-worker", "Watch the Workers use MCP tools. Customer profile from AADV. Flight inventory from DCSID. ML scores from our models. The agent connects to existing systems, when it needs to."),
    ("p2-solver", "Then, the Solver, reasons through all the evidence. Just like a human would reason it out. And you can read, exactly how it decided."),
    ("p2-transparency", "Planning, plus Reasoning, equals Transparency. Every factor considered. Every decision explained. Full audit trail."),
    ("p2-value", "When a customer asks, why did I get this offer? You have a real answer. When regulators ask, how do you decide? You can show them."),

    # Pillar 3: Business Control
    ("p3-intro", "Pillar Three. Business Control. Can you actually control this AI? Absolutely."),
    ("p3-panel", "Let me open, the control panel."),
    ("p3-highlight", "This is your control center. No IT tickets. No waiting weeks. Changes take effect, immediately."),
    ("p3-assistant", "The Prompt Assistant, lets you give instructions, in plain English."),
    ("p3-example", "Type, give extra discount, to customers with delays. That's it. The agent understands, and follows your instruction."),
    ("p3-policy", "For more direct control, there are policy values, you can adjust, in real time."),
    ("p3-values", "Discount percentages. VIP thresholds. Maximum amounts. Change them here. The next decision, uses them instantly."),
    ("p3-summary", "This is Pillar Three. Business Control. You drive the AI. Not IT. Not vendors. You."),

    # Pillar 4: Human + AI
    ("p4-intro", "Pillar Four. Human plus AI. For sensitive decisions, you might want, a human to approve."),
    ("p4-toggle", "That's Human in the Loop. Let me turn it on."),
    ("p4-run", "Now, watch what happens."),
    ("p4-pending", "The agent analyzed everything, and made a recommendation. But look. It stopped. Awaiting approval."),
    ("p4-approval", "A human reviews. Then approves, or rejects. AI speed, for analysis. Human judgment, for the decision."),
    ("p4-summary", "This is Pillar Four. Human plus AI. Best of both worlds."),

    # Closing
    ("close-pattern", "One more thing. What you saw, is a pattern, you can apply anywhere."),
    ("close-examples", "Seat recommendations. Ancillary offers. Service routing. Loyalty decisions. Any complex decision, that needs transparency, and control."),
    ("close-recap", "So, why Agentic AI? Four pillars."),
    ("close-four", "One, Planning. The agent thinks first. Two, Reasoning. Full transparency. Three, Business control. You drive it. Four, Human plus AI. You stay in charge."),
    ("close-end", "That's Agentic AI. Planning. Reasoning. Control. Thank you, for watching."),
]

def generate_audio_files():
    """Generate all audio files using OpenAI TTS."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable not set")
        return False

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
    except ImportError:
        print("ERROR: openai library not installed. Run: pip install openai")
        return False

    # Create output directory
    output_dir = Path(__file__).parent / "static" / "audio"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating {len(DEMO_STEPS)} audio files...")
    print(f"Output directory: {output_dir}")
    print("-" * 50)

    for i, (step_id, text) in enumerate(DEMO_STEPS):
        output_path = output_dir / f"{step_id}.mp3"

        # Skip if already exists
        if output_path.exists():
            print(f"[{i+1}/{len(DEMO_STEPS)}] {step_id}: Already exists, skipping")
            continue

        print(f"[{i+1}/{len(DEMO_STEPS)}] {step_id}: Generating...")

        try:
            response = client.audio.speech.create(
                model="tts-1",
                voice="nova",
                input=text,
                speed=1.0,
            )

            # Save to file
            with open(output_path, "wb") as f:
                f.write(response.content)

            print(f"  ✓ Saved: {output_path.name} ({len(response.content)} bytes)")

        except Exception as e:
            print(f"  ✗ Error: {e}")
            return False

    print("-" * 50)
    print(f"Done! Generated {len(DEMO_STEPS)} audio files.")
    print(f"Files saved to: {output_dir}")
    return True

if __name__ == "__main__":
    generate_audio_files()
