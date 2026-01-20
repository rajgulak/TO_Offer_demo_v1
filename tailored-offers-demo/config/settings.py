"""
Configuration settings for Tailored Offers Demo
"""
import os
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# LLM Configuration
# =============================================================================
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")  # "anthropic" or "openai"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "claude-sonnet-4-20250514")

# Demo Mode
DEMO_MODE = os.getenv("DEMO_MODE", "live")  # "live" or "simulated"

# =============================================================================
# Observability Configuration
# =============================================================================

# Structured Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv("LOG_FORMAT", "json")  # "json" or "console"
LOG_FILE = os.getenv("LOG_FILE", None)

# Prometheus Metrics
METRICS_ENABLED = os.getenv("METRICS_ENABLED", "true").lower() == "true"
METRICS_PORT = int(os.getenv("METRICS_PORT", "9090"))

# LangSmith Tracing
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", "")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "tailored-offers")
LANGSMITH_TRACING = os.getenv("LANGSMITH_TRACING", "false").lower() == "true"

# LangFuse Tracing (alternative to LangSmith)
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

# =============================================================================
# Retry Configuration
# =============================================================================
LLM_RETRY_MAX_ATTEMPTS = int(os.getenv("LLM_RETRY_MAX_ATTEMPTS", "3"))
LLM_RETRY_MIN_WAIT = float(os.getenv("LLM_RETRY_MIN_WAIT", "2.0"))
LLM_RETRY_MAX_WAIT = float(os.getenv("LLM_RETRY_MAX_WAIT", "30.0"))
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "60.0"))

MCP_RETRY_MAX_ATTEMPTS = int(os.getenv("MCP_RETRY_MAX_ATTEMPTS", "3"))
MCP_RETRY_MIN_WAIT = float(os.getenv("MCP_RETRY_MIN_WAIT", "1.0"))
MCP_RETRY_MAX_WAIT = float(os.getenv("MCP_RETRY_MAX_WAIT", "10.0"))
MCP_TIMEOUT_SECONDS = float(os.getenv("MCP_TIMEOUT_SECONDS", "30.0"))

# =============================================================================
# Prompt Versioning
# =============================================================================
OFFER_ORCHESTRATION_PROMPT_VERSION = os.getenv("OFFER_ORCHESTRATION_PROMPT_VERSION", "v1.1")
PERSONALIZATION_PROMPT_VERSION = os.getenv("PERSONALIZATION_PROMPT_VERSION", "v1.0")

# A/B Testing
AB_TEST_ENABLED = os.getenv("AB_TEST_ENABLED", "false").lower() == "true"
AB_TEST_TREATMENT_PERCENTAGE = float(os.getenv("AB_TEST_TREATMENT_PERCENTAGE", "0.1"))

# =============================================================================
# Validation Configuration
# =============================================================================
VALIDATION_ENABLED = os.getenv("VALIDATION_ENABLED", "true").lower() == "true"
VALIDATION_STRICT_MODE = os.getenv("VALIDATION_STRICT_MODE", "false").lower() == "true"

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
