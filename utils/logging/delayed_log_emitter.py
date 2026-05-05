from __future__ import annotations

import contextvars
from dataclasses import dataclass
import logging
import threading
from collections.abc import Callable

@dataclass(slots=True)
class PendingLogMessage:
    message: str
    log_level: int
    context: contextvars.Context

class DelayedLogEmitter:
    """
    Delays repeated log output by keeping only the latest pending message.
    """

    def __init__(
        self,
        interval: float,
        emit_callback: Callable[[str, int], None],
    ):
        self.interval = interval
        self.emit_callback = emit_callback

        self._timer: threading.Timer | None = None
        self._pending: PendingLogMessage | None = None
        self._closed = False
        self._lock = threading.RLock()

    def submit(self, message: str, *, log_level: int = logging.INFO, force: bool = False) -> None:
        with self._lock:
            if self._closed:
                self.emit_callback(message, log_level)
                return

            self._pending = PendingLogMessage(
                message=message,
                log_level=log_level,
                context=contextvars.copy_context(),
            )

            if force or self._timer is None:
                self.flush(restart_timer=not force)

    def flush(self, *, restart_timer: bool = False) -> None:
        with self._lock:
            self._cancel_timer_locked()
            self._submit_pending_message_locked()

            if restart_timer and not self._closed:
                self._start_timer_locked()

    def _cancel_timer_locked(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _submit_pending_message_locked(self) -> None:
        if self._pending is not None:
            pending = self._pending
            self._pending = None
            pending.context.run(self.emit_callback, pending.message, pending.log_level)

    def _start_timer_locked(self) -> None:

        self._timer = threading.Timer(
            self.interval,
            self._on_timer,
        )
        self._timer.daemon = True
        self._timer.start()

    def _on_timer(self) -> None:
        try:
            with self._lock:
                has_pending = self._pending is not None
                self.flush(restart_timer=has_pending)
        except Exception:
            with self._lock:
                self._cancel_timer_locked()
            raise

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self.flush(restart_timer=False)
