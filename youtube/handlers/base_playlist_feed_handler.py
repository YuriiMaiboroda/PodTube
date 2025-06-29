from feedgen.feed import FeedGenerator
from feedgen.ext.podcast import PodcastExtension
from feedgen.ext.podcast_entry import PodcastEntryExtension
import datetime
import isodate
import requests
from tornado import ioloop, web

from youtube.cache import CacheItem
import youtube.config_utils
from youtube.handlers.youtube_response.videos_structure import YoutubeVideoItemContentDetails, YoutubeVideoItemLiveStreamingDetails, YoutubeVideoItemStatus, YoutubeVideosResponse
from youtube.logging_utils import TaggedLogger
from youtube.youtube import cache_manager, __version__
from youtube.handlers.youtube_response.playlist_items_structure import YoutubePlaylistItem, YoutubePlaylistItemsResponse
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

        
class BasePlaylistFeedHandler(web.RequestHandler):
    def initialize(self, logger:TaggedLogger, audio_handler_path:str):
        super().initialize()
        self.logger = logger
        self.audio_handler_path = audio_handler_path

    async def head(self, playlist):
        """
        A coroutine function that sets the header for the given playlist.

        Args:
            self: The instance of the class.
            playlist: The playlist for which the header is being set.

        Returns:
            None
        """
        self.set_header('Content-type', 'application/rss+xml')
        self.set_header('Accept-Ranges', 'bytes')

    def prepare(self):
        self.set_header('Content-type', 'application/rss+xml')
        self.set_header('charset', 'utf-8')

    def try_response_from_cache(self, item_name: str) -> bool:
        """
        Attempts to retrieve a feed from the cache.
        Args:
            item_name (str): The name of the item to retrieve from the cache.
        """
        channel_feed:FeedCacheItem = cache_manager.get(FEED_CACHE_NAME, item_name)
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
        cache_manager.set(
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
            __version__,
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
            max_items = self.get_argument("max_items", "-1")
            max_items = int(max_items)
            self.logger.info(f"Will grab maximum {max_items} videos", log_tag)
        except ValueError:
            self.logger.error(f"Failed parse max_count to int: {max_items}", log_tag)
            max_items = 1

        playlist_items_response:YoutubePlaylistItemsResponse = YoutubePlaylistItemsResponse()
        playlist_items_response.nextPageToken = "first_page"
        items_count = 0
        while playlist_items_response.get('nextPageToken', None) and (max_items < 1 or items_count < max_items):
            next_page = playlist_items_response.nextPageToken
            if next_page == 'first_page':
                next_page = None
            payload = {
                'part': 'snippet',
                'maxResults': 50 if max_items < 1 or max_items - items_count > 50 else max_items - items_count,
                'playlistId': playlist,
                'key': youtube.config_utils.KEY,
                'pageToken': next_page
            }
            request = await ioloop.IOLoop.current().run_in_executor(
                None,
                lambda: requests.get('https://www.googleapis.com/youtube/v3/playlistItems', params=payload, proxies=youtube.config_utils.PROXIES)
            )
            playlist_items_response:YoutubePlaylistItemsResponse = request.json()
            if request.status_code == 200:
                self.logger.debug('Downloaded Channel Information', log_tag)
            elif request.status_code == 404:
                self.logger.debug(f'Playlist not found. {playlist_items_response=}', log_tag)
                if playlist_items_response.items is None:
                    playlist_items_response.items = []
            else:
                # self.logger.debug(f'Request not 200: {payload=}; {request=}', log_tag)
                self.logger.error(f'Error Downloading Channel: {request.reason}', log_tag)
                return None
            
            payload = {
                'part': 'contentDetails,liveStreamingDetails,status',
                'id': ','.join(item.snippet.resourceId.videoId for item in playlist_items_response.items),
                'key': youtube.config_utils.KEY,
            }
            request = await ioloop.IOLoop.current().run_in_executor(
                None,
                lambda: requests.get('https://www.googleapis.com/youtube/v3/videos', params=payload, proxies=youtube.config_utils.PROXIES)
            )
            
            all_video_contentDetails:YoutubeVideoItemContentDetails = None
            all_video_status:YoutubeVideoItemStatus = None
            all_video_liveStreamingDetails:YoutubeVideoItemLiveStreamingDetails = None

            if request.status_code == 200:
                channel_response:YoutubeVideosResponse = request.json()
                all_video_contentDetails = {item.id: item.contentDetails or None for item in channel_response.items}
                all_video_status = {item.id: item.get('status', None) for item in channel_response.items}
                all_video_liveStreamingDetails = {item.id: item.get('liveStreamingDetails', None) for item in channel_response.items}
            elif request.status_code != 404:
                self.logger.error(f'Error Downloading info about video: {request.reason}', log_tags)

            self.update_file_names(playlist_items_response.items)

            for item in playlist_items_response.items:
                snippet = item.snippet
                current_video = snippet.resourceId.videoId
                log_tags = [log_tag, current_video]

                video_contentDetails:YoutubeVideoItemContentDetails = all_video_contentDetails.get(current_video, None) if all_video_contentDetails else None
                video_status:YoutubeVideoItemStatus = all_video_status.get(current_video, None) if all_video_status else None
                video_liveStreamingDetails:YoutubeVideoItemLiveStreamingDetails = all_video_liveStreamingDetails.get(current_video, None) if all_video_liveStreamingDetails else None

                if video_status is not None:
                    if video_status.get('privacyStatus', 'public').lower() == 'private':
                        continue
                elif 'private' in snippet.title.lower():
                    continue

                if snippet.channelTitle is None:
                    snippet.channelTitle = snippet.get('channelId', f'Unknown Channel. {playlist}')

                self.logger.debug(f'{snippet.title}', log_tags)
                items_count += 1

                fe = fg.add_entry()
                fe_podcast:PodcastEntryExtension = getattr(fe, podcast_extension_name)
                fe.title(snippet.title)
                fe.id(current_video)
                icon = max(
                    snippet.thumbnails,
                    key=lambda x: snippet.thumbnails[x].width)
                fe_podcast.itunes_image(snippet.thumbnails[icon].url)
                fe.updated(snippet.publishedAt)
                final_url = f'{self.request.protocol}://{self.request.host}{self.audio_handler_path}{current_video}'
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
                        stream_infos.append(f"Live stream scheduled to start at {video_liveStreamingDetails.scheduledStartTime}")
                    if video_liveStreamingDetails.actualStartTime:
                        stream_infos.append(f"Live stream started at {video_liveStreamingDetails.actualStartTime}")
                    if video_liveStreamingDetails.actualEndTime:
                        stream_infos.append(f"Live stream ended at {video_liveStreamingDetails.actualEndTime}")
                    if stream_infos:
                        description = f"{description}\n\nLive stream information:\n" + "\n".join(stream_infos)

                description = description + f'\n\n{final_url}'
                fe_podcast.itunes_summary(description)
                fe.description(description)

                duration = video_contentDetails and video_contentDetails.get('duration', None) or None
                if duration is not None:
                    duration:datetime.timedelta = isodate.parse_duration(duration)
                    fe_podcast.itunes_duration(int(duration.total_seconds()))
            

        self.logger.debug(f"Got {items_count} videos", log_tag)

        feed = fg.rss_str()
        
        self.save_feed_to_cache(cache_id, title, feed)

        return feed
    
    def update_file_names(self, items:list[YoutubePlaylistItem]):
        """
        Updates the file names of the items in the playlist.

        Args:
            items (list[YoutubePlaylistItem]): The list of items to update.

        Returns:
            None
        """
        for item in items:
            item_file:CacheItem = cache_manager.get(youtube.youtube.AUDIO_FILES_CACHE_NAME, item.snippet.resourceId.videoId)
            if item_file is None:
                continue
            item_file.name = item.snippet.title