"""
Retry Logic Module

Provides retry decorators and utilities using tenacity for:
- LLM API calls with exponential backoff
- MCP tool calls with circuit breaker pattern
- Generic retries with fallback support
"""

import os
import asyncio
from typing import Optional, Callable, TypeVar, Any, Union
from functools import wraps
from dataclasses import dataclass, field

# Try to import tenacity, fall back to simple retry if not available
try:
    from tenacity import (
        retry,
        stop_after_attempt,
        stop_after_delay,
        wait_exponential,
        wait_random_exponential,
        retry_if_exception_type,
        retry_if_not_exception_type,
        before_sleep_log,
        after_log,
        RetryError,
    )
    TENACITY_AVAILABLE = True
except ImportError:
    TENACITY_AVAILABLE = False
    print("Warning: tenacity not installed. Retry logic disabled. Install with: pip install tenacity")

# Try to import pybreaker for circuit breaker
try:
    import pybreaker
    PYBREAKER_AVAILABLE = True
except ImportError:
    PYBREAKER_AVAILABLE = False

from .logging import get_logger

logger = get_logger("retry")

# Type variable for generic functions
T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    min_wait_seconds: float = 1.0
    max_wait_seconds: float = 30.0
    exponential_base: float = 2.0
    timeout_seconds: Optional[float] = 60.0

    # Exception types to retry on
    retry_on: tuple = field(default_factory=lambda: (
        ConnectionError,
        TimeoutError,
        OSError,
    ))

    # Exception types to NOT retry on (fail immediately)
    no_retry_on: tuple = field(default_factory=lambda: (
        ValueError,
        TypeError,
        KeyError,
    ))


# Default configurations
LLM_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    min_wait_seconds=2.0,
    max_wait_seconds=30.0,
    timeout_seconds=60.0,
)

MCP_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    min_wait_seconds=1.0,
    max_wait_seconds=10.0,
    timeout_seconds=30.0,
)


def _create_retry_decorator(config: RetryConfig):
    """Create a tenacity retry decorator from config."""
    if not TENACITY_AVAILABLE:
        # Return no-op decorator if tenacity not available
        def no_op_decorator(func):
            return func
        return no_op_decorator

    return retry(
        stop=(
            stop_after_attempt(config.max_attempts) |
            (stop_after_delay(config.timeout_seconds) if config.timeout_seconds else stop_after_attempt(100))
        ),
        wait=wait_exponential(
            multiplier=config.exponential_base,
            min=config.min_wait_seconds,
            max=config.max_wait_seconds,
        ),
        retry=retry_if_exception_type(config.retry_on),
        before_sleep=_log_retry_attempt,
        reraise=True,
    )


def _log_retry_attempt(retry_state):
    """Log retry attempts."""
    logger.warning(
        "retry_attempt",
        attempt=retry_state.attempt_number,
        wait_seconds=retry_state.next_action.sleep if retry_state.next_action else 0,
        exception=str(retry_state.outcome.exception()) if retry_state.outcome else None,
    )


def retry_llm_call(
    max_attempts: int = 3,
    timeout_seconds: float = 60.0,
    fallback: Optional[Callable[[], T]] = None,
):
    """
    Decorator for retrying LLM API calls with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        timeout_seconds: Maximum total time for all retries
        fallback: Optional fallback function to call if all retries fail

    Example:
        @retry_llm_call(max_attempts=3, fallback=lambda: default_response)
        def call_openai(prompt: str) -> str:
            return openai.complete(prompt)
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        min_wait_seconds=2.0,
        max_wait_seconds=30.0,
        timeout_seconds=timeout_seconds,
    )

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # Add tenacity retry
        retrying_func = _create_retry_decorator(config)(func)

        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            try:
                return retrying_func(*args, **kwargs)
            except Exception as e:
                if fallback is not None:
                    logger.warning(
                        "llm_call_fallback",
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    return fallback()
                raise

        return wrapper

    return decorator


def retry_llm_call_async(
    max_attempts: int = 3,
    timeout_seconds: float = 60.0,
    fallback: Optional[Callable[[], T]] = None,
):
    """
    Async version of retry_llm_call decorator.

    Example:
        @retry_llm_call_async(max_attempts=3)
        async def call_openai_async(prompt: str) -> str:
            return await openai.acomplete(prompt)
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        min_wait_seconds=2.0,
        max_wait_seconds=30.0,
        timeout_seconds=timeout_seconds,
    )

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(config.max_attempts):
                try:
                    # Apply timeout to each attempt
                    return await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=config.timeout_seconds / config.max_attempts if config.timeout_seconds else None
                    )
                except asyncio.TimeoutError as e:
                    last_exception = e
                    logger.warning(
                        "async_retry_timeout",
                        attempt=attempt + 1,
                        max_attempts=config.max_attempts,
                    )
                except Exception as e:
                    last_exception = e
                    if not isinstance(e, config.retry_on):
                        raise

                    logger.warning(
                        "async_retry_attempt",
                        attempt=attempt + 1,
                        max_attempts=config.max_attempts,
                        error=str(e),
                    )

                # Wait before retry (exponential backoff)
                if attempt < config.max_attempts - 1:
                    wait_time = min(
                        config.min_wait_seconds * (config.exponential_base ** attempt),
                        config.max_wait_seconds
                    )
                    await asyncio.sleep(wait_time)

            # All retries failed
            if fallback is not None:
                logger.warning(
                    "async_llm_call_fallback",
                    error=str(last_exception),
                )
                return fallback()

            raise last_exception

        return wrapper

    return decorator


