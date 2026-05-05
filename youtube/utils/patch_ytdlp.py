import contextlib
import enum
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

class AppNames(enum.StrEnum):
    FFMPEG = "ffmpeg"
    # FFPROBE = "ffprobe"
    # AVCONV = "avconv"
    # AVPROBE = "avprobe"


FFMPEG_EXE = {
    'ffmpeg' : AppNames.FFMPEG,
    'ffmpeg.exe' : AppNames.FFMPEG,
    # 'ffprobe' : AppNames.FFPROBE,
    # 'ffprobe.exe' : AppNames.FFPROBE,
    # 'avconv' : AppNames.AVCONV,
    # 'avconv.exe' : AppNames.AVCONV,
    # 'avprobe' : AppNames.AVPROBE,
    # 'avprobe.exe' : AppNames.AVPROBE,
}

def get_app_name(cmd) -> bool:
    if not isinstance(cmd, (list, tuple)) or not cmd:
        return None

    exe = os.path.basename(str(cmd[0])).lower()
    return FFMPEG_EXE.get(exe, None)


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

        app_name = get_app_name(cmd)
        if not app_name:
            return original_popen_run(*args, timeout=timeout, **kwargs)

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
                    clean_line = f'[{app_name}] {clean_line}'
                    active_pp.to_screen(clean_line)

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
    if not enabled:
        return contextlib.nullcontext()

    return patch_ytdlp_ffmpeg_live_logs()
