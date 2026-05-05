import logging
from typing import TypeAlias
from utils.logging.tagged_logger import TaggedLogger

LoggerType: TypeAlias = TaggedLogger | logging.Logger