def retry_mcp_call(
    max_attempts: int = 3,
    timeout_seconds: float = 30.0,
):
    """
    Decorator for retrying MCP tool calls with circuit breaker pattern.

    Args:
        max_attempts: Maximum number of retry attempts
        timeout_seconds: Maximum time for all retries

    Example:
        @retry_mcp_call(max_attempts=3)
        async def get_customer_data(customer_id: str) -> dict:
            return await mcp_client.get_customer(customer_id)
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        min_wait_seconds=0.5,
        max_wait_seconds=5.0,
        timeout_seconds=timeout_seconds,
    )

    # Create circuit breaker if pybreaker is available
    breaker = None
    if PYBREAKER_AVAILABLE:
        breaker = pybreaker.CircuitBreaker(
            fail_max=5,  # Open circuit after 5 failures
            reset_timeout=30,  # Try again after 30 seconds
        )

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(config.max_attempts):
                try:
                    # Check circuit breaker
                    if breaker and breaker.current_state == "open":
                        logger.warning(
                            "circuit_breaker_open",
                            function=func.__name__,
                        )
                        raise ConnectionError("Circuit breaker is open")

                    # Apply timeout
                    result = await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=config.timeout_seconds / config.max_attempts if config.timeout_seconds else None
                    )

                    # Record success with circuit breaker
                    if breaker:
                        breaker.success()

                    return result

                except asyncio.TimeoutError as e:
                    last_exception = e
                    if breaker:
                        breaker.failure()
                    logger.warning(
                        "mcp_retry_timeout",
                        attempt=attempt + 1,
                        function=func.__name__,
                    )

                except Exception as e:
                    last_exception = e
                    if breaker:
                        breaker.failure()

                    logger.warning(
                        "mcp_retry_attempt",
                        attempt=attempt + 1,
                        function=func.__name__,
                        error=str(e),
                    )

                # Wait before retry
                if attempt < config.max_attempts - 1:
                    wait_time = min(
                        config.min_wait_seconds * (config.exponential_base ** attempt),
                        config.max_wait_seconds
                    )
                    await asyncio.sleep(wait_time)

            raise last_exception

        return wrapper

    return decorator


def retry_with_fallback(
    fallback_func: Callable[..., T],
    max_attempts: int = 3,
    log_fallback: bool = True,
):
    """
    Decorator that retries a function and falls back to another on failure.

    Args:
        fallback_func: Function to call if primary fails
        max_attempts: Maximum retry attempts for primary
        log_fallback: Whether to log when falling back

    Example:
        def rules_based_decision(context):
            return {"offer": "MCE", "price": 39}

        @retry_with_fallback(rules_based_decision)
        def llm_decision(context):
            return llm.invoke(context)
    """
    config = RetryConfig(max_attempts=max_attempts)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        retrying_func = _create_retry_decorator(config)(func) if TENACITY_AVAILABLE else func

        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            try:
                return retrying_func(*args, **kwargs)
            except Exception as e:
                if log_fallback:
                    logger.warning(
                        "fallback_triggered",
                        primary_function=func.__name__,
                        fallback_function=fallback_func.__name__,
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                return fallback_func(*args, **kwargs)

        return wrapper

    return decorator


class RetryContext:
    """
    Context manager for retry logic with manual control.

    Example:
        async with RetryContext(max_attempts=3) as ctx:
            while ctx.should_retry():
                try:
                    result = await risky_operation()
                    break
                except Exception as e:
                    ctx.record_failure(e)
    """

    def __init__(self, max_attempts: int = 3, timeout_seconds: Optional[float] = None):
        self.max_attempts = max_attempts
        self.timeout_seconds = timeout_seconds
        self.attempt = 0
        self.last_exception: Optional[Exception] = None
        self._start_time: Optional[float] = None

    def __enter__(self):
        import time
        self._start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    async def __aenter__(self):
        import time
        self._start_time = time.time()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def should_retry(self) -> bool:
        """Check if another retry attempt should be made."""
        import time

        if self.attempt >= self.max_attempts:
            return False

        if self.timeout_seconds and self._start_time:
            elapsed = time.time() - self._start_time
            if elapsed >= self.timeout_seconds:
                return False

        return True

    def record_failure(self, exception: Exception):
        """Record a failure and prepare for next attempt."""
        self.attempt += 1
        self.last_exception = exception

        logger.warning(
            "retry_context_failure",
            attempt=self.attempt,
            max_attempts=self.max_attempts,
            error=str(exception),
        )

    def get_backoff_time(self) -> float:
        """Get the backoff time for the next retry."""
        return min(2.0 ** self.attempt, 30.0)
