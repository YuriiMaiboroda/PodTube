from __future__ import annotations

import logging
import re

from utils.logging.delayed_log_emitter import DelayedLogEmitter
from utils.logging.log_events import LogEvent
from utils.logging.log_handlers import LogHandler


class YtdlpProgressHandler(LogHandler):
    _progress_re = re.compile(
        r"""
        ^\s*(?:\[[^\]]*\]\s*)*
        (?P<percent>\d{1,3}(?:\.\d+)?)%\s+of\s+
        (?P<size>.+?)\s+at\s+
        (?P<speed>.+?)\s+ETA\s+
        (?P<eta>\S+)
        """,
        re.VERBOSE,
    )

    def __init__(self, logger, *, interval: float = 1.0, enabled: bool = True):
        self.logger = logger
        self.enabled = enabled
        self._seen_100_percent = False

        self._emitter = DelayedLogEmitter(
            interval=interval,
            emit_callback=lambda message, level: self.logger.log(level, message),
        )

    def handle(self, event: LogEvent) -> bool:
        if not self.enabled:
            return False

        match = self._progress_re.match(event.message)
        if not match:
            return False

        percent = float(match.group("percent"))

        force = False
        if percent >= 100.0 and not self._seen_100_percent:
            self._seen_100_percent = True
            force = True

        self._emitter.submit(event.message, log_level=event.level, force=force)
        return True

    def close(self) -> None:
        self._emitter.close()