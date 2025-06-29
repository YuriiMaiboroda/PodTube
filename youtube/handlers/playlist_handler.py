import pyyoutube

from youtube.handlers.base_playlist_feed_handler import BasePlaylistFeedHandler
from youtube.logging_utils import TaggedLogger

from tornado import ioloop

logger = TaggedLogger(__name__)

class PlaylistHandler(BasePlaylistFeedHandler):
    def initialize(self, audio_handler_path: str):
        """
        Initialize the class with the provided video and audio handler paths.

        Args:
            audio_handler_path (str): The path to the audio handler.
        """
        super().initialize(logger, audio_handler_path)

    async def get(self, playlist:str):
        """
        A coroutine function to fetch a playlist and generate an RSS feed based on the playlist content.
        """
        index = playlist.find('/')
        if index != -1:
            logger.warning(f"Playlist name contains a slash: {playlist}", playlist)
            playlist = playlist[:index]

        if self.try_response_from_cache(playlist):
            return

        try:
            response:pyyoutube.PlaylistListResponse = await ioloop.IOLoop.current().run_in_executor(
                None,
                lambda: self.youtubeapi.get_playlist_by_id(
                    playlist_id=playlist,
                    parts=['snippet', 'contentDetails'],
                    hl=self.hl,
                )
            )
        except pyyoutube.PyYouTubeException as e:
            logger.error(f'Error retrieving playlist information: {e}', playlist)
            self.send_error(reason='Error retrieving playlist information', status_code=404 if e.status_code == 404 else 500)
            return

        snippet:pyyoutube.PlaylistSnippet = response.items[0].snippet

        icon_url = None
        title = None
        description = None
        language = None

        if self.get_argument("as_channel", None) is not None:
            try:
                response:pyyoutube.ChannelListResponse = await ioloop.IOLoop.current().run_in_executor(
                    None,
                    lambda: self.youtubeapi.get_channel_info(
                        channel_id=snippet.channelId,
                        parts=['snippet'],
                        hl=self.hl,
                    )
                )
            except pyyoutube.PyYouTubeException as e:
                logger.error(f'Error retrieving channel information: {e}', playlist)
                self.send_error(reason='Error retrieving channel information', status_code=404 if e.status_code == 404 else 500)
                return

            channel_data:pyyoutube.ChannelSnippet = response.items[0].snippet
            thumbnail = self.getMaxResolutionThumbnail(channel_data.thumbnails)
            if thumbnail:
                icon_url = thumbnail.url
            if channel_data.title:
                title = channel_data.title
            if channel_data.description:
                description = channel_data.description
            if channel_data.defaultLanguage:
                language = channel_data.defaultLanguage

        channel_title = snippet.channelTitle
        playlist_title = f"{channel_title}: {snippet.title}"

        logger.info(f'Playlist: {playlist} ({playlist_title})', playlist)
        if not title:
            title = playlist_title
        if not description:
            description = snippet.description or ' '
        if not icon_url:
            thumbnail = self.getMaxResolutionThumbnail(snippet.thumbnails)
            icon_url = thumbnail.url if thumbnail else None

        if not language:
            language = snippet.defaultLanguage or 'en-US'

        playlist_url = f'https://www.youtube.com/playlist/?list={playlist[0]}'
        uniq_id = f'{self.request.protocol}://{self.request.host}{self.request.uri}'
        feed = await self.build_feed(
            playlist,
            playlist,
            uniq_id,
            playlist_url,
            channel_title,
            title,
            description,
            icon_url,
            language,
            [],
            playlist
        )

        if not feed:
            self.send_error(reason='Error Downloading Playlist')
            return

        self.write(feed)
        self.finish()