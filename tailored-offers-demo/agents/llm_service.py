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


def should_use_dynamic_reasoning() -> bool:
    """Check if dynamic LLM-generated reasoning is enabled."""
    # Enable by default if LLM is available, can override with env var
    env_setting = os.getenv("USE_DYNAMIC_REASONING", "").lower()
    if env_setting == "true":
        return True
    if env_setting == "false":
        return False
    # Default: use dynamic reasoning if LLM is available
    return is_llm_available()


def generate_dynamic_reasoning(
    agent_name: str,
    data_used: dict,
    decision: str,
    decision_details: dict,
    context: str = ""
) -> str:
    """
    Generate natural-sounding reasoning text using an LLM.

    This keeps the DECISION as rules-based (fast, deterministic),
    but uses an LLM to EXPLAIN the decision in natural language.

    Args:
        agent_name: Name of the agent (e.g., "Customer Intelligence Agent")
        data_used: Dict of data sources and values used
        decision: The decision made (e.g., "ELIGIBLE", "NOT ELIGIBLE")
        decision_details: Additional details about the decision
        context: Optional additional context

    Returns:
        Natural language explanation of the decision
    """
    if not should_use_dynamic_reasoning():
        return None  # Caller should use templated reasoning

    llm = get_llm(temperature=0.3)  # Lower temperature for consistent explanations

    # Format data_used into readable text
    data_text = _format_data_used(data_used)

    prompt = f"""You are explaining a decision made by the {agent_name} in an airline offer system.

DATA USED:
{data_text}

DECISION: {decision}
DECISION DETAILS: {decision_details}

{f"ADDITIONAL CONTEXT: {context}" if context else ""}

Write a clear, conversational explanation of this decision. Use these guidelines:
1. Start with "📊 DATA USED" section showing what data was pulled from which systems
2. Then "🔍 ANALYSIS" explaining the key factors considered
3. Then "✅ DECISION" with the verdict
4. End with "📍 IN SIMPLE TERMS" - a 2-3 sentence plain English summary
5. Add "💡 WHY THIS AGENT MATTERS" - explain what could go wrong without this check

Use the actual data values provided. Be specific, not generic.
Format with clear sections and bullet points.
Keep it concise but informative."""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content
    except Exception as e:
        print(f"LLM reasoning generation failed: {e}")
        return None  # Caller should fall back to templated reasoning


def _format_data_used(data_used: dict) -> str:
    """Format data_used dict into readable text for the LLM prompt."""
    lines = []
    for source, data in data_used.items():
        lines.append(f"\n{source}:")
        if isinstance(data, dict):
            for key, value in data.items():
                lines.append(f"  - {key}: {value}")
        else:
            lines.append(f"  - {data}")
    return "\n".join(lines)


def get_llm_provider_name() -> str:
    """Get the name of the configured LLM provider."""
    if os.getenv("OPENAI_API_KEY"):
        return "OpenAI (GPT-4)"
    elif os.getenv("ANTHROPIC_API_KEY"):
        return "Anthropic (Claude)"
    else:
        return "Mock (Demo Mode)"
