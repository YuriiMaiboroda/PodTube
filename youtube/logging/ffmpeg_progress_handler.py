from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass

from utils.logging.common import LoggerType
from utils.logging.delayed_log_emitter import DelayedLogEmitter
from utils.logging.log_events import LogEvent
from utils.logging.log_handlers import LogHandler
from youtube.utils.patch_ytdlp import AppNames

FFMPEG_DURATION_RE = re.compile(
    r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)"
)

FFMPEG_LOG_RE = re.compile(rf"^(.*\[{AppNames.FFMPEG}\]\s*)(.*)$")


def parse_ffmpeg_duration(line: str) -> float | None:
    match = FFMPEG_DURATION_RE.search(line)
    if not match:
        return None

    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def parse_ffmpeg_time(value: str) -> float | None:
    if not value:
        return None

    if value.isdigit():
        return int(value) / 1_000_000

    if ":" in value:
        hours, minutes, seconds = value.split(":")
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)

    return None


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "--:--:--"

    seconds = max(0, int(seconds))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


@dataclass(slots=True)
class FfmpegProgressState:
    duration: float | None = None
    out_time: float | None = None
    speed: str | None = None
    started_at: float = 0.0


class FfmpegProgressFormatter:
    def format(self, state: FfmpegProgressState, now: int, *, completed: bool = False) -> str:
        elapsed = now - state.started_at

        status = "completed" if completed else "progress"
        percent = None
        eta = None

        if state.duration and state.out_time is not None:
            percent = min(100.0, state.out_time / state.duration * 100.0)
            remaining_media = max(0.0, state.duration - state.out_time)

            speed_value = self._parse_speed(state.speed)
            eta = (
                remaining_media / speed_value
                if speed_value and speed_value > 0
                else None
            )

        message = f"{status}"

        if percent is not None:
            message += f" {percent:.1f}%"

        message += (
            " | "
            f"processed {format_duration(state.out_time)} / "
            f"{format_duration(state.duration)} | "
            f"speed {state.speed or 'N/A'} | "
            f"eta {format_duration(eta)} | "
            f"elapsed {format_duration(elapsed)}"
        )

        return message

    def _parse_speed(self, speed: str | None) -> float | None:
        if not speed:
            return None

        value = speed.strip().removesuffix("x")

        try:
            return float(value)
        except ValueError:
            return None


class FfmpegProgressHandler(LogHandler):
    def __init__(
        self,
        logger: LoggerType,
        *,
        log_level: int = logging.INFO,
        interval: float = 5.0,
        formatter: FfmpegProgressFormatter | None = None,
        enabled: bool = True,
        suppress_raw_lines: bool = True,
    ):
        self.logger = logger
        self.log_level = log_level
        self.enabled = enabled
        self.suppress_raw_lines = suppress_raw_lines
        self.formatter = formatter or FfmpegProgressFormatter()

        self.state = self._new_state()
        self._active = False
        self._completed = False

        self._emitter = DelayedLogEmitter(
            interval=interval,
            emit_callback=lambda message, level: self.logger.log(level, message),
        )

    def _new_state(self) -> FfmpegProgressState:
        return FfmpegProgressState(started_at=time.monotonic())

    def _reset_for_new_run(self) -> None:
        # Flush the last pending progress line before starting another ffmpeg run.
        self._emitter.flush(restart_timer=False)

        self.state = self._new_state()
        self._active = False
        self._completed = False

    def handle(self, event: LogEvent) -> bool:
        if not self.enabled:
            return False
        
        line = event.message.strip()

        if not line:
            return False
        
        ffmpeg_match = FFMPEG_LOG_RE.search(line)
        if not ffmpeg_match:
            return False

        prefix = ffmpeg_match.group(1)
        line = ffmpeg_match.group(2)

        duration = parse_ffmpeg_duration(line)
        if duration is not None:
            if self._active or self._completed:
                self._reset_for_new_run()

            self.state.duration = duration
            self._active = True

        elif "=" in line:
            key, value = line.split("=", 1)

            if key == "out_time_ms":
                self.state.out_time = parse_ffmpeg_time(value)
                self._active = True

            elif key == "out_time":
                self.state.out_time = parse_ffmpeg_time(value)
                self._active = True

            elif key == "speed":
                self.state.speed = value
                self._active = True

            elif key == "progress":
                self._active = True
                completed = value == "end"
                message = self.formatter.format(self.state, time.monotonic(), completed=completed)
                message = prefix + message

                self._emitter.submit(message, log_level=self.log_level, force=completed)

                if completed:
                    self._completed = True
                    self._active = False

        return self.suppress_raw_lines

    def close(self) -> None:
        self._emitter.close()
