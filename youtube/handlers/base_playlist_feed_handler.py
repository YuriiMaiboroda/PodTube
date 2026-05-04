import datetime
import pyyoutube

from feedgen.feed import FeedGenerator
from feedgen.ext.podcast import PodcastExtension
from feedgen.ext.podcast_entry import PodcastEntryExtension
from tornado import ioloop
from urllib.parse import urlencode, urlunparse

from youtube.cache import CacheItem
from youtube.handlers.base_youtube_handler import BaseYoutubeRssHandler
from youtube.logging_utils import TaggedLogger
import youtube.config_utils
import youtube.youtube

FEED_CACHE_NAME = 'feeds'

class FeedCacheItem(CacheItem):
    """
    A class representing a cache item for channel feeds.
    Inherits from CacheItem.
    """
    def __init__(self, name:str, feed:str, expire:datetime.datetime|None = None):
        """
        Initializes the ChannelFeedCacheItem with the given parameters.

        :param expire: A datetime object representing the expiration time of the cache item.
        :param title: A string representing the title of the channel.
        :param feed: A string representing the RSS feed of the channel.
        """
        super().__init__(expire or (datetime.datetime.now() + datetime.timedelta(seconds=youtube.config_utils.PLAYLIST_EXPIRATION_TIME)), name)
        self.feed = feed

