from youtube.handlers.base_playlist_feed_handler import BasePlaylistFeedHandler
from youtube.handlers.youtube_response.channel_structure import YoutubeChannelResponseStructure
from youtube.handlers.youtube_response.playlists_sturcture import YoutubePlaylistsResponse
from youtube.youtube import __version__, cache_manager
from youtube.logging_utils import TaggedLogger
import youtube.config_utils

import requests
from feedgen.feed import FeedGenerator
from feedgen.ext.podcast import PodcastExtension
from tornado import ioloop, web


import datetime
import os

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

        payload = {
            'part': 'snippet',
            'id': playlist,
            'key': youtube.config_utils.KEY
        }
        request = await ioloop.IOLoop.current().run_in_executor(
            None,
            lambda: requests.get('https://www.googleapis.com/youtube/v3/playlists', params=payload, proxies=youtube.config_utils.PROXIES)
        )
        if request.status_code == 200:
            logger.debug('Downloaded Playlist Information', playlist)
        else:
            logger.error(f'Error Downloading Playlist: {request.reason}', playlist)
            self.send_error(reason='Error Downloading Playlist')
            return

        response:YoutubePlaylistsResponse = request.json()
        #logger.debug(f'{response=}', playlist)
        snippet = response.items[0].snippet

        icon_url = None
        title = None
        description = None
        language = None

        as_channel = self.get_argument("as_channel", None)
        if as_channel is not None:
            payload = {
                'part': 'snippet',
                'maxResults': 1,
                'id': snippet.channelId,
                'key': youtube.config_utils.KEY
            }
            request = await ioloop.IOLoop.current().run_in_executor(
                None,
                lambda: requests.get('https://www.googleapis.com/youtube/v3/channels', params=payload, proxies=youtube.config_utils.PROXIES)
            )
            if request.status_code == 200:
                logger.debug('Downloaded Playlist\'s Channel Information', playlist)
            else:
                logger.error(f'Error Downloading Playlist\'s Channel: {request.reason}', playlist)
                self.send_error(reason='Error Downloading Playlist')
                return

            response:YoutubeChannelResponseStructure = request.json()
            channel_data = response.items[0].snippet
            icon_key = max(
                channel_data.thumbnails,
                key=lambda x: channel_data.thumbnails[x].width
            )
            icon_url = channel_data.thumbnails[icon_key].url
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
            description = snippet.get('description', '') or ' '
        if not icon_url:
            icon_type = max(
                snippet.thumbnails,
                key=lambda x: snippet.thumbnails[x].width
            )
            icon_url = snippet.thumbnails[icon_type].url if icon_type else ""

        if not language:
            language = snippet.get('defaultLanguage', 'en-US')

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