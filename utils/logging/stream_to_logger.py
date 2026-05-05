import sys
import logging
import contextlib

from utils.logging.common import LoggerType

class StreamToLogger:
    __logger: LoggerType
    __level: int

    def __init__(self, logger: LoggerType, level: int):
        self.__logger = logger
        self.__level = level

    def write(self, message: str):
        for line in message.splitlines():
            self.__logger.log(self.__level, line.rstrip())

    def flush(self):
        for handler in self.__logger.handlers:
            if hasattr(handler, 'flush'):
                handler.flush()

def is_logger_outputs_to_streams(logger: LoggerType, streams):
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            if handler.stream in streams:
                return True
    return False


@contextlib.contextmanager
def redirect_std_streams(logger:LoggerType, stderr_level:int=logging.ERROR, stdout_level:int=logging.INFO):
    old_stderr = None
    old_stdout = None
    try:
        if not is_logger_outputs_to_streams(logger, (sys.stderr, sys.__stderr__)):
            old_stderr = sys.stderr
            sys.stderr = StreamToLogger(logger, stderr_level)
        if not is_logger_outputs_to_streams(logger, (sys.stdout, sys.__stdout__)):
            old_stdout = sys.stdout
            sys.stdout = StreamToLogger(logger, stdout_level)
        yield
    finally:
        if old_stderr is not None:
            sys.stderr = old_stderr
        if old_stdout is not None:
            sys.stdout = old_stdout

