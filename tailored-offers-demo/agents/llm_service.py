"""
LLM Service Module

Provides LLM integration for agents that require reasoning capabilities.
Supports both OpenAI and Anthropic (Claude) models.

Architecture:
- Rule-based agents: Customer Intelligence, Flight Optimization, Channel & Timing, Measurement
- LLM-powered agents: Offer Orchestration (reasoning), Personalization (generation)
"""
import os
from typing import Optional, Literal
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models import BaseChatModel

# LLM provider type
LLMProvider = Literal["openai", "anthropic", "mock"]


def get_llm(
    provider: Optional[LLMProvider] = None,
    model: Optional[str] = None,
    temperature: float = 0.7
) -> BaseChatModel:
    """
    Get an LLM instance based on configuration.

    Priority:
    1. Explicit provider parameter
    2. TAILORED_OFFERS_LLM_PROVIDER env var
    3. Auto-detect based on available API keys
    4. Fall back to mock mode

    Args:
        provider: "openai", "anthropic", or "mock"
        model: Model name (defaults based on provider)
        temperature: Sampling temperature

    Returns:
        LangChain chat model instance
    """
    # Determine provider
    if provider is None:
        provider = os.getenv("TAILORED_OFFERS_LLM_PROVIDER", "").lower()

    if not provider:
        # Auto-detect based on API keys
        if os.getenv("OPENAI_API_KEY"):
            provider = "openai"
        elif os.getenv("ANTHROPIC_API_KEY"):
            provider = "anthropic"
        else:
            provider = "mock"

    # Create LLM based on provider
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model or "gpt-4o-mini",
            temperature=temperature
        )

    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model or "claude-3-5-sonnet-20241022",
            temperature=temperature
        )

    else:
        # Mock mode - returns a mock LLM for demo without API keys
        return MockLLM()


class MockLLM(BaseChatModel):
    """
    Mock LLM for demo purposes when no API key is available.
    Returns pre-defined responses that simulate LLM reasoning.
    """

    @property
    def _llm_type(self) -> str:
        return "mock"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        from langchain_core.outputs import ChatGeneration, ChatResult

        # Extract the last human message
        last_message = messages[-1].content if messages else ""

        # Generate mock response based on context
        if "offer" in last_message.lower() and "orchestrat" in last_message.lower():
            response = self._mock_orchestration_response(last_message)
        elif "personali" in last_message.lower() or "message" in last_message.lower():
            response = self._mock_personalization_response(last_message)
        else:
            response = "Based on my analysis, I recommend proceeding with the standard approach."

        return ChatResult(generations=[ChatGeneration(message=HumanMessage(content=response))])

    def _mock_orchestration_response(self, context: str) -> str:
        return """## Reasoning

After analyzing the customer profile, ML scores, and business context, here is my reasoning:

**Customer Value Assessment:**
- This customer shows strong engagement patterns based on their loyalty tier and travel history
- Historical acceptance rate indicates receptiveness to upgrade offers
- Revenue potential justifies investment in personalized outreach

**Offer Selection Logic:**
1. **Business Class (IU_BUSINESS)**: Highest expected value when customer has business travel pattern and sufficient propensity score (>0.5)
2. **Premium Economy (IU_PREMIUM_ECONOMY)**: Good middle-ground for price-sensitive customers with moderate propensity
3. **Main Cabin Extra (MCE)**: Safe fallback with lower price point but consistent acceptance

**Decision:**
Based on the expected value calculation (propensity × price × margin), I recommend leading with the Business Class offer as the primary option, with MCE as a fallback for customers who may find the price point more accessible.

**Key Factors:**
- Expected Value drives the primary recommendation
- Customer segment influences messaging approach
- Inventory availability has been confirmed by Flight Optimization agent

This demonstrates agent reasoning that goes beyond simple rules - considering multiple factors holistically rather than following rigid if-then logic."""

    def _mock_personalization_response(self, context: str) -> str:
        return """## Personalized Message Generation

Based on the customer profile and offer context, I've crafted a personalized message:

**Tone Selection:** Professional yet warm - appropriate for a business traveler who values efficiency

**Personalization Elements Applied:**
1. **Name**: Used first name for personal touch
2. **Route**: Referenced specific destination to show relevance
3. **Value proposition**: Emphasized productivity benefits (work space, rest)
4. **Urgency**: Calibrated based on time to departure

**Message Strategy:**
- Lead with the benefit most relevant to their travel pattern
- Include specific price to reduce friction
- Mention fallback option to increase conversion probability
- Use action-oriented CTA appropriate for the channel

This message was generated considering:
- Customer's historical preferences
- Brand tone guidelines
- Channel-specific best practices
- Urgency level based on departure timing

The AI-generated approach allows for nuanced personalization that templates cannot achieve - adapting tone, emphasis, and structure based on the complete customer context."""

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        return self._generate(messages, stop, run_manager, **kwargs)


def is_llm_available() -> bool:
    """Check if a real LLM is available (API key configured)."""
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))


def get_llm_provider_name() -> str:
    """Get the name of the configured LLM provider."""
    if os.getenv("OPENAI_API_KEY"):
        return "OpenAI (GPT-4)"
    elif os.getenv("ANTHROPIC_API_KEY"):
        return "Anthropic (Claude)"
    else:
        return "Mock (Demo Mode)"
