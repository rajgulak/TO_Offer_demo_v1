"""
Prompt Service - Centralized prompt management for agents

This service bridges the gap between:
- The PromptEditor UI (frontend)
- The API endpoints (/api/agents/{id}/prompt)
- The actual agents that use these prompts

Features:
- File-based persistence (survives restarts)
- Hot-reload (changes apply immediately)
- Default fallback (uses hardcoded defaults if no custom prompt)
"""

import json
import os
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime


# =============================================================================
# Default Prompts (fallback if no custom prompt set)
# =============================================================================

DEFAULT_PROMPTS = {
    "offer_orchestration": {
        "planner": """You are the Planner in a ReWOO agent for airline offer optimization.

Your job is to analyze customer data and create a plan of what to evaluate before deciding which upgrade offer to give.

Available evaluation types:
- CONFIDENCE: Check ML model confidence for each offer
- RELATIONSHIP: Check if customer had recent service issues
- PRICE_SENSITIVITY: Check if customer needs a discount
- INVENTORY: Check which cabins need to be filled

Create a plan with numbered steps like E1, E2, E3. Each step should check ONE thing.
Only include steps that are relevant for this specific customer.

Output format (JSON):
```json
{
  "steps": [
    {"step_id": "E1", "evaluation_type": "CONFIDENCE", "description": "Check ML confidence for each offer"},
    {"step_id": "E2", "evaluation_type": "RELATIONSHIP", "description": "Check for recent service issues"}
  ],
  "reasoning": "Why I chose these steps"
}
```""",
        "worker": """You are the Worker in a ReWOO agent for airline offer optimization.

Your job is to execute evaluation steps defined by the Planner. For each step, you will check specific data and provide a recommendation.

Evaluation Guidelines:

CONFIDENCE Evaluation:
- If ML confidence < 60%: Flag as LOW confidence, recommend safer option
- If ML confidence > 85%: Flag as HIGH confidence, proceed with offer
- Compare confidence vs expected value trade-offs

RELATIONSHIP Evaluation:
- Check for recent service issues (delays, cancellations, complaints)
- High-value customers (>$50k/year) with issues: Apply goodwill discount
- Consider customer sentiment from recent interactions

PRICE_SENSITIVITY Evaluation:
- HIGH sensitivity: Customer needs significant discount to convert
- MEDIUM sensitivity: Small discount may help conversion
- LOW sensitivity: Customer will pay full price

INVENTORY Evaluation:
- HIGH priority cabins: Need to fill seats, be more aggressive
- Check load factor - proactive offers when LDF < 85%

For each evaluation, provide:
- Clear recommendation (e.g., "APPLY_DISCOUNT", "CHOOSE_SAFER", "PROCEED")
- Reasoning that references the actual data values
- Any policy IDs that should be applied""",
        "solver": """You are the Solver in a ReWOO agent for airline offer optimization.

The Planner created a plan and the Worker executed all evaluations. Now you have all the evidence.

Your job is to synthesize the evidence and make the final offer decision.

Consider:
- If confidence is low on expensive offers, choose a safer option
- If customer had recent issues, apply goodwill discount if policy allows
- If customer is price sensitive, apply appropriate discount per policy

Output format (JSON):
```json
{
  "selected_offer": "IU_BUSINESS" or "MCE" or "IU_PREMIUM_ECONOMY",
  "reasoning": "How I synthesized the evidence to reach this decision",
  "key_factors": ["factor1", "factor2"]
}
```"""
    },
    "personalization": {
        "system": """You are a Personalization Agent for American Airlines' Tailored Offers system.

Your role is to craft compelling, personalized upgrade offer messages that:
1. Address the customer by name and acknowledge their loyalty status
2. Highlight relevant benefits based on their profile
3. Create urgency without being pushy
4. Include the specific offer details (cabin, price, flight info)

Guidelines:
- Keep messages concise (2-3 short paragraphs max)
- Use a warm, professional tone befitting a premium airline
- Personalize based on loyalty tier, travel history, and context
- Never mention internal systems, ML models, or technical details
- Focus on the customer experience and value proposition

Output a JSON object with:
- "subject": Email subject line (compelling, personalized)
- "body": Email body (personalized message)
- "push_notification": Short push notification text (under 100 chars)
"""
    }
}


# =============================================================================
# Prompt Storage (File-based persistence)
# =============================================================================

class PromptStorage:
    """
    Persists custom prompts to a JSON file.

    File location: config/custom_prompts.json
    """

    STORAGE_PATH = Path(__file__).parent / "custom_prompts.json"

    _cache: Optional[Dict[str, Any]] = None
    _cache_mtime: float = 0

    @classmethod
    def load(cls) -> Dict[str, Any]:
        """Load custom prompts from file."""
        if not cls.STORAGE_PATH.exists():
            return {}

        try:
            # Check if file changed since last cache
            mtime = cls.STORAGE_PATH.stat().st_mtime
            if cls._cache is not None and cls._cache_mtime >= mtime:
                return cls._cache

            with open(cls.STORAGE_PATH, 'r') as f:
                cls._cache = json.load(f)
                cls._cache_mtime = mtime
                return cls._cache
        except Exception as e:
            print(f"Error loading custom prompts: {e}")
            return {}

    @classmethod
    def save(cls, prompts: Dict[str, Any]) -> bool:
        """Save custom prompts to file."""
        try:
            with open(cls.STORAGE_PATH, 'w') as f:
                json.dump(prompts, f, indent=2)
            cls._cache = prompts
            cls._cache_mtime = cls.STORAGE_PATH.stat().st_mtime
            return True
        except Exception as e:
            print(f"Error saving custom prompts: {e}")
            return False

    @classmethod
    def get(cls, key: str) -> Optional[str]:
        """Get a custom prompt by key."""
        prompts = cls.load()
        return prompts.get(key)

    @classmethod
    def set(cls, key: str, value: str) -> bool:
        """Set a custom prompt."""
        prompts = cls.load()
        prompts[key] = {
            "content": value,
            "updated_at": datetime.now().isoformat(),
        }
        return cls.save(prompts)

    @classmethod
    def delete(cls, key: str) -> bool:
        """Delete a custom prompt (reset to default)."""
        prompts = cls.load()
        if key in prompts:
            del prompts[key]
            return cls.save(prompts)
        return True

    @classmethod
    def has_custom(cls, key: str) -> bool:
        """Check if a custom prompt exists."""
        prompts = cls.load()
        return key in prompts


