import sys
import logging
from contextlib import contextmanager
from types import TracebackType
from typing import TypeAlias

class TaggedLogger:
    __logger: logging.Logger

    _SysExcInfoType: TypeAlias = tuple[type[BaseException], BaseException, TracebackType | None] | tuple[None, None, None]
    _ExcInfoType: TypeAlias = None | bool | _SysExcInfoType | BaseException

    def __init__(self, name:str):
        self.__logger = logging.getLogger(name)

    def _format(self, msg:str, tags:list[str]|str|None) -> str:
        if tags is None:
            tags = []
        elif isinstance(tags, str):
            tags = [tags]
        tags_str = ''.join(f'[{i}]' for i in tags)
        return f"{tags_str} {msg}" if tags_str else msg

    def info(self, msg:str, tags:list[str]|str|None=None, stack_info:bool=False):
        self.__logger.info(self._format(msg, tags), stack_info=stack_info)

    def warning(self, msg:str, tags:list[str]|str|None=None, stack_info:bool=False):
        self.__logger.warning(self._format(msg, tags), stack_info=stack_info)

    def error(self, msg:str, tags:list[str]|str|None=None, exc_info:_ExcInfoType = None, stack_info:bool=False):
        self.__logger.error(self._format(msg, tags), exc_info=exc_info, stack_info=stack_info)

    def debug(self, msg:str, tags:list[str]|str|None=None, stack_info:bool=False):
        self.__logger.debug(self._format(msg, tags), stack_info=stack_info)

    def isEnabledFor(self, level:int) -> bool:
        return self.__logger.isEnabledFor(level)

    @property
    def logger(self) -> logging.Logger:
        return self.__logger
    
    @property
    def handlers(self) -> list[logging.Handler]:
        return self.__logger.handlers

class StreamToLogger:
    __logger:TaggedLogger|logging.Logger
    __level:int

    def __init__(self, logger:TaggedLogger|logging.Logger, level:int):
        self.__logger = logger
        self.__level = level

    def write(self, message:str):
        for line in message.splitlines():
            self.__logger.log(self.__level, line.rstrip())

    def flush(self):
        for handler in self.__logger.handlers:
            if hasattr(handler, 'flush'):
                handler.flush()

def is_logger_outputs_to_streams(logger:TaggedLogger|logging.Logger, streams):
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            if handler.stream in streams:
                return True
    return False


@contextmanager
def redirect_std_streams(logger:TaggedLogger|logging.Logger, stderr_level:int=logging.ERROR, stdout_level:int=logging.INFO):
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