"""
LLM Service Module

Provides LLM integration for agents that require reasoning capabilities.
Supports both OpenAI and Anthropic (Claude) models.

Architecture:
- Rule-based agents: Customer Intelligence, Flight Optimization, Channel & Timing, Measurement
- LLM-powered agents: Offer Orchestration (reasoning), Personalization (generation)

Production Features:
- Retry logic with exponential backoff (tenacity)
- Structured logging with correlation IDs (structlog)
- Prometheus metrics for latency and success rates
- LangSmith/LangFuse tracing for observability
"""
import os
import time
from typing import Optional, Literal, Callable, TypeVar
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models import BaseChatModel

# Import infrastructure modules
try:
    from infrastructure.logging import get_logger, log_llm_call, set_correlation_id
    from infrastructure.metrics import metrics, llm_calls, llm_latency, llm_fallback
    from infrastructure.retry import retry_llm_call, RetryConfig
    from infrastructure.tracing import get_tracer, trace_llm_call, TraceMetadata
    from infrastructure.validation import LLMResponseValidator, ValidationResult
    INFRASTRUCTURE_AVAILABLE = True
except ImportError:
    INFRASTRUCTURE_AVAILABLE = False

# Initialize logger
logger = get_logger("llm_service") if INFRASTRUCTURE_AVAILABLE else None

# LLM provider type
LLMProvider = Literal["openai", "anthropic", "mock"]

# Type variable for generic return types
T = TypeVar("T")


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


# =============================================================================
# Enhanced LLM Call with Production Features
# =============================================================================

class EnhancedLLMService:
    """
    Enhanced LLM service with production-grade features:
    - Automatic retry with exponential backoff
    - Structured logging with correlation IDs
    - Prometheus metrics collection
    - LangSmith/LangFuse tracing
    - Response validation
    """

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_retries: int = 3,
        timeout_seconds: float = 60.0,
    ):
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds

        self._llm: Optional[BaseChatModel] = None
        self._tracer = get_tracer() if INFRASTRUCTURE_AVAILABLE else None

    @property
    def llm(self) -> BaseChatModel:
        """Lazy initialization of LLM instance."""
        if self._llm is None:
            self._llm = get_llm(
                provider=self.provider,
                model=self.model,
                temperature=self.temperature,
            )
        return self._llm

    def invoke(
        self,
        messages: list,
        agent_name: str = "unknown",
        prompt_version: str = "v1.0",
        correlation_id: Optional[str] = None,
        fallback: Optional[Callable[[], T]] = None,
    ) -> str:
        """
        Invoke the LLM with production features.

        Args:
            messages: List of messages (SystemMessage, HumanMessage)
            agent_name: Name of the calling agent (for metrics/tracing)
            prompt_version: Version of the prompt being used
            correlation_id: Optional correlation ID for request tracing
            fallback: Optional fallback function if all retries fail

        Returns:
            LLM response content string
        """
        # Set correlation ID for logging
        if INFRASTRUCTURE_AVAILABLE and correlation_id:
            set_correlation_id(correlation_id)

        start_time = time.time()
        model_name = self.model or self._detect_model_name()

        # Log start
        if logger:
            logger.info(
                "llm_invoke_started",
                agent=agent_name,
                model=model_name,
                prompt_version=prompt_version,
                message_count=len(messages),
            )

        try:
            # Invoke with retry logic
            response = self._invoke_with_retry(messages, agent_name)

            duration = time.time() - start_time

            # Record metrics
            if INFRASTRUCTURE_AVAILABLE:
                metrics.record_llm_call(
                    model=model_name,
                    success=True,
                    duration=duration,
                )

            # Record trace
            if self._tracer:
                self._tracer.trace_llm_call(
                    name=f"{agent_name}_llm_call",
                    input_data={"messages": [str(m)[:500] for m in messages]},
                    output_data={"content": response.content[:500] if response.content else ""},
                    metadata=TraceMetadata(
                        agent_name=agent_name,
                        model=model_name,
                        prompt_version=prompt_version,
                        latency_ms=duration * 1000,
                    ),
                )

            # Log success
            if logger:
                logger.info(
                    "llm_invoke_completed",
                    agent=agent_name,
                    model=model_name,
                    duration_ms=round(duration * 1000, 2),
                    response_length=len(response.content) if response.content else 0,
                )

            return response.content

        except Exception as e:
            duration = time.time() - start_time

            # Record failure metrics
            if INFRASTRUCTURE_AVAILABLE:
                metrics.record_llm_call(
                    model=model_name,
                    success=False,
                    duration=duration,
                )

            # Log error
            if logger:
                logger.error(
                    "llm_invoke_failed",
                    agent=agent_name,
                    model=model_name,
                    duration_ms=round(duration * 1000, 2),
                    error=str(e),
                    error_type=type(e).__name__,
                )

            # Use fallback if provided
            if fallback is not None:
                if logger:
                    logger.warning(
                        "llm_invoke_fallback",
                        agent=agent_name,
                        reason=str(e),
                    )
                if INFRASTRUCTURE_AVAILABLE:
                    llm_fallback.labels(agent_name=agent_name, reason=type(e).__name__).inc()
                return fallback()

            raise

    def _invoke_with_retry(self, messages: list, agent_name: str):
        """Invoke LLM with retry logic."""
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                return self.llm.invoke(messages)

            except Exception as e:
                last_exception = e

                # Check if we should retry
                if not self._should_retry(e):
                    raise

                if logger:
                    logger.warning(
                        "llm_retry_attempt",
                        agent=agent_name,
                        attempt=attempt + 1,
                        max_attempts=self.max_retries,
                        error=str(e),
                    )

                # Exponential backoff
                if attempt < self.max_retries - 1:
                    wait_time = min(2.0 ** attempt, 30.0)
                    time.sleep(wait_time)

        raise last_exception

    def _should_retry(self, exception: Exception) -> bool:
        """Determine if an exception should trigger a retry."""
        # Retry on network/timeout errors
        retry_exceptions = (
            ConnectionError,
            TimeoutError,
            OSError,
        )

        # Check for rate limit errors (common in LLM APIs)
        error_msg = str(exception).lower()
        if "rate limit" in error_msg or "429" in error_msg:
            return True

        if "timeout" in error_msg or "connection" in error_msg:
            return True

        return isinstance(exception, retry_exceptions)

    def _detect_model_name(self) -> str:
        """Detect the model name from the LLM instance."""
        if hasattr(self.llm, 'model_name'):
            return self.llm.model_name
        if hasattr(self.llm, 'model'):
            return self.llm.model
        return "unknown"


def invoke_llm_with_tracing(
    messages: list,
    agent_name: str,
    prompt_version: str = "v1.0",
    temperature: float = 0.3,
    fallback: Optional[Callable[[], str]] = None,
) -> str:
    """
    Convenience function to invoke LLM with full production features.

    Args:
        messages: List of LangChain messages
        agent_name: Name of the calling agent
        prompt_version: Version identifier for the prompt
        temperature: Sampling temperature
        fallback: Optional fallback function

    Returns:
        LLM response content
    """
    service = EnhancedLLMService(temperature=temperature)
    return service.invoke(
        messages=messages,
        agent_name=agent_name,
        prompt_version=prompt_version,
        fallback=fallback,
    )
