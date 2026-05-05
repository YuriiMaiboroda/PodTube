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
import yt_dlp.utils
import threading

from configparser import ConfigParser
from enum import Enum
from pathlib import Path
from tornado import ioloop
from tornado.locks import Semaphore
import youtube.utils.config_utils
from youtube.utils.logging_utils import TaggedLogger, redirect_std_streams
from youtube.utils.cache import CacheManager, CacheItem
from youtube.utils.patch_ytdlp import ytdlp_ffmpeg_live_logs_context

__version__ = 'v2025.06.30.0'

class UnavailableType(Enum):
    STREAM = 1
    SPONSOR = 2
    LOGIN = 3
    REMOVED = 4
    PRIVATE = 5
    INTERNAL_ERROR = 500

class AudioFileCacheItem(CacheItem):
    def __init__(self, file_path:str, expire_duration:float = None):
        """
        Initializes an AudioFileCacheItem with the given file path and expiration time.
        Args:
            file_path (str): The path to the audio file.
            expire (datetime.datetime, optional): The expiration time for the cache item. Defaults to None.
        """
        self.__file_path = file_path
        self.__expire_duration = expire_duration or youtube.utils.config_utils.AUDIO_EXPIRATION_TIME
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
        with logger.tags('cleanup'):
            if os.path.exists(self.__file_path):
                try:
                    os.remove(self.__file_path)
                    logger.debug(f'Deleted audio file: {self.__file_path}')
                except Exception as ex:
                    logger.error(f'Error removing audio file {self.__file_path}: {ex}')

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
    def __init__(self, video_id: str, added: datetime.datetime, additional_data):
        """
        Initializes a ConversionQueueItem with a video ID and its conversion status.
        
        Args:
            video_id (str): The ID of the video to be converted.
            status (bool): The conversion status of the video. Defaults to False.
        """
        self.video_id = video_id
        self.added = added
        self.status = False
        self.additional_data = additional_data

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
                r'HTTP Error 403',
            ]) + r'\b',
            re.IGNORECASE
        ),
        unavailable_type=UnavailableType.LOGIN,
        message="HTTP Error 403: Forbidden"
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
    youtube.utils.config_utils.init_config(conf)

    ioloop.PeriodicCallback(
        callback=cleanup,
        callback_time=youtube.utils.config_utils.CLEANUP_PERIOD * 1000
    ).start()
    ioloop.PeriodicCallback(
        callback=convert_videos,
        callback_time=youtube.utils.config_utils.CONVERT_VIDEO_PERIOD * 1000
    ).start()

    for file in glob.glob(f'{youtube.utils.config_utils.AUDIO_DIR}/*.tmp'):
        os.remove(file)

    for file in glob.glob(f'{youtube.utils.config_utils.AUDIO_DIR}/*mp3'):
        cache_manager.set(
            AUDIO_FILES_CACHE_NAME,
            os.path.splitext(os.path.basename(file))[0],
            AudioFileCacheItem(file)
        )

def add_video_to_conversion_queue(video: str, additional_data) -> bool:
    """
    Adds a video to the conversion queue if it is not already present.

    Args:
        video (str): The ID of the video to be added to the conversion queue.
    """
    with logger.tags('convert_video'):
        global conversion_queue
        if video not in conversion_queue:
            conversion_queue[video] = ConversionQueueItem(video, datetime.datetime.now(), additional_data)
            # logger.info(f'Added video {video} to conversion queue')
            return True
        else:
            # logger.debug(f'Video {video} is already in the conversion queue')
            return False

def remove_video_from_conversion_queue(video: str) -> bool:
    """
    Removes a video from the conversion queue if it exists.

    Args:
        video (str): The ID of the video to be removed from the conversion queue.

    Returns:
        bool: True if the video was removed, False if it was not found in the queue.
    """
    with logger.tags('convert_video'):
        global conversion_queue
        if video in conversion_queue:
            conversion_queue.pop(video, None)
            # logger.info(f'Removed video {video} from conversion queue')
            return True
        else:
            # logger.debug(f'Video {video} is not in the conversion queue')
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
    return f'{youtube.utils.config_utils.AUDIO_DIR}/{video}.mp3'

