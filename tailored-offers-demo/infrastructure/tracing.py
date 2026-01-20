"""
LLM Tracing Module

Provides integration with LangSmith and LangFuse for:
- LLM call tracing and observability
- Prompt evaluation tracking
- Cost and latency monitoring
- A/B testing of prompts
"""

import os
import time
import uuid
from typing import Optional, Dict, Any, Callable, List
from functools import wraps
from dataclasses import dataclass, field
from datetime import datetime
from contextlib import contextmanager

from .logging import get_logger, get_correlation_id

logger = get_logger("tracing")

# Try to import LangSmith
try:
    from langsmith import Client as LangSmithClient
    from langsmith.run_trees import RunTree
    from langsmith import traceable
    LANGSMITH_AVAILABLE = True
except ImportError:
    LANGSMITH_AVAILABLE = False
    traceable = lambda *args, **kwargs: lambda f: f  # No-op decorator

# Try to import LangFuse
try:
    from langfuse import Langfuse
    from langfuse.decorators import observe, langfuse_context
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    observe = lambda *args, **kwargs: lambda f: f  # No-op decorator


@dataclass
class TraceMetadata:
    """Metadata for a trace span."""
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    span_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    parent_span_id: Optional[str] = None
    correlation_id: str = field(default_factory=get_correlation_id)

    agent_name: Optional[str] = None
    model: Optional[str] = None
    prompt_version: Optional[str] = None

    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0

    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class TracingManager:
    """
    Centralized tracing manager for LLM observability.

    Supports both LangSmith and LangFuse, with automatic fallback
    to local logging if neither is configured.
    """

    def __init__(self):
        self.langsmith_client: Optional[LangSmithClient] = None
        self.langfuse_client: Optional[Langfuse] = None
        self.project_name = os.getenv("LANGSMITH_PROJECT", "tailored-offers")

        self._init_clients()

    def _init_clients(self):
        """Initialize tracing clients based on available API keys."""
        # Try LangSmith first
        if LANGSMITH_AVAILABLE and os.getenv("LANGSMITH_API_KEY"):
            try:
                self.langsmith_client = LangSmithClient()
                logger.info(
                    "tracing_initialized",
                    provider="langsmith",
                    project=self.project_name,
                )
            except Exception as e:
                logger.warning(
                    "langsmith_init_failed",
                    error=str(e),
                )

        # Try LangFuse as alternative/supplement
        if LANGFUSE_AVAILABLE and os.getenv("LANGFUSE_SECRET_KEY"):
            try:
                self.langfuse_client = Langfuse()
                logger.info(
                    "tracing_initialized",
                    provider="langfuse",
                )
            except Exception as e:
                logger.warning(
                    "langfuse_init_failed",
                    error=str(e),
                )

        if not self.langsmith_client and not self.langfuse_client:
            logger.info(
                "tracing_disabled",
                reason="No API keys configured. Set LANGSMITH_API_KEY or LANGFUSE_SECRET_KEY",
            )

    @property
    def is_enabled(self) -> bool:
        """Check if any tracing is enabled."""
        return bool(self.langsmith_client or self.langfuse_client)

    def trace_llm_call(
        self,
        name: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        metadata: Optional[TraceMetadata] = None,
    ):
        """
        Record an LLM call trace.

        Args:
            name: Name of the operation (e.g., "offer_orchestration_reasoning")
            input_data: Input to the LLM (prompt, messages, etc.)
            output_data: Output from the LLM (response, parsed data, etc.)
            metadata: Optional trace metadata
        """
        if not self.is_enabled:
            return

        metadata = metadata or TraceMetadata()

        try:
            if self.langsmith_client:
                self._trace_langsmith(name, input_data, output_data, metadata)

            if self.langfuse_client:
                self._trace_langfuse(name, input_data, output_data, metadata)

        except Exception as e:
            logger.warning(
                "trace_recording_failed",
                name=name,
                error=str(e),
            )

    def _trace_langsmith(
        self,
        name: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        metadata: TraceMetadata,
    ):
        """Record trace to LangSmith."""
        run = self.langsmith_client.create_run(
            name=name,
            run_type="llm",
            project_name=self.project_name,
            inputs=input_data,
            outputs=output_data,
            extra={
                "metadata": {
                    "correlation_id": metadata.correlation_id,
                    "agent_name": metadata.agent_name,
                    "model": metadata.model,
                    "prompt_version": metadata.prompt_version,
                    "latency_ms": metadata.latency_ms,
                    "input_tokens": metadata.input_tokens,
                    "output_tokens": metadata.output_tokens,
                    **metadata.metadata,
                },
                "tags": list(metadata.tags.values()) if metadata.tags else [],
            },
        )

    def _trace_langfuse(
        self,
        name: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        metadata: TraceMetadata,
    ):
        """Record trace to LangFuse."""
        trace = self.langfuse_client.trace(
            name=name,
            input=input_data,
            output=output_data,
            metadata={
                "correlation_id": metadata.correlation_id,
                "agent_name": metadata.agent_name,
                "prompt_version": metadata.prompt_version,
                **metadata.metadata,
            },
            tags=list(metadata.tags.values()) if metadata.tags else [],
        )

        # Add generation span for token/cost tracking
        trace.generation(
            name=f"{name}_generation",
            model=metadata.model,
            input=input_data.get("messages", input_data),
            output=output_data.get("content", output_data),
            usage={
                "input": metadata.input_tokens,
                "output": metadata.output_tokens,
            },
            metadata={
                "latency_ms": metadata.latency_ms,
                "cost_usd": metadata.cost_usd,
            },
        )

    def create_evaluation(
        self,
        name: str,
        trace_id: str,
        score: float,
        comment: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Create an evaluation score for a trace.

        Used for tracking prompt quality and A/B testing.
        """
        if not self.is_enabled:
            return

        try:
            if self.langfuse_client:
                self.langfuse_client.score(
                    trace_id=trace_id,
                    name=name,
                    value=score,
                    comment=comment,
                    metadata=metadata,
                )

            logger.info(
                "evaluation_recorded",
                name=name,
                trace_id=trace_id,
                score=score,
            )

        except Exception as e:
            logger.warning(
                "evaluation_recording_failed",
                name=name,
                error=str(e),
            )

    def flush(self):
        """Flush any pending traces."""
        if self.langfuse_client:
            try:
                self.langfuse_client.flush()
            except Exception as e:
                logger.warning("langfuse_flush_failed", error=str(e))


# Global tracer instance
_tracer: Optional[TracingManager] = None


def get_tracer() -> TracingManager:
    """Get the global tracing manager instance."""
    global _tracer
    if _tracer is None:
        _tracer = TracingManager()
    return _tracer


def trace_agent(agent_name: str, prompt_version: Optional[str] = None):
    """
    Decorator to trace agent execution.

    Args:
        agent_name: Name of the agent being traced
        prompt_version: Optional version identifier for the prompt

    Example:
        @trace_agent("offer_orchestration", prompt_version="v1.2")
        def analyze(self, state):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer()
            metadata = TraceMetadata(
                agent_name=agent_name,
                prompt_version=prompt_version,
            )

            start_time = time.time()

            # Capture input
            input_data = {
                "agent": agent_name,
                "args": str(args[1:]) if len(args) > 1 else None,  # Skip self
                "kwargs": {k: str(v)[:500] for k, v in kwargs.items()},
            }

            try:
                result = func(*args, **kwargs)

                metadata.latency_ms = (time.time() - start_time) * 1000

                # Capture output (truncated for large responses)
                output_data = {
                    "success": True,
                    "result_keys": list(result.keys()) if isinstance(result, dict) else None,
                    "selected_offer": result.get("selected_offer") if isinstance(result, dict) else None,
                }

                tracer.trace_llm_call(
                    name=f"agent_{agent_name}",
                    input_data=input_data,
                    output_data=output_data,
                    metadata=metadata,
                )

                return result

            except Exception as e:
                metadata.latency_ms = (time.time() - start_time) * 1000

                tracer.trace_llm_call(
                    name=f"agent_{agent_name}",
                    input_data=input_data,
                    output_data={
                        "success": False,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                    metadata=metadata,
                )
                raise

        return wrapper

    return decorator


def trace_llm_call(
    name: str,
    model: Optional[str] = None,
    prompt_version: Optional[str] = None,
):
    """
    Decorator to trace individual LLM API calls.

    Args:
        name: Name for this LLM call
        model: Model being used
        prompt_version: Version of the prompt

    Example:
        @trace_llm_call("orchestration_reasoning", model="gpt-4", prompt_version="v1.0")
        def _llm_reasoning(self, context):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer()
            metadata = TraceMetadata(
                model=model,
                prompt_version=prompt_version,
            )

            start_time = time.time()

            try:
                result = func(*args, **kwargs)

                metadata.latency_ms = (time.time() - start_time) * 1000

                tracer.trace_llm_call(
                    name=name,
                    input_data={"function": func.__name__},
                    output_data={"success": True},
                    metadata=metadata,
                )

                return result

            except Exception as e:
                metadata.latency_ms = (time.time() - start_time) * 1000

                tracer.trace_llm_call(
                    name=name,
                    input_data={"function": func.__name__},
                    output_data={"success": False, "error": str(e)},
                    metadata=metadata,
                )
                raise

        return wrapper

    return decorator


@contextmanager
def trace_span(name: str, metadata: Optional[Dict[str, Any]] = None):
    """
    Context manager for tracing a block of code.

    Example:
        with trace_span("data_enrichment", {"pnr": "ABC123"}):
            data = load_enriched_data(pnr)
    """
    tracer = get_tracer()
    trace_meta = TraceMetadata(metadata=metadata or {})
    start_time = time.time()

    try:
        yield trace_meta

        trace_meta.latency_ms = (time.time() - start_time) * 1000
        tracer.trace_llm_call(
            name=name,
            input_data=metadata or {},
            output_data={"success": True},
            metadata=trace_meta,
        )

    except Exception as e:
        trace_meta.latency_ms = (time.time() - start_time) * 1000
        tracer.trace_llm_call(
            name=name,
            input_data=metadata or {},
            output_data={"success": False, "error": str(e)},
            metadata=trace_meta,
        )
        raise
