import sys
import logging
import contextlib
import contextvars
from types import TracebackType
from typing import TypeAlias


_SysExcInfoType: TypeAlias = tuple[type[BaseException], BaseException, TracebackType | None] | tuple[None, None, None]
_ExcInfoType: TypeAlias = None | bool | _SysExcInfoType | BaseException

_log_tags_var: contextvars.ContextVar[tuple[str, ...]] = contextvars.ContextVar(
    'log_tags',
    default=(),
)

class LogTagScope:
    def __init__(self, context_var: contextvars.ContextVar[tuple[str, ...]], parent_tags: tuple[str, ...], token):
        self._context_var = context_var
        self._parent_tags = parent_tags
        self._token = token
        self._local_tags = ()

    def set(self, *tags: str):
        self._local_tags = tuple(str(tag) for tag in tags if tag)
        self._context_var.set(self._parent_tags + self._local_tags)

    def add(self, *tags: str):
        self.set(*(self._local_tags + tuple(str(tag) for tag in tags if tag)))

class TaggedLogger:
    __logger: logging.Logger

    def __init__(self, name: str, default_tags: list[str] | None = None):
        self.__logger = logging.getLogger(name)
        self.default_tags = tuple(default_tags or [])

    @contextlib.contextmanager
    def tags(self, *tags: str):
        parent_tags = _log_tags_var.get()
        token = _log_tags_var.set(parent_tags)

        scope = LogTagScope(_log_tags_var, parent_tags, token)
        scope.set(*tags)

        try:
            yield scope
        finally:
            _log_tags_var.reset(token)

    def _normalize_tags(self, tags: list[str] | tuple[str, ...] | str | None) -> tuple[str, ...]:
        if tags is None:
            return ()

        if isinstance(tags, str):
            return (tags,)

        return tuple(tags)

    def _format(self, msg: str, tags: list[str] | tuple[str, ...] | str | None = None) -> str:
        all_tags = (
            self.default_tags
            + _log_tags_var.get()
            + self._normalize_tags(tags)
        )
        tags_str = ''.join(f'[{tag}]' for tag in all_tags)
        return f'{tags_str} {msg}' if tags_str else msg

    def log(self, level: int, msg: str, *args, tags: list[str] | str | None = None, stack_info: bool = False, **kwargs):
        self.__logger.log(level, self._format(msg, tags), *args, stack_info=stack_info, **kwargs)

    def info(self, msg: str, *args, tags: list[str] | str | None = None, stack_info: bool = False, **kwargs):
        self.__logger.info(self._format(msg, tags), *args, stack_info=stack_info, **kwargs)

    def warning(self, msg: str, *args, tags: list[str] | str | None = None, stack_info: bool = False, **kwargs):
        self.__logger.warning(self._format(msg, tags), *args, stack_info=stack_info, **kwargs)

    def error(self, msg:str, *args, tags: list[str] | str | None = None, exc_info:_ExcInfoType = None, stack_info:bool=False, **kwargs):
        self.__logger.error(self._format(msg, tags), *args, exc_info=exc_info, stack_info=stack_info, **kwargs)

    def debug(self, msg: str, *args, tags: list[str] | str | None = None, stack_info: bool = False, **kwargs):
        self.__logger.debug(self._format(msg, tags), *args, stack_info=stack_info, **kwargs)

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


@contextlib.contextmanager
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