class BasePlaylistFeedHandler(BaseYoutubeRssHandler):
    def initialize(self, logger:TaggedLogger, audio_handler_path:str):
        super().initialize(logger)
        self.audio_handler_path = audio_handler_path

    async def head(self, *args, **kwargs):
        """
        A coroutine function that sets the header for the given playlist.

        Args:
            self: The instance of the class.

        Returns:
            None
        """
        self.set_header('Content-type', 'application/rss+xml')
        self.set_header('Accept-Ranges', 'bytes')

    def try_response_from_cache(self, item_name: str) -> bool:
        """
        Attempts to retrieve a feed from the cache.
        Args:
            item_name (str): The name of the item to retrieve from the cache.
        """
        channel_feed:FeedCacheItem = youtube.youtube.cache_manager.get(FEED_CACHE_NAME, item_name)
        if channel_feed and channel_feed.expire > datetime.datetime.now():
            self.write(channel_feed.feed)
            self.finish()
            return True
        return False

    def save_feed_to_cache(self, item_name: str, name:str, feed: str):
        """
        Saves the generated feed to the cache.

        Args:
            item_name (str): The name of the item to save in the cache.
            feed (str): The generated feed content to be cached.
        """
        youtube.youtube.cache_manager.set(
            FEED_CACHE_NAME,
            item_name,
            FeedCacheItem(name=name, feed=feed)
        )

    async def build_feed(self,
        cache_id:str,
        playlist:str,
        id:str,
        url:str,
        author:str,
        title:str,
        description:str,
        icon_url:str,
        language:str,
        categories:list[str],
        log_tag:str
    ) -> str:
        fg = FeedGenerator()
        podcast_extension_name = PodcastExtension.__module__.rsplit('.', 1)[-1]
        fg.load_extension(podcast_extension_name)
        fg_podcast:PodcastExtension = getattr(fg, podcast_extension_name)
        fg.generator(
            'PodTube (python-feedgen)',
            youtube.youtube.__version__,
            'https://github.com/YuriiMaiboroda/PodTube'
        )
        fg.id(id)
        fg.title(title)
        fg.description(description)
        fg.author(
            name=author,
            email=' ',
            uri=url
        )
        fg_podcast.itunes_author(author)
        fg.link(
            href=url,
            rel='self'
        )
        fg.language(language)
        fg.image(icon_url)
        fg_podcast.itunes_image(icon_url)
        fg_podcast.itunes_explicit('no')
        fg_podcast.itunes_summary(description)
        fg_podcast.itunes_category([{"cat": category} for category in categories])
        fg.updated(str(datetime.datetime.now(datetime.timezone.utc)))

        try:
            max_items = int(self.get_argument("max_items", "-1"))
            self.logger.debug(f"Will grab maximum {max_items} videos", log_tag)
        except ValueError:
            self.logger.error(f"Failed parse max_count to int: {max_items}", log_tag)
            max_items = 1

        isFirstRequest = True
        playlist_items_response:pyyoutube.PlaylistItemListResponse = pyyoutube.PlaylistItemListResponse()

        items_count = 0
        while (isFirstRequest or playlist_items_response.nextPageToken) and (max_items < 1 or items_count < max_items):
            isFirstRequest = False
            restItemsCount = max_items - items_count if max_items >= 0 else None
            next_page = playlist_items_response.nextPageToken

            try:
                playlist_items_response = await ioloop.IOLoop.current().run_in_executor(
                    None,
                    lambda: self.youtube_client.playlistItems.list(
                        parts = ['snippet'],
                        playlist_id = playlist,
                        max_results = min(restItemsCount or 50, 50),
                        page_token = next_page,
                    )
                )
            except pyyoutube.PyYouTubeException as e:
                if e.status_code != 404:
                    self.logger.error(f'Error retrieving playlist items: {e}', log_tag)
                    self.send_error(reason='Error retrieving playlist items', status_code=404 if e.status_code == 404 else 500)
                    return None

                self.logger.error(f'Playlist not found: {playlist}', log_tag)

            if playlist_items_response.items is None:
                playlist_items_response.items = []

            all_video_contentDetails:dict[str, pyyoutube.VideoContentDetails] = {}
            all_video_status:dict[str, pyyoutube.VideoStatus] = {}
            all_video_liveStreamingDetails:dict[str, pyyoutube.VideoLiveStreamingDetails] = {}

            batch_size=50
            for i in range(0, len(playlist_items_response.items), batch_size):
                items = playlist_items_response.items[i:i+batch_size]
                videos_response:pyyoutube.VideoListResponse = None
                try:
                    videos_response = await ioloop.IOLoop.current().run_in_executor(
                        None,
                        lambda: self.youtube_client.videos.list(
                            video_id=','.join(item.snippet.resourceId.videoId for item in items),
                            parts=['contentDetails', 'liveStreamingDetails', 'status'],
                            hl=self.hl
                        )
                    )
                except pyyoutube.PyYouTubeException as e:
                    self.logger.error(f'Error retrieving video details: {e}', log_tag)

                if videos_response and videos_response.items:
                    for item in videos_response.items:
                        if item.id is None:
                            continue
                        if item.contentDetails is not None:
                            all_video_contentDetails[item.id] = item.contentDetails
                        if item.status is not None:
                            all_video_status[item.id] = item.status
                        if item.liveStreamingDetails is not None:
                            all_video_liveStreamingDetails[item.id] = item.liveStreamingDetails

            self.update_file_names(playlist_items_response.items)

            for item in playlist_items_response.items:
                snippet = item.snippet
                current_video = snippet.resourceId.videoId
                log_tags = [log_tag, current_video]

                video_contentDetails:pyyoutube.VideoContentDetails = all_video_contentDetails.get(current_video, None) if all_video_contentDetails else None
                video_status:pyyoutube.VideoStatus = all_video_status.get(current_video, None) if all_video_status else None
                video_liveStreamingDetails:pyyoutube.VideoLiveStreamingDetails = all_video_liveStreamingDetails.get(current_video, None) if all_video_liveStreamingDetails else None

                if video_status is not None:
                    if video_status.privacyStatus and video_status.privacyStatus.lower() == 'private':
                        continue
                elif 'private' in snippet.title.lower():
                    continue

                if snippet.channelTitle is None:
                    snippet.channelTitle = snippet.channelId or f'Unknown Channel. {playlist}'

                self.logger.debug(f'{snippet.title}', log_tags)
                items_count += 1

                fe = fg.add_entry()
                fe_podcast:PodcastEntryExtension = getattr(fe, podcast_extension_name)
                fe.title(snippet.title)
                fe.id(current_video)
                thumbnail:pyyoutube.models.common.Thumbnail = self.getMaxResolutionThumbnail(snippet.thumbnails)
                fe_podcast.itunes_image(thumbnail.url if thumbnail else None)
                fe.updated(snippet.publishedAt)

                query = {}
                if self.hl is not None:
                    query['hl'] = self.hl
                if self.mark_watched is not None:
                    query['mark_watched'] = self.mark_watched
                if self.start_time is not None:
                    query['start'] = self.start_time
                if self.end_time is not None:
                    query['end'] = self.end_time
                final_url = urlunparse((
                    self.request.protocol,
                    self.request.host,
                    f'{self.audio_handler_path}{current_video}',
                    '',
                    urlencode(query),
                    ''
                ))

                # final_url = f'{self.request.protocol}://{self.request.host}{self.audio_handler_path}{current_video}'
                fe.enclosure(
                    url=final_url,
                    type="audio/mpeg"
                )
                fe.author(name=snippet.channelTitle)
                fe_podcast.itunes_author(snippet.channelTitle)
                fe.pubDate(snippet.publishedAt)
                fe.link(
                    href=f'https://www.youtube.com/watch?v={current_video}',
                    title=snippet.title
                )
                description = snippet.description
                if video_liveStreamingDetails:
                    stream_infos = []
                    if video_liveStreamingDetails.scheduledStartTime:
                        stream_infos.append(f"Live stream scheduled to start at {self.getDateTimeStingInLocalTimezone(video_liveStreamingDetails.scheduledStartTime)}")
                    if video_liveStreamingDetails.actualStartTime:
                        stream_infos.append(f"Live stream started at {self.getDateTimeStingInLocalTimezone(video_liveStreamingDetails.actualStartTime)}")
                    if video_liveStreamingDetails.actualEndTime:
                        stream_infos.append(f"Live stream ended at {self.getDateTimeStingInLocalTimezone(video_liveStreamingDetails.actualEndTime)}")
                        stream_infos.append("Live stream is ended")
                    if stream_infos:
                        description = f"{description}\n\nLive stream information:\n" + "\n".join(stream_infos)

                description = description + f'\n\n{final_url}\n{self.getDateTimeStingInLocalTimezone(snippet.publishedAt)}'
                fe_podcast.itunes_summary(description)
                fe.description(description)

                duration = video_contentDetails.get_video_seconds_duration() if video_contentDetails else None
                if duration is not None:
                    fe_podcast.itunes_duration(duration)

        self.logger.debug(f"Got {items_count} videos", log_tag)

        feed = fg.rss_str()

        self.save_feed_to_cache(cache_id, title, feed)

        return feed

    def getDateTimeStingInLocalTimezone(self, datetime:str) -> str:
        return pyyoutube.DatetimeTimeMixin.string_to_datetime(datetime).astimezone().replace(tzinfo=None).isoformat(' ', 'seconds').replace(":", ".")

    def update_file_names(self, items:list[pyyoutube.PlaylistItem]) -> None:
        """
        Updates the file names of the items in the playlist.

        Args:
            items (list[YoutubePlaylistItem]): The list of items to update.

        Returns:
            None
        """
        for item in items:
            item_file:CacheItem = youtube.youtube.cache_manager.get(youtube.youtube.AUDIO_FILES_CACHE_NAME, item.snippet.resourceId.videoId)
            if item_file is None:
                continue
            item_file.name = item.snippet.title

    def getMaxResolutionThumbnail(self, thumbnails:pyyoutube.Thumbnails) -> pyyoutube.models.common.Thumbnail | None:
        """
        Returns the highest resolution thumbnail from the provided thumbnails.

        Args:
            thumbnails (pyyoutube.Thumbnails): The thumbnails object containing various resolutions.

        Returns:
            pyyoutube.Thumbnail: The thumbnail with the highest resolution available.
        """
        return thumbnails.maxres or thumbnails.high or thumbnails.medium or thumbnails.standard or thumbnails.default
