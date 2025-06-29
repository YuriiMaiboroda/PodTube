import youtube.config_utils
from youtube.logging_utils import TaggedLogger

import pyyoutube
from tornado import web

class BaseYoutubeHandler(web.RequestHandler):
    """
    A base class for YouTube handlers that provides common functionality for handling requests.
    """

    def initialize(self, logger:TaggedLogger):
        """
        Initializes the BaseYoutubeHandler with a logger.

        Args:
            logger (TaggedLogger): The logger instance to be used for logging.
        """
        self.logger = logger

    def prepare(self):
        super().prepare()
        self.set_header('Content-type', 'application/rss+xml')
        self.set_header('charset', 'utf-8')
        self.youtubeapi = pyyoutube.Api(api_key=youtube.config_utils.KEY, proxies=youtube.config_utils.PROXIES)
        self.hl = self.get_argument('hl', youtube.config_utils.HL)