def cleanup():
    """
    Clean up expired video links, playlist feeds, channel feeds, and channel name map.
    Delete audio files older than a certain time.
    Logs the items cleaned from each category.
    """

    with logger.tags('cleanup'):
        removed_counts = cache_manager.cleanup_expired_items()
        if removed_counts:
            for category, count in removed_counts.items():
                logger.info(f'Cleaned {count} items from {category}')

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
        with logger.tags(video):
            logger.info('Start downloading')

            try:
                await ioloop.IOLoop.current().run_in_executor(None, download_youtube_audio, video)
                logger.info('Successfully downloaded')
            except Exception as ex:
                errorType = UnavailableType.INTERNAL_ERROR
                errorMessage = str(ex) or "Internal error"

                if isinstance(ex, (
                    yt_dlp.utils.DownloadError,
                    yt_dlp.utils.ExtractorError,
                    PodtubeYoutubeError
                )):
                    for pattern in ERROR_PATTERNS:
                        if pattern.pattern.search(ex.msg):
                            errorType = pattern.unavailable_type
                            errorMessage = pattern.message
                            break

                logger.warning(f'Error converting file: {errorMessage}')
                video_link_cache:VideoLinkCacheItem = cache_manager.get_or_add(
                    VIEDO_LINKS_CACHE_NAME,
                    video,
                    lambda: VideoLinkCacheItem(None, datetime.datetime.now() + datetime.timedelta(hours=1))
                )
                video_link_cache.unavailable_type = errorType

                if errorType == UnavailableType.INTERNAL_ERROR:
                    raise
            finally:
                conversion_queue.pop(video, None)

def _on_task_done(task:asyncio.Task):
    with logger.tags('convert_video'):
        active_tasks.discard(task)
        try:
            task.result()
        except Exception as e:
            logger.error(f'Unhandled error in task: {e}', exc_info=e, stack_info=logger.isEnabledFor(logging.DEBUG))

class LoggerForYoutubeDL:
    _progress_re = re.compile(
        r"""
        ^\s*(?:\[[^\]]*\]\s*)*          # optional [tags]
        (?P<percent>\d{1,3}(?:\.\d+)?)%\s+of\s+
        (?P<size>.+?)\s+at\s+
        (?P<speed>.+?)\s+ETA\s+      # speed can contain spaces (e.g. "Unknown B/s")
        (?P<eta>\S+)
        """,
        re.VERBOSE
    )

    def __init__(self, progress_interval=1.0, progress_filter_enabled=True):
        self.progress_interval = progress_interval
        self.progress_filter_enabled = progress_filter_enabled

        self._progress_timer = None
        self._pending_progress_msg = None
        self._progress_lock = threading.RLock()

        self._seen_100_percent = False

    def debug(self, msg: str):
        # For compatibility with youtube-dl, both debug and info are passed into debug
        # You can distinguish them by the prefix '[debug] '
        if msg.startswith('[debug] '):
            logger.debug(msg)
        else:
            self.info(msg)

    def info(self, msg):
        if self._handle_progress_message(msg):
            return

        logger.info(msg)

    def warning(self, msg):
        logger.warning(msg)

    def error(self, msg):
        logger.error(msg)

    def _handle_progress_message(self, msg):
        if not self.progress_filter_enabled:
            return False

        match = self._progress_re.match(msg)
        if not match:
            return False

        percent = float(match.group('percent'))

        is_first_100_percent = percent >= 100.0 and not self._seen_100_percent

        if is_first_100_percent:
            self._seen_100_percent = True

        with self._progress_lock:
            self._pending_progress_msg = msg
            if is_first_100_percent or self._progress_timer is None:
                self.flush_progress(restart_timer=True)

        return True

    def flush_progress(self, restart_timer=False):
        with self._progress_lock:
            if self._progress_timer is not None:
                self._progress_timer.cancel()
                self._progress_timer = None

            if self._pending_progress_msg is not None:
                logger.info(self._pending_progress_msg)
                self._pending_progress_msg = None

            if restart_timer:
                self._start_progress_timer()

    def _start_progress_timer(self):
        with self._progress_lock:
            self._progress_timer = threading.Timer(
                self.progress_interval,
                self._safe_timer_callback
            )
            self._progress_timer.daemon = True
            self._progress_timer.start()

    def _safe_timer_callback(self):
        try:
            self._on_progress_timer()
        except Exception as ex:
            if self._progress_timer is not None:
                try:
                    self._progress_timer.cancel()
                finally:
                    self._progress_timer = None
            raise

    def _on_progress_timer(self):
        with self._progress_lock:
            has_pending = self._pending_progress_msg is not None
            self.flush_progress(restart_timer=has_pending)

