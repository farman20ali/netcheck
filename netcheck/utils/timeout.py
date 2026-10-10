import atexit
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Any, Callable, TypeVar

T = TypeVar('T')

# Global ThreadPoolExecutor for executing operations within timeout boundaries
_timeout_executor = ThreadPoolExecutor(max_workers=200, thread_name_prefix="timeout_runner")

# Register cleanup on exit
def _cleanup_executor():
    _timeout_executor.shutdown(wait=False)

atexit.register(_cleanup_executor)

def run_with_timeout(timeout: float, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """
    Executes func(*args, **kwargs) in a background thread and waits up to `timeout` seconds.
    Raises concurrent.futures.TimeoutError if the timeout is exceeded.
    """
    if timeout is None or timeout <= 0:
        return func(*args, **kwargs)

    future = _timeout_executor.submit(func, *args, **kwargs)
    try:
        return future.result(timeout=timeout)
    except TimeoutError:
        # Note: The background thread will continue to run until it completes,
        # but control is returned to the caller immediately.
        raise TimeoutError(f"Operation timed out after {timeout} seconds")

