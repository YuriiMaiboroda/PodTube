import contextlib
import contextvars
import logging
from types import TracebackType
from typing import Iterator, TypeAlias

_SysExcInfoType: TypeAlias = tuple[type[BaseException], BaseException, TracebackType | None] | tuple[None, None, None]
_ExcInfoType: TypeAlias = None | bool | _SysExcInfoType | BaseException
TagsType: TypeAlias = list[str] | tuple[str, ...] | str | None


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

    def __init__(self, name: str, default_tags: TagsType = None):
        self.__logger = logging.getLogger(name)
        self.default_tags = self._normalize_tags(default_tags)

    @contextlib.contextmanager
    def tags(self, *tags: str) -> Iterator[LogTagScope]:
        parent_tags = _log_tags_var.get()
        token = _log_tags_var.set(parent_tags)

        scope = LogTagScope(_log_tags_var, parent_tags, token)
        scope.set(*tags)

        try:
            yield scope
        finally:
            _log_tags_var.reset(token)

    def _normalize_tags(self, tags: TagsType) -> tuple[str, ...]:
        if tags is None:
            return ()

        if isinstance(tags, str):
            return (tags,)

        return tuple(tags)

    def _format(self, msg: str, tags: TagsType = None) -> str:
        all_tags = (
            self.default_tags
            + _log_tags_var.get()
            + self._normalize_tags(tags)
        )
        tags_str = ''.join(f'[{tag}]' for tag in all_tags)
        return f'{tags_str} {msg}' if tags_str else msg

    def log(self, level: int, msg: str, *args, tags: TagsType = None, stack_info: bool = False, **kwargs):
        self.__logger.log(level, self._format(msg, tags), *args, stack_info=stack_info, **kwargs)

    def info(self, msg: str, *args, tags: TagsType = None, stack_info: bool = False, **kwargs):
        self.__logger.info(self._format(msg, tags), *args, stack_info=stack_info, **kwargs)

    def warning(self, msg: str, *args, tags: TagsType = None, stack_info: bool = False, **kwargs):
        self.__logger.warning(self._format(msg, tags), *args, stack_info=stack_info, **kwargs)

    def error(self, msg:str, *args, tags: TagsType = None, exc_info:_ExcInfoType = None, stack_info:bool=False, **kwargs):
        self.__logger.error(self._format(msg, tags), *args, exc_info=exc_info, stack_info=stack_info, **kwargs)

    def debug(self, msg: str, *args, tags: TagsType = None, stack_info: bool = False, **kwargs):
        self.__logger.debug(self._format(msg, tags), *args, stack_info=stack_info, **kwargs)

    def isEnabledFor(self, level:int) -> bool:
        return self.__logger.isEnabledFor(level)

    @property
    def logger(self) -> logging.Logger:
        return self.__logger

    @property
    def handlers(self) -> list[logging.Handler]:
        return self.__logger.handlers