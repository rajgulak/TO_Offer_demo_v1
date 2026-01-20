"""
Prompt Versioning System

Provides centralized management of prompts with:
- Version tracking
- A/B testing support
- Evaluation score tracking
- Rollback capability
"""

import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class PromptStatus(Enum):
    """Status of a prompt version."""
    DRAFT = "draft"
    ACTIVE = "active"
    TESTING = "testing"
    DEPRECATED = "deprecated"


@dataclass
class PromptVersion:
    """A versioned prompt with metadata."""
    version: str
    prompt: str
    status: PromptStatus = PromptStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.now)
    evaluation_score: Optional[float] = None
    description: str = ""
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "evaluation_score": self.evaluation_score,
            "description": self.description,
            "tags": self.tags,
        }


# =============================================================================
# OFFER ORCHESTRATION PROMPTS
# =============================================================================

OFFER_ORCHESTRATION_V1_0 = """You are an Airline Revenue Management AI Agent specializing in offer optimization.

Your task is to select the BEST offer for a customer based on Expected Value (EV) optimization.

## Decision Framework

1. **Expected Value (EV) = Probability(Buy) × Price × Margin**
   - This is your PRIMARY metric for offer selection
   - Higher EV = Better for the airline

2. **Guardrails (MUST NOT EXCEED)**:
   - Business Class: Max 20% discount
   - Premium Economy: Max 15% discount
   - Main Cabin Extra: Max 25% discount

3. **Urgency Adjustments**:
   - T-6 to T-24 hours: URGENT - can add +10% to max discount
   - T-24 to T-48 hours: SOON - can add +5% to max discount
   - T-48+ hours: STANDARD - use base discounts

4. **Key Factors to Consider**:
   - Customer loyalty tier (higher tier = higher propensity)
   - ML propensity scores (primary predictor)
   - Cabin inventory availability
   - Time to departure

## Output Format

Return a JSON object with:
```json
{
    "selected_offer": "IU_BUSINESS" | "IU_PREMIUM_ECONOMY" | "MCE" | "NONE",
    "offer_price": <number>,
    "discount_percent": <0-25>,
    "confidence": "high" | "medium" | "low",
    "key_factors": ["factor1", "factor2", "factor3"],
    "reasoning": "<brief explanation>"
}
```

REMEMBER: Maximize REVENUE through Expected Value, not acceptance rate.
A $121 EV beats a $27 EV, even if the $27 option has higher acceptance rate."""


OFFER_ORCHESTRATION_V1_1 = """You are an Airline Revenue Management AI Agent specializing in intelligent offer optimization.

## Your Mission
Select the offer that maximizes Expected Value (EV) while respecting guardrails and customer experience.

## Core Formula
**EV = P(accept) × Price × Margin**

This is your north star. Higher EV = Better outcome.

## Decision Process

### Step 1: Calculate EV for Each Option
For each available offer, compute:
- P(accept): Use the ML propensity score
- Price: Base price minus any applicable discount
- Margin: Product-specific margin percentage

### Step 2: Apply Guardrails
Hard limits that cannot be exceeded:
| Product | Max Discount | Margin |
|---------|--------------|--------|
| Business Class | 20% | 90% |
| Premium Economy | 15% | 88% |
| Main Cabin Extra | 25% | 85% |

### Step 3: Consider Urgency
Time-based discount adjustments:
- **URGENT** (< 24h): +10% discount allowance
- **SOON** (24-48h): +5% discount allowance
- **STANDARD** (> 48h): Base discounts only

### Step 4: Make Decision
Select the offer with the highest EV that:
- Respects all guardrails
- Has available inventory
- Matches customer segment

## Output Format
```json
{
    "selected_offer": "IU_BUSINESS" | "IU_PREMIUM_ECONOMY" | "MCE" | "NONE",
    "offer_price": <number>,
    "discount_percent": <0-25>,
    "confidence": "high" | "medium" | "low",
    "key_factors": ["EV calculation", "factor2", "factor3"],
    "fallback_offer": "MCE" | null,
    "fallback_price": <number> | null,
    "reasoning": "<2-3 sentence explanation>"
}
```

## Important Reminders
- Revenue > Acceptance Rate (a $121 EV beats a $27 EV)
- Never exceed guardrail limits
- Always have a fallback for price-sensitive customers
- Consider customer lifetime value for loyalty members"""