def download_youtube_audio(video: str):
    """
    Asynchronous download audio form the youtube video.

    Args:
        video (str): Youtube video's key.
    """
    with logger.tags(video) as log_scope:
        video_queue_item = conversion_queue[video]
        yturl = get_youtube_url(video)
        logger.debug(f"Full URL: {yturl}")
        additional_data = video_queue_item.additional_data or {}

        # audio_file = f'{AUDIO_DIR}/{video}.mp3'
        # audio_file_temp = audio_file + '.temp'
        # video_file = None

        Path(youtube.utils.config_utils.AUDIO_DIR).mkdir(parents=True, exist_ok=True)
        logger.debug('Start downloading audio stream')

        def progress_hook(info):
            status = info['status']
            logger.debug(f'Downloading audio. Status {status}. {info=}\n\n')

        ytdlp_params = {
            'paths': {
                'home': f'{youtube.utils.config_utils.AUDIO_DIR}',
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
            'logger': LoggerForYoutubeDL(progress_interval=5),
            # 'progress_hooks': [progress_hook],
            'extractor_args': {
                'youtube': {
                    'lang': [(video_queue_item.additional_data or {}).get('hl', youtube.utils.config_utils.HL)],
                }
            },
            'extractor_retries': 1,
        }

        if youtube.utils.config_utils.HTTPS_PROXY is not None:
            ytdlp_params['proxy'] = youtube.utils.config_utils.HTTPS_PROXY,

        if youtube.utils.config_utils.COOKIES_FILE_PATH is not None:
            ytdlp_params['cookiefile'] = youtube.utils.config_utils.COOKIES_FILE_PATH,

        start_time = additional_data.get("start_time", None)
        end_time = additional_data.get("end_time", None)
        if start_time is not None or end_time is not None:
            start_time = float(start_time) if start_time is not None else 0
            end_time = float(end_time) if end_time is not None else float("inf")
            download_ranges = yt_dlp.download_range_func(
                [],
                [[start_time, end_time]]
            )

            ytdlp_params['download_ranges'] = download_ranges

        if youtube.utils.config_utils.FFMPEG_LIVE_LOGS:
            ppa: dict[list[str]] = ytdlp_params.setdefault('postprocessor_args', {})
            ffmpeg_args: list[str] = ppa.setdefault('ffmpeg', [])
            ffmpeg_args.extend(['-progress', 'pipe:2', '-nostats'])

        # This setup allows capturing logs from external tools (e.g. ffmpeg)
        # that write directly to sys.stderr or sys.stdout, and redirecting them to the Python logger.
        audio_name = None
        with (
            redirect_std_streams(logger),
            ytdlp_ffmpeg_live_logs_context(youtube.utils.config_utils.FFMPEG_LIVE_LOGS),
            yt_dlp.YoutubeDL(ytdlp_params) as ydl
        ):
            info = ydl.extract_info(yturl, download=False, process=False)
            if (info.get('live_status', None) in ['is_live', 'is_upcoming', 'is_premiere']):
                raise PodtubeYoutubeError(f'Video is Live Stream or Premiere: {video}')

            audio_name = info.get('title', None)
            if logger.isEnabledFor(logging.DEBUG):
                log_scope.add(
                    info.get('title',''),
                    info.get('channel_id',''),
                    info.get('channel',''),
                )
            ydl.params['mark_watched'] = (video_queue_item.additional_data or {}).get('mark_watched', youtube.utils.config_utils.MARK_WATCHED)

            ydl.download([yturl])

        logger.debug('Successfully downloaded audio')

        file_path = get_audio_file_path(video)
        cache_item = AudioFileCacheItem(file_path)
        cache_item.name = audio_name
        cache_manager.set(
            AUDIO_FILES_CACHE_NAME,
            os.path.basename(file_path),
            cache_item
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
