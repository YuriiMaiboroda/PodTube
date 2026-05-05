import contextlib
import os
import re
import subprocess
import threading
import time
from typing import IO
from queue import Queue

from yt_dlp.postprocessor.ffmpeg import FFmpegPostProcessor
from yt_dlp.utils import Popen as YtdlpPopen


ACTIVE_PP_ATTR = '_active_streaming_log_pp'

FFMPEG_EXE = [
    'ffmpeg', 'ffmpeg.exe',
    # 'ffprobe', 'ffprobe.exe',
    # 'avconv', 'avconv.exe',
    # 'avprobe', 'avprobe.exe',
]

def _is_ffmpeg_tool(cmd) -> bool:
    if not isinstance(cmd, (list, tuple)) or not cmd:
        return False

    exe = os.path.basename(str(cmd[0])).lower()
    return exe in FFMPEG_EXE


def _stream_reader(stream_name: str, stream: IO, output_queue: Queue[tuple[int, str, str|bytes|None]]):
    try:
        for line in stream:
            output_queue.put((time.monotonic(), stream_name, line))
    finally:
        output_queue.put((time.monotonic(), stream_name, None))


def _decode_line_for_log(line: str | bytes) -> str:
    if isinstance(line, bytes):
        return line.decode('utf-8', errors='replace').rstrip('\r\n')
    return line.rstrip('\r\n')


def _join_output(parts: list[str|bytes], text_mode: bool):
    return ''.join(parts) if text_mode else b''.join(parts)


FFMPEG_DURATION_RE = re.compile(
    r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)'
)


def parse_ffmpeg_duration(line: str) -> float:
    match = FFMPEG_DURATION_RE.search(line)
    if not match:
        return None

    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def parse_ffmpeg_time(value: str):
    if not value:
        return None

    if value.isdigit():
        # out_time_ms is actually microseconds in ffmpeg progress output.
        return int(value) / 1_000_000

    if ':' in value:
        hours, minutes, seconds = value.split(':')
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)

    return None


def format_duration(seconds: float):
    if seconds is None:
        return '--:--:--'

    seconds = max(0, int(seconds))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    return f'{hours:02d}:{minutes:02d}:{secs:02d}'


class FfmpegProgressFormatter:
    def __init__(self, min_interval : float = 5.0):
        self.duration: float = None
        self.out_time: float = None
        self.speed: str = None
        self.started_at: float = time.monotonic()
        self.last_log_at: float = 0.0
        self.min_interval: float = min_interval

    def handle_line(self, line: str):
        duration = parse_ffmpeg_duration(line)
        if duration is not None:
            self.duration = duration
            return None

        if '=' not in line:
            return None

        key, value = line.split('=', 1)

        if key == 'out_time_ms':
            self.out_time = parse_ffmpeg_time(value)
        elif key == 'out_time':
            self.out_time = parse_ffmpeg_time(value)
        elif key == 'speed':
            self.speed = value
        elif key == 'progress':
            is_end = value == 'end'
            return self.format(force=is_end, completed=is_end)

        return None

    def format(self, force=False, completed=False):
        now = time.monotonic()

        if not force and now - self.last_log_at < self.min_interval:
            return None

        self.last_log_at = now

        elapsed = now - self.started_at

        status = 'progress'
        percent = None
        eta = None

        if self.duration and self.out_time is not None:
            percent = min(100.0, self.out_time / self.duration * 100.0)
            remaining_media = max(0.0, self.duration - self.out_time)

            speed_value = self.parse_speed()
            eta = remaining_media / speed_value if speed_value and speed_value > 0 else None

            if completed:
                status = 'completed'

        message = f'{status}'
        if (percent is not None):
            message += f' {percent:.1f}%'
        
        message += (
            ' | '
            f'processed {format_duration(self.out_time)} / {format_duration(self.duration)} | '
            f'speed {self.speed or "N/A"} | '
            f'eta {format_duration(eta)} | '
            f'elapsed {format_duration(elapsed)}'
        )

        return message

    def parse_speed(self):
        if not self.speed:
            return None

        value = self.speed.strip().removesuffix('x')

        try:
            return float(value)
        except ValueError:
            return None