# =============================================================================
# Prompt Service (Main Interface)
# =============================================================================

class PromptService:
    """
    Main interface for getting prompts.

    Usage:
        from config.prompt_service import PromptService

        # Get planner prompt (custom if set, otherwise default)
        prompt = PromptService.get_planner_prompt()

        # Get personalization prompt
        prompt = PromptService.get_personalization_prompt()

        # Set custom prompt
        PromptService.set_custom_prompt("offer_orchestration.planner", "New prompt...")
    """

    # Key mappings for different agent prompts
    PROMPT_KEYS = {
        "offer_orchestration": "offer_orchestration.planner",  # Main agent prompt
        "offer_orchestration.planner": "offer_orchestration.planner",
        "offer_orchestration.worker": "offer_orchestration.worker",
        "offer_orchestration.solver": "offer_orchestration.solver",
        "personalization": "personalization.system",
        "personalization.system": "personalization.system",
    }

    @classmethod
    def get_prompt(cls, agent_id: str, prompt_type: str = "system") -> str:
        """
        Get the active prompt for an agent.

        Args:
            agent_id: Agent identifier (e.g., "offer_orchestration", "personalization")
            prompt_type: Type of prompt (e.g., "planner", "solver", "system")

        Returns:
            The custom prompt if set, otherwise the default prompt
        """
        key = f"{agent_id}.{prompt_type}"

        # Check for custom prompt
        custom = PromptStorage.get(key)
        if custom:
            return custom.get("content", "")

        # Fall back to default
        if agent_id in DEFAULT_PROMPTS:
            return DEFAULT_PROMPTS[agent_id].get(prompt_type, "")

        return ""

    @classmethod
    def get_planner_prompt(cls) -> str:
        """Get the ReWOO planner prompt."""
        return cls.get_prompt("offer_orchestration", "planner")

    @classmethod
    def get_worker_prompt(cls) -> str:
        """Get the ReWOO worker prompt (evaluation guidelines)."""
        return cls.get_prompt("offer_orchestration", "worker")

    @classmethod
    def get_solver_prompt(cls) -> str:
        """Get the ReWOO solver prompt."""
        return cls.get_prompt("offer_orchestration", "solver")

    @classmethod
    def get_personalization_prompt(cls) -> str:
        """Get the personalization agent prompt."""
        return cls.get_prompt("personalization", "system")

    @classmethod
    def set_custom_prompt(cls, key: str, content: str) -> bool:
        """
        Set a custom prompt.

        Args:
            key: Prompt key (e.g., "offer_orchestration.planner")
            content: The custom prompt content
        """
        return PromptStorage.set(key, content)

    @classmethod
    def reset_prompt(cls, key: str) -> bool:
        """Reset a prompt to its default."""
        return PromptStorage.delete(key)

    @classmethod
    def is_custom(cls, key: str) -> bool:
        """Check if a prompt has been customized."""
        return PromptStorage.has_custom(key)

    @classmethod
    def get_default_prompt(cls, agent_id: str, prompt_type: str = "system") -> str:
        """Get the default prompt (ignoring any customization)."""
        if agent_id in DEFAULT_PROMPTS:
            return DEFAULT_PROMPTS[agent_id].get(prompt_type, "")
        return ""

    @classmethod
    def get_all_prompts_info(cls) -> Dict[str, Any]:
        """Get information about all available prompts."""
        info = {}

        for agent_id, prompts in DEFAULT_PROMPTS.items():
            for prompt_type in prompts.keys():
                key = f"{agent_id}.{prompt_type}"
                info[key] = {
                    "agent_id": agent_id,
                    "prompt_type": prompt_type,
                    "is_custom": cls.is_custom(key),
                    "default_preview": prompts[prompt_type][:200] + "...",
                }

        return info


# =============================================================================
# Convenience Functions
# =============================================================================

def get_planner_prompt() -> str:
    """Get the ReWOO planner prompt."""
    return PromptService.get_planner_prompt()


def get_worker_prompt() -> str:
    """Get the ReWOO worker prompt (evaluation guidelines)."""
    return PromptService.get_worker_prompt()


def get_solver_prompt() -> str:
    """Get the ReWOO solver prompt."""
    return PromptService.get_solver_prompt()


def get_personalization_prompt() -> str:
    """Get the personalization agent prompt."""
    return PromptService.get_personalization_prompt()


def set_custom_prompt(key: str, content: str) -> bool:
    """Set a custom prompt."""
    return PromptService.set_custom_prompt(key, content)


def reset_prompt(key: str) -> bool:
    """Reset a prompt to default."""
    return PromptService.reset_prompt(key)


def is_prompt_custom(key: str) -> bool:
    """Check if a prompt is customized."""
    return PromptService.is_custom(key)
