import youtube.config_utils
from youtube.logging_utils import TaggedLogger
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
        self.youtubeapi = None

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
        self.youtubeapi = pyyoutube.Api(api_key=youtube.config_utils.KEY, proxies=youtube.config_utils.PROXIES)
        self.hl = self.get_argument('hl', youtube.config_utils.HL)
        self.mark_watched = utils.convert_to_bool(self.get_argument('mark_watched', youtube.config_utils.MARK_WATCHED))
        self.start_time = self.get_argument("start", None)
        self.end_time = self.get_argument("end", None)

    def on_finish(self):
        if self.youtubeapi is not None:
            session = getattr(self.youtubeapi, "session", None)
            if isinstance(session, requests.Session):
                try:
                    session.close()
                except Exception:
                    pass

class BaseYoutubeRssHandler(BaseYoutubeHandler):
    def prepare(self):
        super().prepare()
        self.set_header('Content-type', 'application/rss+xml')
