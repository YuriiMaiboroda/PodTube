import youtube.config_utils
from youtube.handlers.base_playlist_feed_handler import BasePlaylistFeedHandler
from youtube.handlers.youtube_response.channel_structure import YoutubeChannelResponseStructure
from youtube.logging_utils import TaggedLogger
from youtube.youtube import __version__

import requests
from tornado import ioloop

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

        payload = {
            'part': 'snippet,contentDetails,topicDetails',
            'maxResults': 1,
            'fields': 'items',
            'key': youtube.config_utils.KEY
        }
        if handle:
            payload['forHandle'] = handle
        else:
            payload['id'] = channel_id

        request = await ioloop.IOLoop.current().run_in_executor(
            None,
            lambda: requests.get('https://www.googleapis.com/youtube/v3/channels', params=payload, proxies=youtube.config_utils.PROXIES)
        )
        if request.status_code == 200:
            logger.debug('Downloaded Channel Information', channel)
        else:
            # logger.debug(f'Request not 200: {payload=}; {request=}', channel)
            logger.error(f'Error Downloading Channel: {request.reason}', channel)
            self.send_error(reason='Error Downloading Channel', status_code=404 if request.status_code == 404 else 500)
            return

        channel_response:YoutubeChannelResponseStructure = request.json()
        channel_data = channel_response['items'][0]
        #get upload playlist
        playlist = channel_data['contentDetails']['relatedPlaylists']['uploads']
        categories = [category.rsplit('/', 1)[-1] for category in channel_data.get('topicDetails', {}).get('topicCategories', [])]
        channel_data = channel_data['snippet']

        title = channel_data.get('title', channel)

        logger.info(f'Channel: {channel} ({title})', channel)
        icon_type:str = max(
            channel_data['thumbnails'],
            key=lambda x: channel_data['thumbnails'][x]['width']
        )

        description = channel_data.get('description', None) or ' '
        icon_url = channel_data['thumbnails'][icon_type]['url'] if icon_type else ""
        uniq_id = f'{self.request.protocol}://{self.request.host}{self.request.uri}'
        channel_url = f'https://www.youtube.com/' + (handle or f'channel/{channel}')
        language = channel_data.get('defaultLanguage', 'en-US')
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
