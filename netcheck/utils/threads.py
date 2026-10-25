import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any


class DaemonThreadPoolExecutor(ThreadPoolExecutor):
    """
    ThreadPoolExecutor that spawns daemon worker threads and cleanly shuts down
    immediately without blocking on KeyboardInterrupt or unhandled exceptions.

    Standard ThreadPoolExecutor joins non-daemon worker threads upon exiting the
    `with` context manager and during interpreter shutdown (_python_exit / threading._shutdown).
    When workers are blocked in network sockets (TCP connect, DNS resolution),
    this causes the process to hang on Ctrl+C, requiring multiple SIGINTs and
    dumping unhandled KeyboardInterrupt tracebacks from threading._shutdown.

    DaemonThreadPoolExecutor resolves this by:
    1. Creating workers with `daemon=True` so Python's threading._shutdown does not block.
    2. Detaching workers from concurrent.futures.thread._threads_queues so _python_exit does not block.
    3. Exiting context manager immediately (wait=False) when an exception occurs.
    """

    def _adjust_thread_count(self) -> None:
        orig_thread = threading.Thread

        def _daemon_thread(*args: Any, **kwargs: Any) -> threading.Thread:
            kwargs["daemon"] = True
            return orig_thread(*args, **kwargs)

        threading.Thread = _daemon_thread
        try:
            super()._adjust_thread_count()
        finally:
            threading.Thread = orig_thread

        try:
            import concurrent.futures.thread as cft
            for t in list(self._threads):
                cft._threads_queues.pop(t, None)
        except Exception:
            pass

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        if exc_type is not None:
            try:
                self.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                self.shutdown(wait=False)
            return False
        return super().__exit__(exc_type, exc_val, exc_tb)


def cleanup_thread_queues() -> None:
    """Safely clear concurrent.futures worker queues to prevent interpreter shutdown hangs."""
    try:
        import concurrent.futures.thread as cft
        cft._threads_queues.clear()
    except Exception:
        pass
