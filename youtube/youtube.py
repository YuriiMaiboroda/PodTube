"""
This file contains the implementation of handlers and functions related to interacting with YouTube
content. It includes classes such as VideoHandler, AudioHandler, ClearCacheHandler, and UserHandler,
which handle different types of requests related to YouTube content.
"""
import asyncio
import datetime
import glob
import logging
import os
import re
import yt_dlp

from configparser import ConfigParser
from enum import Enum
from pathlib import Path
from tornado import ioloop
from tornado.locks import Semaphore
import youtube.config_utils
from youtube.logging_utils import TaggedLogger, redirect_std_streams
from youtube.cache import CacheManager, CacheItem

__version__ = 'v2025.06.30.0'

class UnavailableType(Enum):
    STREAM = 1
    SPONSOR = 2
    LOGIN = 3
    REMOVED = 4
    PRIVATE = 5

class AudioFileCacheItem(CacheItem):
    def __init__(self, file_path:str, expire_duration:float = None):
        """
        Initializes an AudioFileCacheItem with the given file path and expiration time.
        Args:
            file_path (str): The path to the audio file.
            expire (datetime.datetime, optional): The expiration time for the cache item. Defaults to None.
        """
        self.__file_path = file_path
        self.__expire_duration = expire_duration or youtube.config_utils.AUDIO_EXPIRATION_TIME
        super().__init__(expire=datetime.datetime.fromtimestamp(os.path.getctime(self.__file_path) + self.__expire_duration))

    @property
    def file_path(self) -> str:
        """
        Returns the path to the audio file.
        
        Returns:
            str: The path to the audio file.
        """
        return self.__file_path
    
    @property
    def name(self) -> str:
        """
        Returns the name of the audio file.
        
        Returns:
            str: The name of the audio file.
        """
        base_name = super().name
        if base_name:
            name = base_name
        else:
            name = os.path.basename(self.__file_path)

        size = os.path.getsize(self.__file_path)
        if size > 2**40:
            size = str(size // 2**40) + 'TiB'
        elif size > 2**30:
            size = str(size // 2**30) + 'GiB'
        elif size > 2**20:
            size = str(size // 2**20) + 'MiB'
        elif size > 2**10:
            size = str(size // 2**10) + 'KiB'
        else:
            size = str(size) + 'B'
        return f'{name} ({size})'
    
    @name.setter
    def name(self, value: str):
        super(AudioFileCacheItem, self.__class__).name.fset(self, value)

    def clear(self):
        """
        Deletes the audio file from the filesystem.
        This method is called when the cache item is expired or cleared.
        """
        if os.path.exists(self.__file_path):
            try:
                os.remove(self.__file_path)
                logger.debug(f'Deleted audio file: {self.__file_path}', 'cleanup')
            except Exception as ex:
                logger.error(f'Error removing audio file {self.__file_path}: {ex}', 'cleanup')

class VideoLinkCacheItem(CacheItem):
    unavailable_type: UnavailableType | None = None

    """
    Represents a cache item for a YouTube video link.
    """
    def __init__(self, url: str, expire: datetime.datetime):
        """
        Initializes a VideoLinkCacheItem with the given URL and expiration time.
        
        Args:
            url (str): The URL of the video.
            expire (datetime.datetime, optional): The expiration time for the cache item. Defaults to None.
        """
        self.url = url
        super().__init__(expire=expire)

class PodtubeYoutubeError(Exception):
    """Base exception for Potube Youtube errors."""
    msg = None

    def __init__(self, msg=None):
        if msg is not None:
            self.msg = msg
        elif self.msg is None:
            self.msg = type(self).__name__
        super().__init__(self.msg)

class ConversionQueueItem:
    """
    Represents an item in the conversion queue.
    Contains the video ID and its conversion status.
    """
    def __init__(self, video_id: str, added: datetime.datetime):
        """
        Initializes a ConversionQueueItem with a video ID and its conversion status.
        
        Args:
            video_id (str): The ID of the video to be converted.
            status (bool): The conversion status of the video. Defaults to False.
        """
        self.video_id = video_id
        self.added = added
        self.status = False

class ErrorPattern:
    def __init__(self, pattern:re.Pattern[str], unavailable_type: UnavailableType, message: str):
        """
        Initializes an ErrorPattern instance with a regex pattern, an unavailable type, and a message.

        Args:
            pattern (re.Pattern[str]): The regex pattern to match error messages.
            unavailable_type (UnavailableType): The type of unavailability associated with this error.
            message (str): The message to be displayed when this error occurs.
        """
        self.pattern = pattern
        self.unavailable_type = unavailable_type
        self.message = message

ERROR_PATTERNS:list[ErrorPattern] = [
    ErrorPattern(
        pattern=re.compile(
            r'\b' + r'\b|\b'.join([
                r'live',
                r'подія в прямому ефірі',
                r'прем\’єра',
                r'трансляція'
            ]) + r'\b',
            re.IGNORECASE
        ),
        unavailable_type=UnavailableType.STREAM,
        message="Video is Live Stream or Premiere"
    ),
    ErrorPattern(
        pattern=re.compile(
            r'\b' + r'\b|\b'.join([
                r'спонсор.*?',
            ]) + r'\b',
            re.IGNORECASE
        ),
        unavailable_type=UnavailableType.SPONSOR,
        message="Need to be a sponsor to access the video"
    ),
    ErrorPattern(
        pattern=re.compile(
            r'\b' + r'\b|\b'.join([
                r'увійдіть',
            ]) + r'\b',
            re.IGNORECASE
        ),
        unavailable_type=UnavailableType.LOGIN,
        message="Login required"
    ),
    ErrorPattern(
        pattern=re.compile(
            r'\b' + r'\b|\b'.join([
                r'вилучив',
            ]) + r'\b',
            re.IGNORECASE
        ),
        unavailable_type=UnavailableType.REMOVED,
        message="Removed video"
    ),
    ErrorPattern(
        pattern=re.compile(
            r'\b' + r'\b|\b'.join([
                r'приватне',
            ]) + r'\b',
            re.IGNORECASE
        ),
        unavailable_type=UnavailableType.PRIVATE,
        message="Private video"
    ),
]

conversion_queue:dict[str, ConversionQueueItem] = {}
converting_semaphore = Semaphore(3)
active_tasks:set[asyncio.Task] = set()

logger:TaggedLogger = TaggedLogger(__name__)
cache_manager:CacheManager = CacheManager()

VIEDO_LINKS_CACHE_NAME = 'video_links'
AUDIO_FILES_CACHE_NAME = 'audio_files'

def init(conf: ConfigParser):
    """
    Initializes the configuration settings for the system.

    Args:
        conf (ConfigParser): The configuration parser object.

    Returns:
        None
    """
    youtube.config_utils.init_config(conf)

    ioloop.PeriodicCallback(
        callback=cleanup,
        callback_time=youtube.config_utils.CLEANUP_PERIOD * 1000
    ).start()
    ioloop.PeriodicCallback(
        callback=convert_videos,
        callback_time=youtube.config_utils.CONVERT_VIDEO_PERIOD * 1000
    ).start()

    for file in glob.glob(f'{youtube.config_utils.AUDIO_DIR}/*.tmp'):
        os.remove(file)

    for file in glob.glob(f'{youtube.config_utils.AUDIO_DIR}/*mp3'):
        cache_manager.set(
            AUDIO_FILES_CACHE_NAME,
            os.path.splitext(os.path.basename(file))[0],
            AudioFileCacheItem(file)
        )

def add_video_to_conversion_queue(video: str) -> bool:
    """
    Adds a video to the conversion queue if it is not already present.

    Args:
        video (str): The ID of the video to be added to the conversion queue.
    """
    global conversion_queue
    if video not in conversion_queue:
        conversion_queue[video] = ConversionQueueItem(video, datetime.datetime.now())
        # logger.info(f'Added video {video} to conversion queue', 'convert_video')
        return True
    else:
        # logger.debug(f'Video {video} is already in the conversion queue', 'convert_video')
        return False
    
def remove_video_from_conversion_queue(video: str) -> bool:
    """
    Removes a video from the conversion queue if it exists.

    Args:
        video (str): The ID of the video to be removed from the conversion queue.

    Returns:
        bool: True if the video was removed, False if it was not found in the queue.
    """
    global conversion_queue
    if video in conversion_queue:
        conversion_queue.pop(video, None)
        # logger.info(f'Removed video {video} from conversion queue', 'convert_video')
        return True
    else:
        # logger.debug(f'Video {video} is not in the conversion queue', 'convert_video')
        return False
    
def is_video_in_conversion_queue(video: str) -> bool:
    """
    Checks if a video is already in the conversion queue.

    Args:
        video (str): The ID of the video to check.

    Returns:
        bool: True if the video is in the conversion queue, False otherwise.
    """
    global conversion_queue
    return video in conversion_queue

def get_audio_file_path(video: str) -> str:
    """
    Returns the path to the audio file for a given video ID.

    Args:
        video (str): The ID of the video.

    Returns:
        str: The path to the audio file.
    """
    return f'{youtube.config_utils.AUDIO_DIR}/{video}.mp3'

def cleanup():
    """
    Clean up expired video links, playlist feeds, channel feeds, and channel name map.
    Delete audio files older than a certain time.
    Logs the items cleaned from each category.
    """

    removed_counts = cache_manager.cleanup_expired_items()
    if removed_counts:
        for category, count in removed_counts.items():
            logger.info(f'Cleaned {count} items from {category}', 'cleanup')

async def convert_videos():
    global active_tasks
    if len(conversion_queue) == 0:
        return
    pending = [
        key for key in conversion_queue.keys()
        if not conversion_queue[key].status
    ]
    for video in pending:
        if any(t.get_name() == video for t in active_tasks):
            continue

        task = asyncio.create_task(convert_video_async(video), name=video)
        active_tasks.add(task)

        task.add_done_callback(_on_task_done)

async def convert_video_async(video):
    global conversion_queue
    global converting_semaphore
    conversion_queue[video].status = True
    async with converting_semaphore:
        logger.info('Start downloading', video)

        try:
            await ioloop.IOLoop.current().run_in_executor(None, download_youtube_audio, video)
            logger.info('Successfully downloaded', video)
        except (yt_dlp.utils.DownloadError, yt_dlp.utils.ExtractorError, PodtubeYoutubeError) as ex:
            errorType = None
            errorMessage = None
            
            for pattern in ERROR_PATTERNS:
                if pattern.pattern.search(ex.msg):
                    errorType = pattern.unavailable_type
                    errorMessage = pattern.message
                    break

            if errorType:
                logger.error(f'Error converting file: {errorMessage}', video)
                video_link_cache:VideoLinkCacheItem = cache_manager.get_or_add(
                    VIEDO_LINKS_CACHE_NAME,
                    video,
                    lambda: VideoLinkCacheItem(None, datetime.datetime.now() + datetime.timedelta(hours=1))
                )
                video_link_cache.unavailable_type = errorType
            else:
                raise
        finally:
            conversion_queue.pop(video, None)

def _on_task_done(task:asyncio.Task):
    active_tasks.discard(task)
    try:
        task.result()
    except Exception as e:
        logger.error(f'Unhandled error in task: {e}', 'convert_video', e, logger.isEnabledFor(logging.DEBUG))

class LoggerForYoutubeDL:
    def __init__(self, videoId: str):
        self.videoId = videoId

    def debug(self, msg):
        # For compatibility with youtube-dl, both debug and info are passed into debug
        # You can distinguish them by the prefix '[debug] '
        if msg.startswith('[debug] '):
            logger.debug(msg, self.videoId)
        else:
            self.info(msg)

    def info(self, msg):
        logger.info(msg, self.videoId)

    def warning(self, msg):
        logger.warning(msg, self.videoId)

    def error(self, msg):
        logger.error(msg, self.videoId)

def download_youtube_audio(video: str):
    """
    Asynchronous download audio form the youtube video.

    Args:
        video (str): Youtube video's key.
    """
    yturl = get_youtube_url(video)
    logger.debug(f"Full URL: {yturl}", video)

    # audio_file = f'{AUDIO_DIR}/{video}.mp3'
    # audio_file_temp = audio_file + '.temp'
    # video_file = None

    Path(youtube.config_utils.AUDIO_DIR).mkdir(parents=True, exist_ok=True)
    logger.debug('Start downloading audio stream', video)

    def progress_hook(info):
        status = info['status']
        logger.debug(f'Downloading audio. Status {status}. {info=}\n\n', video)

    ydl = yt_dlp.YoutubeDL({
        'paths': {
            'home': f'{youtube.config_utils.AUDIO_DIR}',
            'temp': f'tmp'
        },
        'outtmpl': {
            'home': f'{video}',
            'temp': f'{video}'
        },
        'verbose': logger.isEnabledFor(logging.DEBUG),
        'format': 'm4a/bestaudio/best',
        'postprocessors': [{  # Extract audio using ffmpeg
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
        }],
        'logger': LoggerForYoutubeDL(video),
        # 'progress_hooks': [progress_hook],
        'proxy': youtube.config_utils.HTTPS_PROXY,
        'cookiefile': youtube.config_utils.COOKIES_FILE_PATH,
        'extractor_args': {
            'youtube': {
                'lang': ['uk'],
                'player_skip': ['webpage'],
                # 'bypass_native_jsi': True,
                # 'deno_no_jitless': True,
            }
        },
        'extractor_retries': 1,
        'mark_watched': True,
    })

    # This setup allows capturing logs from external tools (e.g. ffmpeg)
    # that write directly to sys.stderr or sys.stdout, and redirecting them to the Python logger.
    with redirect_std_streams(logger):
        info = ydl.extract_info(yturl, download=False, process=False)
        if (info.get('live_status', None) in ['is_live', 'is_upcoming', 'is_premiere']):
            raise PodtubeYoutubeError(f'Video is Live Stream or Premiere: {video}')

        ydl.download([yturl])

    logger.debug('Successfully downloaded audio', video)

    file_path = get_audio_file_path(video)
    cache_manager.set(
        AUDIO_FILES_CACHE_NAME,
        os.path.basename(file_path),
        AudioFileCacheItem(file_path)
    )

def get_youtube_url(video: str) -> str:
    """
    Function to get the YouTube URL for a given video.

    Args:
    - video: The video ID for which the URL is needed.

    Returns:
    - The YouTube URL for the given video.
    """
    return f"https://www.youtube.com/watch?v={video}"
