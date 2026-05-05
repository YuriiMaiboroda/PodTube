from utils.logging.common import LoggerType
from utils.logging.log_events import LogEvent
from utils.logging.log_handlers import FallbackLogHandler, LogHandler


import contextlib
import logging
from typing import Self


class ProcessingLogger(contextlib.AbstractContextManager):
    """
    Generic logger that passes LogEvent objects through a handlers.

    The first handler that returns True stops further processing.
    Pending handler state is flushed on close / context exit.
    """

    def __init__(
        self,
        logger: LoggerType,
        *handlers: LogHandler,
        add_fallback: bool = True,
    ):
        self.logger = logger
        self._closed = False
        self.handlers = list(handlers)

        if add_fallback:
            self.handlers.append(FallbackLogHandler(logger))

    def handle(self, event: LogEvent) -> None:
        if self._closed:
            self.logger.log(event.level, event.message)
            return

        for handler in self.handlers:
            if handler.handle(event):
                return

    def log(self, level: int, message: str) -> None:
        self.handle(LogEvent(level=level, message=message))

    def debug(self, message: str) -> None:
        self.log(logging.DEBUG, message)

    def info(self, message: str) -> None:
        self.log(logging.INFO, message)

    def warning(self, message: str) -> None:
        self.log(logging.WARNING, message)

    def error(self, message: str) -> None:
        self.log(logging.ERROR, message)

    def close(self) -> None:
        if self._closed:
            return

        self._closed = True

        for handler in self.handlers:
            handler.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args, **kwargs) -> None:
        self.close()