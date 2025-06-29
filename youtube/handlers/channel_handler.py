import pyyoutube

from tornado import ioloop
from youtube.logging_utils import TaggedLogger

from youtube.handlers.base_playlist_feed_handler import BasePlaylistFeedHandler

logger = TaggedLogger(__name__)

class ChannelHandler(BasePlaylistFeedHandler):

    def initialize(self, audio_handler_path: str):
        """
        Initializes the ChannelHandler with the specified audio handler path.

        Args:
            audio_handler_path (str): The path to the audio handler.

        Returns:
            None
        """
        super().initialize(logger, audio_handler_path)

    async def head(self, channel):
        """
        Coroutine function to set header values for the specified channel.

        Args:
            self: The instance of the class.
            channel: The channel for which the header values are being set.

        Returns:
            None
        """
        self.set_header('Content-type', 'application/rss+xml')
        self.set_header('Accept-Ranges', 'bytes')

    async def get(self, channel:str):
        """
        A coroutine function that retrieves videos from a specified YouTube channel and generates an RSS feed. 
        Parameters:
            - self: the class instance
            - channel: the channel from which to retrieve videos
        Return types:
            - None
        """

        index = channel.find('/')
        if index != -1:
            logger.warning(f"Channel name contains a slash: {channel}", channel)
            channel = channel[:index]

        if self.try_response_from_cache(channel):
            return

        handle = None
        channel_id = None
        if channel.startswith('@'):
            handle = channel
        else:
            channel_id = channel

        try:
            channel_response:pyyoutube.ChannelListResponse = await ioloop.IOLoop.current().run_in_executor(
                None,
                lambda: self.youtubeapi.get_channel_info(
                    channel_id=channel_id,
                    for_handle=handle,
                    parts=['snippet', 'contentDetails', 'topicDetails'],
                    hl=self.hl,
                )
            )
        except pyyoutube.PyYouTubeException as e:
            logger.error(f'Error retrieving channel information: {e}', channel)
            self.send_error(reason='Error retrieving channel information', status_code=404 if e.status_code == 404 else 500)
            return

        logger.debug('Downloaded Channel Information', channel)

        channel_data = channel_response.items[0]
        playlist = channel_data.contentDetails.relatedPlaylists.uploads
        categories = [category.rsplit('/', 1)[-1] for category in channel_data.topicDetails.topicCategories] if channel_data.topicDetails and channel_data.topicDetails.topicCategories else []
        channel_data = channel_data.snippet

        title = channel_data.title or channel

        logger.info(f'Channel: {channel} ({title})', channel)
        thumbnails = channel_data.thumbnails
        thumbnail = self.getMaxResolutionThumbnail(thumbnails)

        description = channel_data.description or ' '
        icon_url = thumbnail.url if thumbnail else ""
        uniq_id = f'{self.request.protocol}://{self.request.host}{self.request.uri}'
        channel_url = f'https://www.youtube.com/' + (handle or f'channel/{channel}')
        language = channel_data.defaultLanguage or 'en-US'
        feed = await self.build_feed(
            channel,
            playlist,
            uniq_id,
            channel_url,
            title,
            title,
            description,
            icon_url,
            language,
            categories,
            channel
        )

        if not feed:
            self.send_error(reason='Error Downloading Channel')
            return

        self.write(feed)
        self.finish()