@contextlib.contextmanager
def patch_ytdlp_ffmpeg_postprocessor_context():
    sentinel = object()

    def patched_real_run_ffmpeg(self, *args, **kwargs):
        previous_pp = getattr(FFmpegPostProcessor, ACTIVE_PP_ATTR, sentinel)

        try:
            setattr(FFmpegPostProcessor, ACTIVE_PP_ATTR, self)
            return original_real_run_ffmpeg(self, *args, **kwargs)
        finally:
            if previous_pp is sentinel:
                if hasattr(FFmpegPostProcessor, ACTIVE_PP_ATTR):
                    delattr(FFmpegPostProcessor, ACTIVE_PP_ATTR)
            else:
                setattr(FFmpegPostProcessor, ACTIVE_PP_ATTR, previous_pp)

    original_real_run_ffmpeg = FFmpegPostProcessor.real_run_ffmpeg
    try:
        FFmpegPostProcessor.real_run_ffmpeg = patched_real_run_ffmpeg
        yield
    finally:
        FFmpegPostProcessor.real_run_ffmpeg = original_real_run_ffmpeg


@contextlib.contextmanager
def patch_ytdlp_ffmpeg_streaming_logs():
    def patched_run(cls, *args, timeout=None, **kwargs):
        cmd = args[0] if args else kwargs.get('args')

        if not _is_ffmpeg_tool(cmd):
            return original_popen_run(*args, timeout=timeout, **kwargs)

        exe = os.path.basename(str(cmd[0]))
        app_name = os.path.splitext(exe)[0].lower()
        progress_formatter = FfmpegProgressFormatter(min_interval=5.0) if app_name == 'ffmpeg' else None

        text_mode = (
            kwargs.get('text')
            or kwargs.get('universal_newlines')
            or kwargs.get('encoding')
            or kwargs.get('errors')
        )

        kwargs = dict(kwargs)
        kwargs['stdout'] = subprocess.PIPE
        kwargs['stderr'] = subprocess.PIPE
        kwargs.setdefault('stdin', subprocess.DEVNULL)

        if text_mode:
            kwargs.setdefault('encoding', 'utf-8')
            kwargs.setdefault('errors', 'replace')
            kwargs.setdefault('bufsize', 1)

        proc: YtdlpPopen = cls(*args, **kwargs)

        active_pp:FFmpegPostProcessor = getattr(FFmpegPostProcessor, ACTIVE_PP_ATTR, None)

        output_queue: Queue[tuple[int, str, str|bytes|None]] = Queue()
        stdout_parts: list[str|bytes] = []
        stderr_parts: list[str|bytes] = []

        threads = [
            threading.Thread(target=_stream_reader, args=('stdout', proc.stdout, output_queue), daemon=True),
            threading.Thread(target=_stream_reader, args=('stderr', proc.stderr, output_queue), daemon=True),
        ]

        for thread in threads:
            thread.start()

        finished_streams = 0

        try:
            while finished_streams < 2:
                _, stream_name, line = output_queue.get()

                if line is None:
                    finished_streams += 1
                    continue

                if stream_name == 'stdout':
                    stdout_parts.append(line)
                else:
                    stderr_parts.append(line)

                clean_line = _decode_line_for_log(line)

                if clean_line and active_pp is not None:
                    if progress_formatter and stream_name == 'stderr':
                        clean_line = progress_formatter.handle_line(clean_line)
                        if not clean_line:
                            continue

                    active_pp.to_screen(f'{clean_line}')

            returncode = proc.wait(timeout=timeout)

        except BaseException:
            proc.kill(timeout=None)
            proc.wait()
            raise

        stdout = _join_output(stdout_parts, text_mode)
        stderr = _join_output(stderr_parts, text_mode)

        return stdout, stderr, returncode


    original_popen_run = YtdlpPopen.run
    try:
        YtdlpPopen.run = classmethod(patched_run)
        yield
    finally:
        YtdlpPopen.run = original_popen_run


@contextlib.contextmanager
def patch_ytdlp_ffmpeg_live_logs():
    with patch_ytdlp_ffmpeg_postprocessor_context():
        with patch_ytdlp_ffmpeg_streaming_logs():
            yield

def ytdlp_ffmpeg_live_logs_context(enabled: bool):
    return (
        patch_ytdlp_ffmpeg_live_logs()
        if enabled
        else contextlib.nullcontext()
    )
