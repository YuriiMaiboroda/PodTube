import youtube.utils.config_utils
from youtube.utils.logging_utils import TaggedLogger
import utils

import pyyoutube
import requests
from tornado import web

class BaseYoutubeHandler(web.RequestHandler):
    """
    A base class for YouTube handlers that provides common functionality for handling requests.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.youtube_client = None

    def initialize(self, logger:TaggedLogger):
        """
        Initializes the BaseYoutubeHandler with a logger.

        Args:
            logger (TaggedLogger): The logger instance to be used for logging.
        """
        self.logger = logger

    def prepare(self):
        super().prepare()
        self.set_header('charset', 'utf-8')
        self.youtube_client = pyyoutube.Client(api_key=youtube.utils.config_utils.KEY, proxies=youtube.utils.config_utils.PROXIES)
        self.hl = self.get_argument('hl', youtube.utils.config_utils.HL)
        self.mark_watched = utils.convert_to_bool(self.get_argument('mark_watched', youtube.utils.config_utils.MARK_WATCHED))
        self.start_time = self.get_argument("start", None)
        self.end_time = self.get_argument("end", None)

    def on_finish(self):
        if self.youtube_client is not None:
            session = getattr(self.youtube_client, "session", None)
            if isinstance(session, requests.Session):
                try:
                    session.close()
                except Exception as e:
                    self.logger.debug("Fail while closing session: " + e, stack_info=True)

class BaseYoutubeRssHandler(BaseYoutubeHandler):
    def prepare(self):
        super().prepare()
        self.set_header('Content-type', 'application/rss+xml')
