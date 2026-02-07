"""
Unified retry handler for all agents.
Provides consistent error handling and automatic retries with exponential backoff.
"""
import asyncio
from functools import wraps
from typing import Callable, Any, TypeVar, ParamSpec
from logging import getLogger

logger = getLogger(__name__)

P = ParamSpec('P')
T = TypeVar('T')


class RetryConfig:
    """Configuration for retry behavior"""
    
    def __init__(
        self, 
        max_retries: int = 1, 
        retry_delay: float = 2.0, 
        backoff_factor: float = 2.0,
        retry_on_rate_limit: bool = True,
        retry_on_timeout: bool = True
    ):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.backoff_factor = backoff_factor
        self.retry_on_rate_limit = retry_on_rate_limit
        self.retry_on_timeout = retry_on_timeout


def with_retry(config: RetryConfig = None):
    """
    Decorator for automatic retry with exponential backoff.
    
    Args:
        config: RetryConfig instance. If None, uses default configuration.
    
    Example:
        @with_retry(RetryConfig(max_retries=3, retry_delay=1.0))
        async def my_function():
            # Your code here
            pass
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            delay = config.retry_delay
            last_error = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    error_str = str(e).lower()
                    
                    # Determine if error is retryable
                    is_rate_limit = config.retry_on_rate_limit and (
                        "429" in str(e) or "resource_exhausted" in error_str
                    )
                    is_timeout = config.retry_on_timeout and (
                        "timeout" in error_str or "timed out" in error_str
                    )
                    
                    should_retry = is_rate_limit or is_timeout
                    
                    if attempt < config.max_retries and should_retry:
                        retry_reason = "rate limit" if is_rate_limit else "timeout"
                        logger.warning(
                            f"{func.__name__}: {retry_reason} detected, "
                            f"retry {attempt + 1}/{config.max_retries} after {delay}s"
                        )
                        await asyncio.sleep(delay)
                        delay *= config.backoff_factor
                        continue
                    
                    # Not retryable or out of retries
                    raise
            
            # Should never reach here, but just in case
            raise last_error
        
        return wrapper
    return decorator


async def retry_async_call(
    func: Callable[..., T],
    *args,
    max_retries: int = 1,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    **kwargs
) -> T:
    """
    Utility function to retry an async function call without using a decorator.
    
    Args:
        func: Async function to retry
        *args: Positional arguments for func
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds before first retry
        backoff_factor: Multiplier for delay on each retry
        **kwargs: Keyword arguments for func
    
    Returns:
        Result of the function call
    
    Raises:
        Last exception if all retries fail
    
    Example:
        result = await retry_async_call(
            my_agent.run, 
            user_id="123", 
            state={},
            max_retries=3
        )
    """
    delay = initial_delay
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            error_str = str(e).lower()
            
            # Check if it's a retryable error
            is_rate_limit = "429" in str(e) or "resource_exhausted" in error_str
            is_timeout = "timeout" in error_str
            
            if attempt < max_retries and (is_rate_limit or is_timeout):
                retry_reason = "rate limit" if is_rate_limit else "timeout"
                logger.warning(
                    f"{func.__name__}: {retry_reason} hit, "
                    f"retrying in {delay}s... (attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(delay)
                delay *= backoff_factor
                continue
            
            # Not retryable or out of retries
            raise
    
    # If we've exhausted all retries
    raise last_exception
