from __future__ import annotations

from abc import ABC, abstractmethod
from utils.logging.common import LoggerType
from utils.logging.log_events import LogEvent


class LogHandler(ABC):
    @abstractmethod
    def handle(self, event: LogEvent) -> bool:
        """
        Return True if the message was handled and should not be passed
        to the next handler.
        """
        raise NotImplementedError

    def close(self) -> None:
        """
        Flush pending messages or release resources.
        """
        pass


class FallbackLogHandler(LogHandler):
    def __init__(self, logger: LoggerType):
        self.logger = logger

    def handle(self, event: LogEvent) -> bool:
        self.logger.log(event.level, event.message)
        return True