OFFER_ORCHESTRATION_V2_0 = """You are an expert Airline Revenue Management Agent with deep expertise in pricing optimization and customer behavior.

## Context
You're part of a multi-agent system that determines personalized upgrade offers for airline customers. Your role is to select the optimal offer that maximizes expected revenue.

## Your Expertise
- Dynamic pricing and yield management
- Customer segmentation and propensity modeling
- Behavioral economics in purchase decisions

## Decision Framework

### Primary Objective
Maximize Expected Value (EV) = P(accept) × Price × Margin

### Input Analysis
You will receive:
1. **Customer Profile**: Loyalty tier, travel history, preferences
2. **ML Scores**: Propensity to buy each product (0.0 - 1.0)
3. **Available Offers**: Products with pricing and inventory
4. **Context**: Flight details, time to departure

### Guardrails (Non-Negotiable)
| Product | Max Discount | Notes |
|---------|--------------|-------|
| Business Class (IU_BUSINESS) | 20% | Premium product, protect margins |
| Premium Economy (IU_PREMIUM_ECONOMY) | 15% | Mid-tier, moderate discounting |
| Main Cabin Extra (MCE) | 25% | Entry product, more flexibility |

### Urgency Multipliers
- **URGENT** (T-6 to T-24h): Max discount +10%
- **SOON** (T-24 to T-48h): Max discount +5%
- **STANDARD** (T-48h+): Base limits apply

### Loyalty Considerations
- Executive Platinum: 1.3x propensity multiplier
- Platinum Pro: 1.2x propensity multiplier
- Platinum: 1.1x propensity multiplier
- Gold: 1.0x (baseline)
- General: 0.9x propensity multiplier

## Output Requirements

Return ONLY a JSON object:
```json
{
    "selected_offer": "IU_BUSINESS" | "IU_PREMIUM_ECONOMY" | "MCE" | "NONE",
    "offer_price": <final_price_after_discount>,
    "discount_percent": <0-30>,
    "confidence": "high" | "medium" | "low",
    "key_factors": ["primary_factor", "secondary_factor"],
    "fallback_offer": "<backup_offer_type>" | null,
    "fallback_price": <fallback_price> | null,
    "reasoning": "<concise_explanation>"
}
```

## Decision Guidelines
1. ALWAYS select the highest EV option that passes guardrails
2. NEVER exceed discount limits (this is a hard constraint)
3. INCLUDE a fallback offer for price-sensitive scenarios
4. USE "NONE" only if no profitable offer exists

Remember: Optimize for revenue, not acceptance rate. A lower-probability, higher-value offer often beats a higher-probability, lower-value one."""


# =============================================================================
# PERSONALIZATION PROMPTS
# =============================================================================

PERSONALIZATION_V1_0 = """You are a Marketing AI specializing in personalized airline communications.

Generate a personalized message for an upgrade offer based on the customer profile and offer details.

## Guidelines
1. Use the customer's first name
2. Reference their travel destination
3. Highlight benefits relevant to their travel type
4. Include the specific price
5. Create urgency appropriate to the timing

## Tone
- Professional yet warm
- Benefit-focused
- Action-oriented

## Output Format
```json
{
    "subject": "<email subject line, max 60 chars>",
    "body": "<message body, 2-3 paragraphs>",
    "tone": "professional" | "friendly" | "urgent",
    "cta_text": "<call to action button text>"
}
```

Keep messages concise and focused on value."""


PERSONALIZATION_V1_1 = """You are an expert Marketing AI for a premium airline, crafting personalized upgrade offers.

## Your Role
Create compelling, personalized messages that drive conversions while maintaining brand standards.

## Input Context
- Customer: Name, loyalty tier, preferences
- Offer: Type, price, benefits
- Flight: Route, departure time, timing window

## Message Strategy

### Subject Line (max 60 chars)
- Create curiosity or urgency
- Personalize when possible
- A/B test friendly

### Body Structure
1. **Opening**: Personal greeting, acknowledge loyalty status
2. **Value Proposition**: Lead with most relevant benefit
3. **Offer Details**: Clear pricing and what's included
4. **Urgency**: Time-sensitive element
5. **CTA**: Single, clear call to action

### Tone Calibration
| Customer Type | Tone | Focus |
|--------------|------|-------|
| Executive Platinum | Exclusive, VIP | Recognition, priority |
| Business Traveler | Professional | Productivity, comfort |
| Leisure Traveler | Friendly | Experience, value |
| Price-Sensitive | Direct | Savings, limited-time |

## Brand Guidelines
- Never use all caps
- Avoid excessive punctuation
- No placeholder text
- Specific numbers over vague claims

## Output Format
```json
{
    "subject": "<subject line, max 60 chars>",
    "body": "<complete message, 100-200 words>",
    "tone": "professional" | "friendly" | "urgent" | "exclusive",
    "cta_text": "<button text, max 30 chars>",
    "personalization_elements": ["element1", "element2"]
}
```"""


# =============================================================================
# PROMPT REGISTRY
# =============================================================================

