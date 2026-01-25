#!/usr/bin/env python3
"""
Generate narration audio files for the Explainer Video.

Run this script once when you have OpenAI API access to create
static audio files that work offline.

Usage:
    export OPENAI_API_KEY=your-key
    python scripts/generate_narration_audio.py

The generated MP3 files will be saved to frontend/public/audio/
"""

import os
import sys
from pathlib import Path

# Narration scripts for each scene
NARRATIONS = {
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


def generate_audio():
    """Generate audio files for all scenes."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set")
        print("Set it with: export OPENAI_API_KEY=your-key")
        sys.exit(1)

    try:
        from openai import OpenAI
    except ImportError:
        print("Error: openai package not installed")
        print("Install with: pip install openai")
        sys.exit(1)

    # Output directory
    script_dir = Path(__file__).parent.parent
    output_dir = script_dir / "frontend" / "public" / "audio"
    output_dir.mkdir(parents=True, exist_ok=True)

    client = OpenAI(api_key=api_key)

    print(f"Generating audio files to: {output_dir}")
    print("-" * 50)

    for scene_id, text in NARRATIONS.items():
        output_path = output_dir / f"{scene_id}.mp3"
        print(f"Generating: {scene_id}.mp3 ... ", end="", flush=True)

        try:
            response = client.audio.speech.create(
                model="tts-1-hd",
                voice="nova",  # Warm, engaging voice
                input=text,
                speed=0.95,  # Slightly slower for clarity
            )

            with open(output_path, "wb") as f:
                f.write(response.content)

            size_kb = output_path.stat().st_size / 1024
            print(f"Done ({size_kb:.1f} KB)")

        except Exception as e:
            print(f"Failed: {e}")

    print("-" * 50)
    print("Audio generation complete!")
    print(f"Files saved to: {output_dir}")
    print("\nThese files will be used automatically by the Explainer Video.")


if __name__ == "__main__":
    generate_audio()
