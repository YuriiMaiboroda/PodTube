from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class LogEvent:
    level: int
    message: str