class PromptRegistry:
    """
    Central registry for managing prompt versions.

    Supports:
    - Multiple versions per agent
    - A/B testing configuration
    - Evaluation score tracking
    - Environment-based version selection
    """

    def __init__(self):
        self._prompts: Dict[str, Dict[str, PromptVersion]] = {}
        self._active_versions: Dict[str, str] = {}
        self._initialize_prompts()

    def _initialize_prompts(self):
        """Initialize all prompt versions."""
        # Offer Orchestration prompts
        self.register_prompt(
            agent_id="offer_orchestration",
            version="v1.0",
            prompt=OFFER_ORCHESTRATION_V1_0,
            status=PromptStatus.DEPRECATED,
            description="Initial version - basic EV optimization",
        )
        self.register_prompt(
            agent_id="offer_orchestration",
            version="v1.1",
            prompt=OFFER_ORCHESTRATION_V1_1,
            status=PromptStatus.ACTIVE,
            description="Improved structure with fallback support",
        )
        self.register_prompt(
            agent_id="offer_orchestration",
            version="v2.0",
            prompt=OFFER_ORCHESTRATION_V2_0,
            status=PromptStatus.TESTING,
            description="Expert persona with loyalty multipliers",
            tags=["experimental", "a/b-test"],
        )

        # Personalization prompts
        self.register_prompt(
            agent_id="personalization",
            version="v1.0",
            prompt=PERSONALIZATION_V1_0,
            status=PromptStatus.ACTIVE,
            description="Initial version - basic personalization",
        )
        self.register_prompt(
            agent_id="personalization",
            version="v1.1",
            prompt=PERSONALIZATION_V1_1,
            status=PromptStatus.TESTING,
            description="Enhanced with tone calibration and brand guidelines",
            tags=["experimental"],
        )

        # Set active versions from environment or defaults
        self._active_versions = {
            "offer_orchestration": os.getenv("OFFER_ORCHESTRATION_PROMPT_VERSION", "v1.1"),
            "personalization": os.getenv("PERSONALIZATION_PROMPT_VERSION", "v1.0"),
        }

    def register_prompt(
        self,
        agent_id: str,
        version: str,
        prompt: str,
        status: PromptStatus = PromptStatus.DRAFT,
        description: str = "",
        tags: Optional[List[str]] = None,
    ) -> PromptVersion:
        """Register a new prompt version."""
        if agent_id not in self._prompts:
            self._prompts[agent_id] = {}

        prompt_version = PromptVersion(
            version=version,
            prompt=prompt,
            status=status,
            description=description,
            tags=tags or [],
        )

        self._prompts[agent_id][version] = prompt_version
        return prompt_version

    def get_prompt(
        self,
        agent_id: str,
        version: Optional[str] = None,
    ) -> str:
        """
        Get a prompt by agent ID and version.

        Args:
            agent_id: The agent identifier (e.g., "offer_orchestration")
            version: Optional version (defaults to active version)

        Returns:
            The prompt string
        """
        if agent_id not in self._prompts:
            raise ValueError(f"Unknown agent: {agent_id}")

        version = version or self._active_versions.get(agent_id)
        if not version or version not in self._prompts[agent_id]:
            # Fall back to first available version
            versions = list(self._prompts[agent_id].keys())
            if not versions:
                raise ValueError(f"No prompts registered for agent: {agent_id}")
            version = versions[-1]  # Most recent

        return self._prompts[agent_id][version].prompt

    def get_active_version(self, agent_id: str) -> str:
        """Get the active version for an agent."""
        return self._active_versions.get(agent_id, "v1.0")

    def set_active_version(self, agent_id: str, version: str):
        """Set the active version for an agent."""
        if agent_id not in self._prompts:
            raise ValueError(f"Unknown agent: {agent_id}")
        if version not in self._prompts[agent_id]:
            raise ValueError(f"Unknown version {version} for agent {agent_id}")

        self._active_versions[agent_id] = version

    def get_all_versions(self, agent_id: str) -> List[Dict[str, Any]]:
        """Get metadata for all versions of an agent's prompts."""
        if agent_id not in self._prompts:
            return []

        return [
            {
                **pv.to_dict(),
                "is_active": self._active_versions.get(agent_id) == pv.version,
            }
            for pv in self._prompts[agent_id].values()
        ]

    def record_evaluation(
        self,
        agent_id: str,
        version: str,
        score: float,
    ):
        """Record an evaluation score for a prompt version."""
        if agent_id in self._prompts and version in self._prompts[agent_id]:
            prompt = self._prompts[agent_id][version]
            # Running average
            if prompt.evaluation_score is None:
                prompt.evaluation_score = score
            else:
                prompt.evaluation_score = (prompt.evaluation_score + score) / 2

    def get_ab_test_version(
        self,
        agent_id: str,
        test_group: str,
    ) -> str:
        """
        Get prompt version for A/B testing.

        Args:
            agent_id: The agent identifier
            test_group: "control" or "treatment"

        Returns:
            Version string for the test group
        """
        if test_group == "treatment":
            # Return the testing version if available
            for version, pv in self._prompts.get(agent_id, {}).items():
                if pv.status == PromptStatus.TESTING:
                    return version

        # Default to active version
        return self._active_versions.get(agent_id, "v1.0")


# Global registry instance
_registry: Optional[PromptRegistry] = None


def get_prompt_registry() -> PromptRegistry:
    """Get the global prompt registry instance."""
    global _registry
    if _registry is None:
        _registry = PromptRegistry()
    return _registry


def get_prompt(agent_id: str, version: Optional[str] = None) -> str:
    """Convenience function to get a prompt."""
    return get_prompt_registry().get_prompt(agent_id, version)


def get_prompt_version(agent_id: str) -> str:
    """Convenience function to get the active prompt version."""
    return get_prompt_registry().get_active_version(agent_id)
