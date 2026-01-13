"""
Configuration settings for Tailored Offers Demo
"""
import os
from dotenv import load_dotenv

load_dotenv()

# LLM Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")  # "anthropic" or "openai"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "claude-sonnet-4-20250514")

# Demo Mode
DEMO_MODE = os.getenv("DEMO_MODE", "live")  # "live" or "simulated"

# Offer Configuration
OFFER_TYPES = {
    "IU_BUSINESS": {
        "name": "Instant Upgrade - Business Class",
        "base_price": 199,
        "min_discount": 0,
        "max_discount": 0.20,
        "margin": 0.90
    },
    "IU_PREMIUM_ECONOMY": {
        "name": "Instant Upgrade - Premium Economy",
        "base_price": 129,
        "min_discount": 0,
        "max_discount": 0.15,
        "margin": 0.88
    },
    "MCE": {
        "name": "Main Cabin Extra",
        "base_price": 39,
        "min_discount": 0,
        "max_discount": 0.25,
        "margin": 0.85
    }
}

# Channel Configuration
CHANNELS = {
    "push": {"priority": 1, "avg_open_rate": 0.45},
    "email": {"priority": 2, "avg_open_rate": 0.22},
    "in_app": {"priority": 3, "avg_open_rate": 0.65}
}

# Timing Windows
TIMING_WINDOWS = {
    "T-72": {"hours_before": 72, "urgency": "low"},
    "T-48": {"hours_before": 48, "urgency": "medium"},
    "T-24": {"hours_before": 24, "urgency": "high"}
}

# Loyalty Tiers
LOYALTY_TIERS = {
    "Executive Platinum": {"level": 5, "upgrade_multiplier": 1.3},
    "Platinum Pro": {"level": 4, "upgrade_multiplier": 1.2},
    "Platinum": {"level": 3, "upgrade_multiplier": 1.1},
    "Gold": {"level": 2, "upgrade_multiplier": 1.0},
    "General": {"level": 1, "upgrade_multiplier": 0.9}
}
