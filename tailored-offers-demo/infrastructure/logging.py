"""
Structured Logging Module

Provides structured logging with correlation IDs for request tracing.
Uses structlog for JSON-formatted, context-aware logging.
"""

import os
import sys
import uuid
import logging
from typing import Optional, Any, Dict
from contextvars import ContextVar
from functools import wraps
from datetime import datetime

# Try to import structlog, fall back to standard logging if not available
try:
    import structlog
    STRUCTLOG_AVAILABLE = True
except ImportError:
    STRUCTLOG_AVAILABLE = False
    print("Warning: structlog not installed. Using standard logging. Install with: pip install structlog")

# Context variable for correlation ID (thread-safe)
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    """Get the current correlation ID from context."""
    return correlation_id_var.get() or str(uuid.uuid4())[:8]


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """Set a correlation ID in the current context."""
    cid = correlation_id or str(uuid.uuid4())[:8]
    correlation_id_var.set(cid)
    return cid


def configure_logging(
    log_level: str = "INFO",
    json_format: bool = True,
    log_file: Optional[str] = None,
) -> None:
    """
    Configure structured logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        json_format: If True, output JSON format; otherwise, console format
        log_file: Optional file path for logging output
    """
    if not STRUCTLOG_AVAILABLE:
        # Fallback to standard logging
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            handlers=[
                logging.StreamHandler(sys.stdout),
                *([logging.FileHandler(log_file)] if log_file else []),
            ]
        )
        return

    # Configure structlog processors
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        _add_correlation_id,
        _add_service_info,
    ]

    if json_format:
        # JSON format for production
        processors = shared_processors + [
            structlog.processors.JSONRenderer()
        ]
    else:
        # Console format for development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True)
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def _add_correlation_id(logger, method_name, event_dict):
    """Add correlation ID to all log entries."""
    event_dict["correlation_id"] = get_correlation_id()
    return event_dict


def _add_service_info(logger, method_name, event_dict):
    """Add service information to log entries."""
    event_dict["service"] = "tailored-offers"
    event_dict["environment"] = os.getenv("ENVIRONMENT", "development")
    return event_dict


def get_logger(name: str = "tailored_offers") -> Any:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (typically module name)

    Returns:
        Structured logger instance
    """
    if STRUCTLOG_AVAILABLE:
        return structlog.get_logger(name)
    else:
        return logging.getLogger(name)


class LogContext:
    """Context manager for adding temporary logging context."""

    def __init__(self, **context):
        self.context = context
        self._tokens = []

    def __enter__(self):
        if STRUCTLOG_AVAILABLE:
            for key, value in self.context.items():
                token = structlog.contextvars.bind_contextvars(**{key: value})
                self._tokens.append((key, token))
        return self

    def __exit__(self, *args):
        if STRUCTLOG_AVAILABLE:
            structlog.contextvars.clear_contextvars()


def log_agent_execution(agent_name: str):
    """Decorator to log agent execution with timing."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger(agent_name)
            start_time = datetime.now()

            logger.info(
                "agent_execution_started",
                agent=agent_name,
            )

            try:
                result = func(*args, **kwargs)
                duration_ms = (datetime.now() - start_time).total_seconds() * 1000

                logger.info(
                    "agent_execution_completed",
                    agent=agent_name,
                    duration_ms=round(duration_ms, 2),
                    success=True,
                )
                return result

            except Exception as e:
                duration_ms = (datetime.now() - start_time).total_seconds() * 1000
                logger.error(
                    "agent_execution_failed",
                    agent=agent_name,
                    duration_ms=round(duration_ms, 2),
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise

        return wrapper
    return decorator


def log_llm_call(func):
    """Decorator to log LLM calls with token tracking."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_logger("llm_service")
        start_time = datetime.now()

        # Extract relevant info from kwargs or args
        model = kwargs.get("model", "unknown")
        temperature = kwargs.get("temperature", 0.7)

        logger.info(
            "llm_call_started",
            model=model,
            temperature=temperature,
        )

        try:
            result = func(*args, **kwargs)
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000

            logger.info(
                "llm_call_completed",
                model=model,
                duration_ms=round(duration_ms, 2),
                success=True,
            )
            return result

        except Exception as e:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(
                "llm_call_failed",
                model=model,
                duration_ms=round(duration_ms, 2),
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    return wrapper


def log_mcp_call(tool_name: str):
    """Decorator to log MCP tool calls."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            logger = get_logger("mcp_client")
            start_time = datetime.now()

            logger.info(
                "mcp_call_started",
                tool=tool_name,
            )

            try:
                result = await func(*args, **kwargs)
                duration_ms = (datetime.now() - start_time).total_seconds() * 1000

                logger.info(
                    "mcp_call_completed",
                    tool=tool_name,
                    duration_ms=round(duration_ms, 2),
                    success=True,
                    has_result=result is not None,
                )
                return result

            except Exception as e:
                duration_ms = (datetime.now() - start_time).total_seconds() * 1000
                logger.error(
                    "mcp_call_failed",
                    tool=tool_name,
                    duration_ms=round(duration_ms, 2),
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise

        return wrapper
    return decorator
