"""
This file contains the implementation of handlers and functions related to interacting with YouTube
content. It includes classes such as VideoHandler, AudioHandler, ClearCacheHandler, and UserHandler,
which handle different types of requests related to YouTube content.
"""
import datetime
import logging
import os
import psutil
import time
import glob
import requests
import utils
from configparser import ConfigParser, NoSectionError, NoOptionError
from pathlib import Path
from feedgen.feed import FeedGenerator
from pytube import YouTube, exceptions
from tornado import gen, httputil, ioloop, iostream, process, web
from tornado.locks import Semaphore

KEY = None
CLEANUP_PERIOD = None
CONVERT_VIDEO_PERIOD = None
AUDIO_EXPIRATION_TIME = None
AUTOLOAD_NEWEST_AUDIO = None
HTTP_PROXY = None
HTTPS_PROXY = None
PROXIES = None
USE_OAUTH = False

AUDIO_DIR = "./audio"
VIDEO_DIR = "./video"

video_links = {}
playlist_feed = {}
channel_feed = {}
channel_name_to_id = {}

__version__ = 'v2023.04.21.5'

conversion_queue = {}
converting_lock = Semaphore(2)

def get_env_or_config_option(conf: ConfigParser, env_name: str, config_name: str, default_value = None):
    """
    Get the value of a configuration option from the given ConfigParser object, either from the environment variables or from the configuration file.
    
    Args:
        conf (ConfigParser): The ConfigParser object containing the configuration options.
        env_name (str): The name of the environment variable to check for the configuration option.
        config_name (str): The name of the configuration option in the configuration file.
        default_value: The default value to return if the configuration option is not found.

    Returns:
        The value of the configuration option, or the default value if the option is not found.
    """
    return utils.get_env_or_config_option(conf, env_name, config_name, "youtube", default_value=default_value)

def init(conf: ConfigParser):
    """
    Initializes the configuration settings for the system.

    Args:
        conf (ConfigParser): The configuration parser object.

    Returns:
        None
    """
    global KEY, CLEANUP_PERIOD, CONVERT_VIDEO_PERIOD, AUDIO_EXPIRATION_TIME, AUTOLOAD_NEWEST_AUDIO, HTTP_PROXY, HTTPS_PROXY, PROXIES, USE_OAUTH
    KEY                   = str(get_env_or_config_option(conf, "YT_API_KEY"               , "yt_api_key"               , default_value=None))
    HTTP_PROXY            =     get_env_or_config_option(conf, "YT_HTTP_PROXY"            , "yt_http_proxy"            , default_value=None)
    HTTPS_PROXY           =     get_env_or_config_option(conf, "YT_HTTPS_PROXY"           , "yt_https_proxy"           , default_value=None)
    CLEANUP_PERIOD        = int(get_env_or_config_option(conf, "YT_CLEANUP_PERIOD"        , "yt_cleanup_period"        , default_value=600000)) # 10 minutes
    CONVERT_VIDEO_PERIOD  = int(get_env_or_config_option(conf, "YT_CONVERT_VIDEO_PERIOD"  , "yt_convert_video_period"  , default_value=1000)) # 1 second
    AUDIO_EXPIRATION_TIME = int(get_env_or_config_option(conf, "YT_AUDIO_EXPIRATION_TIME" , "yt_audio_expiration_time" , default_value=259200000)) # 3 days
    AUTOLOAD_NEWEST_AUDIO =     get_env_or_config_option(conf, "YT_AUTOLOAD_NEWEST_AUDIO" , "yt_autoload_newest_audio" , default_value=True)
    USE_OAUTH             =     get_env_or_config_option(conf, "YT_USE_OAUTH"             , "yt_use_oauth"             , default_value=False)

    AUTOLOAD_NEWEST_AUDIO = utils.convert_to_bool(AUTOLOAD_NEWEST_AUDIO)
    USE_OAUTH = utils.convert_to_bool(USE_OAUTH)

    if any(proxy is not None for proxy in [HTTP_PROXY, HTTPS_PROXY]):
        PROXIES = {}
    if HTTP_PROXY is not None:
        PROXIES["http"] = HTTP_PROXY
    if HTTPS_PROXY is not None:
        PROXIES["https"] = HTTPS_PROXY

    ioloop.PeriodicCallback(
        callback=cleanup,
        callback_time=CLEANUP_PERIOD
    ).start()
    ioloop.PeriodicCallback(
        callback=convert_videos,
        callback_time=CONVERT_VIDEO_PERIOD
    ).start()

def set_key(new_key: str = None):
    """
    Sets the value of the global variable `KEY` to the provided `new_key`.
    
    :param new_key: A string representing the new value for the `KEY` variable.
    :type new_key: str
    
    :return: None
    """
    global KEY
    KEY = new_key

def cleanup():
    """
    Clean up expired video links, playlist feeds, channel feeds, and channel name map.
    Delete audio files older than a certain time.
    Logs the items cleaned from each category.
    """
    # Globals
    global video_links, playlist_feed, channel_name_to_id, channel_feed, AUDIO_EXPIRATION_TIME, AUDIO_DIR, VIDEO_DIR
    current_time = datetime.datetime.now()
    # Video Links
    video_links_length = len(video_links)
    video_links = {
        video:
            info
            for video, info in video_links.items()
            if info['expire'] > current_time
    }
    video_links_length -= len(video_links)
    if video_links_length:
        logging.info('Cleaned %s items from video list', video_links_length)
    # Playlist Feeds
    playlist_feed_length = len(playlist_feed)
    playlist_feed = {
        playlist:
            info
            for playlist, info in playlist_feed.items()
            if info['expire'] > current_time
    }
    playlist_feed_length -= len(playlist_feed)
    if playlist_feed_length:
        logging.info(
            'Cleaned %s items from playlist feeds',
            playlist_feed_length
        )
    # Channel Feeds
    channel_feed_length = len(channel_feed)
    channel_feed = {
        channel:
            info
            for channel, info in channel_feed.items()
            if info['expire'] > current_time
    }
    channel_feed_length -= len(channel_feed)
    if channel_feed_length:
        logging.info(
            'Cleaned %s items from channel feeds',
            channel_feed_length
        )
    # Channel Feeds
    channel_name_to_id_length = len(channel_name_to_id)
    channel_name_to_id = {
        channel:
            info
            for channel, info in channel_name_to_id.items()
            if info['expire'] > current_time
    }
    channel_name_to_id_length -= len(channel_name_to_id)
    if channel_name_to_id_length:
        logging.info(
            'Cleaned %s items from channel name map',
            channel_name_to_id_length
        )
    # Space Check
    expired_time = time.time() - (AUDIO_EXPIRATION_TIME / 1000)
    for f in sorted(glob.glob(f'{AUDIO_DIR}/*mp3') + glob.glob(f'{VIDEO_DIR}/*mp4'), key=lambda a_file: os.path.getctime(a_file)):
        ctime = os.path.getctime(f)
        if ctime <= expired_time:
            try:
                os.remove(f)
                logging.info('Deleted %s', f)
            except Exception as ex:
                logging.error('Error remove file %s: %s', f, ex)
        else:
            break

@gen.coroutine
def convert_videos():
    """
    Asynchronous function to convert videos. 
    This function checks the conversion queue for pending videos, selects the next video to convert, 
    and then initiates the conversion process. 
    If an error occurs during the conversion, it handles the error and cleans up any temporary files.
    """
    global conversion_queue
    global converting_lock
    if len(conversion_queue) == 0:
        return
    try:
        remaining = [
            key
            for key in conversion_queue.keys()
            if not conversion_queue[key]['status']
        ]
        video = sorted(
            remaining,
            key=lambda v: conversion_queue[v]['added']
        )[0]
        conversion_queue[video]['status'] = True
    except Exception:
        return
    with (yield converting_lock.acquire()):
        logging.info('Start downloading: %s', video)
        try:
            yield download_youtube_audio(video)
            logging.info('Successfully downloaded: %s', video)
        except Exception as ex:
            if isinstance(ex, (exceptions.LiveStreamError, exceptions.VideoUnavailable)):
                errorType = "Video is Live Stream" if isinstance(ex, exceptions.LiveStreamError) else "Video is Unavailable"
                logging.error('Error converting file: %s', errorType)
                if video not in video_links:
                    video_links[video] = {
                        'url': None,
                        'expire': datetime.datetime.now() + datetime.timedelta(hours=6)
                    }
                video_links[video]['unavailable'] = True
            else:
                logging.exception('Error converting file: %s', ex)
        finally:
            del conversion_queue[video]

async def download_youtube_audio(video: str):
    """
    Asynchronous download audio form the youtube video.

    Args:
        video (str): Youtube video's key.
    """
    global PROXIES, USE_OAUTH, AUDIO_DIR
    yturl = get_youtube_url(video)
    logging.debug("Full URL: %s", yturl)

    audio_file = f'{AUDIO_DIR}/{video}.mp3'
    audio_file_temp = audio_file + '.temp'
    video_file = None

    try:
        Path(AUDIO_DIR).mkdir(parents=True, exist_ok=True)
        logging.debug('Start downloading audio stream: %s', video)

        yt = YouTube(
            yturl,
            use_oauth=USE_OAUTH,
            allow_oauth_cache=USE_OAUTH,
            proxies=PROXIES
        )
        if logging.root.isEnabledFor(logging.DEBUG):
            yt.register_on_progress_callback(
                lambda stream, chunk, bytes_remaining:
                    logging.debug('Downloading audio %s: downloaded %s, remain %s', video, len(chunk), bytes_remaining)
            )
        yt.streams.get_audio_only().download(filename=audio_file_temp, max_retries=5)

        try:
            os.rename(audio_file_temp, audio_file)
        except (OSError, SystemError) as e:
            logging.error('Error rename temp file: %s', e)
            raise e

        logging.debug('Successfully downloaded audio: %s', video)

    except (OSError, SystemError) as e:
        raise e

    except Exception as e:
        logging.debug( "Error returned by Youtube: %s", e )
        try:
            try:
                if os.path.exists(audio_file_temp):
                    os.remove(audio_file_temp)
                if os.path.exists(audio_file):
                    os.remove(audio_file)
            except Exception as e2:
                logging.error('Error remove file: %s', e2)
                raise e2

            video_file = download_youtube_video(video)

            logging.debug('Start converting video: %s', video)
            ffmpeg_process = process.Subprocess([
                'ffmpeg',
                '-loglevel', 'panic',
                '-y',
                '-i', video_file,
                '-f', 'mp3', audio_file_temp
            ])
            await ffmpeg_process.wait_for_exit()

            try:
                os.rename(audio_file_temp, audio_file)
            except (OSError, SystemError) as e:
                logging.error('Error rename temp file: %s', e)
                raise e

            logging.debug('Successfully converted video: %s', video)

        except Exception as e2:
            try:
                if os.path.exists(audio_file):
                    os.remove(audio_file)
            except Exception as e3:
                logging.error('Error remove temp file: %s', e3)
            raise e2

    finally:
        try:
            if os.path.exists(audio_file_temp):
                os.remove(audio_file_temp)
            if video_file and os.path.exists(video_file):
                os.remove(video_file)
        except Exception as e:
            logging.error('Error remove temp file: %s', e)

def download_youtube_video(video) -> str:
    """
    Download video from YouTube.

    Args:
        video (str): Youtube video's key.
    
    Return (str):
        Path to downloaded video file.
    """
    global PROXIES, USE_OAUTH, VIDEO_DIR
    yturl = get_youtube_url(video)
    logging.debug("Full URL: %s", yturl)

    video_file = f'{VIDEO_DIR}/{video}.mp4'
    video_file_temp = video_file + '.temp'

    try:
        Path(VIDEO_DIR).mkdir(parents=True, exist_ok=True)
        logging.debug('Start downloading video stream: %s', video)
        yt = YouTube(
            yturl,
            use_oauth=USE_OAUTH,
            allow_oauth_cache=USE_OAUTH,
            proxies=PROXIES
        )
        if logging.root.isEnabledFor(logging.DEBUG):
            yt.register_on_progress_callback(
                lambda stream, chunk, bytes_remaining:
                    logging.debug('Downloading video %s: downloaded %s, remain %s', video, len(chunk), bytes_remaining)
            )
        logging.debug( "Stream count: %s", len(yt.streams))
        stream = yt.streams.get_by_resolution("720p", progressive=False)
        if not stream:
            stream = yt.streams.get_highest_resolution(progressive=False)
        stream.download(filename=video_file_temp, max_retries=5)

        os.rename(video_file_temp, video_file)
        logging.debug('Successfully downloaded video: %s', video)

    except Exception as e:
        try:
            if os.path.exists(video_file):
                os.remove(video_file)
        except Exception as ex2:
            logging.error('Error remove temp file: %s', ex2)
        raise e

    finally:
        try:
            if os.path.exists(video_file_temp):
                os.remove(video_file_temp)
        except Exception as ex2:
            logging.error('Error remove temp file: %s', ex2)
    return video_file

def get_youtube_url(video: str) -> str:
    """
    Function to get the YouTube URL for a given video.

    Args:
    - video: The video ID for which the URL is needed.

    Returns:
    - The YouTube URL for the given video.
    """
    return "https://www.youtube.com/watch?v=%s" % video

class ChannelHandler(web.RequestHandler):
    def initialize(self, video_handler_path: str, audio_handler_path: str, default_item_type: str = "audio"):
        """
        Initializes the object with the given video and audio handler paths.

        :param video_handler_path: A string representing the path to the video handler.
        :param audio_handler_path: A string representing the path to the audio handler.
        :param default_item_type: Default type of elements. 'audio' or 'video'
        """
        self.video_handler_path = video_handler_path
        self.audio_handler_path = audio_handler_path
        self.default_item_type = default_item_type

    @gen.coroutine
    def head(self):
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

    @gen.coroutine
    def get(self, channel):
        """
        A coroutine function that retrieves videos from a specified YouTube channel and generates an RSS feed. 
        Parameters:
            - self: the class instance
            - channel: the channel from which to retrieve videos
        Return types:
            - None
        """
        global KEY, PROXIES
        max_pages = self.get_argument('max', None)
        if max_pages:
            logging.info("Will grab videos from a maximum of %s pages" % max_pages)

        try:
            max_items = self.get_argument("max_items", "-1")
            max_items = int(max_items)
            logging.info("Will grab maximum %s videos" % max_items)
        except ValueError:
            logging.error(f"Failed parse max_count to int: {max_items}")
            max_items = 1

        channel = channel.split('/')
        if len(channel) < 2:
            channel.append(self.default_item_type)
        channel_name = ['/'.join(channel)]
        self.set_header('Content-type', 'application/rss+xml')
        if channel_name[0] in channel_feed and channel_feed[channel_name[0]]['expire'] > datetime.datetime.now():
            self.write(channel_feed[channel_name[0]]['feed'])
            self.finish()
            return
        fg = None
        video = None
        calls = 0
        payload = {
            'part': 'snippet,contentDetails',
            'maxResults': 1,
            'fields': 'items',
            'order': 'date',
            'id': channel[0],
            'key': KEY
        }
        request = requests.get(
            'https://www.googleapis.com/youtube/v3/channels',
            params=payload,
            proxies=PROXIES
        )
        calls += 1
        if request.status_code != 200:
            payload = {
                'part': 'snippet,contentDetails',
                'maxResults': 1,
                'fields': 'items',
                'order': 'date',
                'forUsername': channel[0],
                'key': KEY
            }
            request = requests.get(
                'https://www.googleapis.com/youtube/v3/channels',
                params=payload,
                proxies=PROXIES
            )
            calls += 1
        if request.status_code == 200:
            logging.debug('Downloaded Channel Information')
        else:
            logging.error('Error Downloading Channel: %s', request.reason)
            self.send_error(reason='Error Downloading Channel')
            return
        response = request.json()
        channel_data = response['items'][0]
        if channel[0] != channel_data['id']:
            channel[0] = channel_data['id']
            channel_name.append('/'.join(channel))
        #get upload playlist
        channel_upload_list = channel_data['contentDetails']['relatedPlaylists']['uploads']
        channel_data = channel_data['snippet']

        fg = FeedGenerator()
        fg.load_extension('podcast')
        fg.generator(
            'PodTube (python-feedgen)',
            __version__,
            'https://github.com/amckee/PodTube'
        )
        if 'title' not in channel_data:
            logging.info("Channel title not found")
            channel_data['title'] = channel[0]
        logging.info(
            'Channel: %s (%s)',
            channel[0],
            channel_data['title']
        )
        icon = max(
            channel_data['thumbnails'],
            key=lambda x: channel_data['thumbnails'][x]['width']
        )
        fg.title(channel_data['title'])
        fg.id(f'{self.request.protocol}://{self.request.host}{self.request.uri}')
        fg.description(channel_data['description'] or ' ')
        fg.author(
            name='Podtube',
            email='armware+podtube@gmail.com',
            uri='https://github.com/amckee/PodTube')
        fg.podcast.itunes_author(channel_data['title'])
        fg.image(channel_data['thumbnails'][icon]['url'])
        fg.link(
            href=f'https://www.youtube.com/channel/%s' % channel[0],
            rel='self'
        )
        fg.language('en-US')
        fg.podcast.itunes_image(channel_data['thumbnails'][icon]['url'])
        fg.podcast.itunes_explicit('no')
        fg.podcast.itunes_owner(
            name='Podtube',
            email='armware+podtube@gmail.com'
        )
        fg.podcast.itunes_summary(channel_data['description'] or ' ')
        fg.podcast.itunes_category(cat='Technology')
        fg.updated(str(datetime.datetime.utcnow()) + 'Z')

        response = {'nextPageToken': ''}
        page_count = items_count = 0
        while 'nextPageToken' in response.keys() and (max_items < 1 or items_count < max_items):
            page_count += 1
            if max_pages and page_count > int(max_pages):
                logging.info("Reached maximum number of pages. Stopping here.")
                break
            next_page = response['nextPageToken']
            payload = {
                'part': 'snippet,contentDetails',
                'maxResults': 50 if max_items < 1 or max_items - items_count > 50 else max_items - items_count,
                'playlistId': channel_upload_list,
                'key': KEY,
                'pageToken': next_page
            }
            request = requests.get(
                'https://www.googleapis.com/youtube/v3/playlistItems',
                params=payload,
                proxies=PROXIES
            )
            calls += 1
            response = request.json()
            if request.status_code == 200:
                logging.debug('Downloaded Channel Information')
            else:
                logging.error('Error Downloading Channel: %s', request.reason)
                self.send_error(reason='Error Downloading Channel')
                return
            for item in response['items']:
                snippet = item['snippet']
                if 'private' in snippet['title'].lower():
                    continue
                current_video = item['contentDetails']['videoId']

                try:
                    chan=snippet['channelTitle']
                except KeyError:
                    snippet['channelTitle'] = snippet['channelId']
                    logging.error("Channel title not found")

                logging.debug(
                    'ChannelVideo: %s (%s)',
                    current_video,
                    snippet['title']
                )
                fe = fg.add_entry()
                items_count += 1
                fe.title(snippet['title'])
                fe.id(current_video)
                icon = max(
                    snippet['thumbnails'],
                    key=lambda x: snippet['thumbnails'][x]['width'])
                fe.podcast.itunes_image(snippet['thumbnails'][icon]['url'])
                fe.updated(snippet['publishedAt'])
                if channel[1] == 'video':
                    fe.enclosure(
                        url=f'{self.request.protocol}://{self.request.host}{self.video_handler_path}{current_video}',
                        type="video/mp4"
                    )
                elif channel[1] == 'audio':
                    fe.enclosure(
                        url=f'{self.request.protocol}://{self.request.host}{self.audio_handler_path}{current_video}',
                        type="audio/mpeg"
                    )
                fe.author(name=snippet['channelTitle'])
                fe.podcast.itunes_author(snippet['channelTitle'])
                fe.pubDate(snippet['publishedAt'])
                fe.link(
                    href=f'https://www.youtube.com/watch?v={current_video}',
                    title=snippet['title']
                )
                fe.podcast.itunes_summary(snippet['description'])
                fe.description(snippet['description'])
                if not video or video['expire'] < fe.pubDate():
                    video = {'video': fe.id(), 'expire': fe.pubDate()}
        feed = {
            'feed': fg.rss_str(),
            'expire': datetime.datetime.now() + datetime.timedelta(hours=calls),
            'title': channel_data['title']
        }
        for chan in channel_name:
            channel_feed[chan] = feed

        logging.info("Got %s videos from %s pages" % (items_count, page_count))

        self.write(feed['feed'])
        self.finish()

        global AUTOLOAD_NEWEST_AUDIO, AUDIO_DIR
        if not AUTOLOAD_NEWEST_AUDIO:
            return
        video = video['video']
        mp3_file = f'{AUDIO_DIR}/{video}.mp3'
        if channel[1] == 'audio' and not os.path.exists(mp3_file) and video not in conversion_queue.keys():
            conversion_queue[video] = {
                'status': False,
                'added': datetime.datetime.now()
            }

class PlaylistHandler(web.RequestHandler):
    def initialize(self, video_handler_path: str, audio_handler_path: str, default_item_type: str = "audio"):
        """
        Initialize the class with the provided video and audio handler paths.

        Args:
            video_handler_path (str): The path to the video handler.
            audio_handler_path (str): The path to the audio handler.
            default_item_type (str): Default type of elements. 'audio' or 'video'
        """
        self.video_handler_path = video_handler_path
        self.audio_handler_path = audio_handler_path
        self.default_item_type = default_item_type

    @gen.coroutine
    def head(self, playlist):
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

    @gen.coroutine
    def get(self, playlist):
        """
        A coroutine function to fetch a playlist and generate an RSS feed based on the playlist content.
        """
        global KEY, PROXIES
        playlist = playlist.split('/')
        if len(playlist) < 2:
            playlist.append(self.default_item_type)
        playlist_name = '/'.join(playlist)
        self.set_header('Content-type', 'application/rss+xml')
        self.set_header('charset', 'utf-8')
        if playlist_name in playlist_feed and playlist_feed[playlist_name]['expire'] > datetime.datetime.now():
            self.write(playlist_feed[playlist_name]['feed'])
            self.finish()
            return

        try:
            max_items = self.get_argument("max_items", "-1")
            max_items = int(max_items)
        except ValueError:
            logging.error(f"Failed parse max_count to int: {max_items}")
            max_items = 1

        calls = 0
        payload = {
            'part': 'snippet',
            'id': playlist[0],
            'key': KEY
        }
        request = requests.get(
            'https://www.googleapis.com/youtube/v3/playlists',
            params=payload,
            proxies=PROXIES
        )
        calls += 1
        if request.status_code == 200:
            logging.debug('Downloaded Playlist Information')
        else:
            logging.error('Error Downloading Playlist: %s', request.reason)
            self.send_error(reason='Error Downloading Playlist')
            return
        response = request.json()
        fg = FeedGenerator()
        fg.load_extension('podcast')
        fg.generator(
            'PodTube (python-feedgen)',
            __version__,
            'https://github.com/amckee/PodTube'
        )
        playlist_data = response['items'][0]['snippet']
        snippet = playlist_data

        icon_url = None
        title = None
        description = None

        as_channel = self.get_argument("as_channel", None)
        if as_channel is not None:
            payload = {
                'part': 'snippet',
                'maxResults': 1,
                'id': snippet['channelId'],
                'key': KEY
            }
            request = requests.get(
                'https://www.googleapis.com/youtube/v3/channels',
                params=payload,
                proxies=PROXIES
            )
            calls += 1
            if request.status_code != 200:
                payload = {
                    'part': 'snippet',
                    'maxResults': 1,
                    'forUsername': snippet['channelId'],
                    'key': KEY
                }
                request = requests.get(
                    'https://www.googleapis.com/youtube/v3/channels',
                    params=payload,
                    proxies=PROXIES
                )
                calls += 1
            if request.status_code == 200:
                logging.debug('Downloaded Playlist\'s Channel Information')
            else:
                logging.error('Error Downloading Playlist\'s Channel: %s', request.reason)
                self.send_error(reason='Error Downloading Playlist')
                return

            response = request.json()
            channel_data = response['items'][0]['snippet']
            icon_key = max(
                channel_data['thumbnails'],
                key=lambda x: channel_data['thumbnails'][x]['width']
            )
            icon_url = channel_data['thumbnails'][icon_key]['url']
            if 'title' in channel_data:
                title = channel_data['title']
            if 'description' in channel_data:
                description = channel_data['description']

        icon = max(
            snippet['thumbnails'],
            key=lambda x: snippet['thumbnails'][x]['width']
        )
        playlist_title = f"{snippet['channelTitle']}: {snippet['title']}"
        logging.info(
            'Playlist: %s (%s)',
            playlist[0],
            playlist_title
        )
        if not title:
            title = playlist_title
        if not description:
            description = snippet['description'] or ' '
        if not icon_url:
            icon = max(
                snippet['thumbnails'],
                key=lambda x: snippet['thumbnails'][x]['width']
            )
            icon_url = snippet['thumbnails'][icon]['url']

        fg.title(title)
        fg.id(f'{self.request.protocol}://{self.request.host}{self.request.uri}')
        fg.description(description)
        fg.author(
            name='Podtube',
            email='armware+podtube@gmail.com',
            uri='https://github.com/amckee/PodTube'
        )
        fg.podcast.itunes_author(snippet['channelTitle'])
        fg.image(icon_url)
        fg.link(
            href=f'https://www.youtube.com/playlist/?list={playlist[0]}',
            rel='self'
        )
        fg.language('en-US')
        fg.podcast.itunes_image(icon_url)
        fg.podcast.itunes_explicit('no')
        fg.podcast.itunes_owner(
            name='Podtube',
            email='armware+podtube@gmail.com'
        )
        fg.podcast.itunes_summary(snippet['description'])
        fg.podcast.itunes_category(cat='Technology')
        fg.updated(str(datetime.datetime.utcnow()) + 'Z')
        video = None
        response = {'nextPageToken': ''}
        items_count = 0
        while 'nextPageToken' in response.keys() and (max_items < 1 or items_count < max_items):
            payload = {
                'part': 'snippet',
                'maxResults': 50 if max_items < 1 or max_items - items_count > 50 else max_items - items_count,
                'playlistId': playlist[0],
                'key': KEY,
                'pageToken': response['nextPageToken']
            }
            request = requests.get(
                'https://www.googleapis.com/youtube/v3/playlistItems',
                params=payload,
                proxies=PROXIES
            )
            calls += 1
            response = request.json()
            if request.status_code == 200:
                logging.debug('Downloaded Playlist Information')
            else:
                logging.error('Error Downloading Playlist: %s', request.reason)
                self.send_error(reason='Error Downloading Playlist Items')
                return

            # logging.debug(response)
            for item in response['items']:
                snippet = item['snippet']
                current_video = snippet['resourceId']['videoId']
                if 'Private' in snippet['title']:
                    continue
                logging.debug(
                    'PlaylistVideo: %s (%s)',
                    current_video,
                    snippet['title']
                )
                fe = fg.add_entry()
                fe.title(snippet['title'])
                fe.id(current_video)
                if snippet['thumbnails']:
                    icon = max(
                        snippet['thumbnails'],
                        key=lambda x: snippet['thumbnails'][x]['width']
                    )
                    fe.podcast.itunes_image(snippet['thumbnails'][icon]['url'])
                fe.updated(snippet['publishedAt'])
                final_url = None
                if playlist[1] == 'video':
                    final_url = f'{self.request.protocol}://{self.request.host}{self.video_handler_path}{current_video}'
                    fe.enclosure(
                        url=final_url,
                        type="video/mp4"
                    )
                elif playlist[1] == 'audio':
                    final_url = f'{self.request.protocol}://{self.request.host}{self.audio_handler_path}{current_video}'
                    fe.enclosure(
                        url=final_url,
                        type="audio/mpeg"
                    )
                logging.debug( "Final URL created for enclosure: %s" % final_url )
                fe.author(name=snippet['channelTitle'])
                fe.podcast.itunes_author(snippet['channelTitle'])
                fe.pubDate(snippet['publishedAt'])
                fe.link(
                    href=f'https://www.youtube.com/watch?v={current_video}',
                    title=snippet['title']
                )
                fe.podcast.itunes_summary(snippet['description'])
                fe.description(snippet['description'])
                if not video or video['expire'] < fe.pubDate():
                    video = {'video': fe.id(), 'expire': fe.pubDate()}
                items_count = items_count + 1
        feed = {
            'feed': fg.rss_str(),
            'expire': datetime.datetime.now() + datetime.timedelta(hours=calls),
            'title': playlist_data['title']
        }
        playlist_feed[playlist_name] = feed
        self.write(feed['feed'])
        self.finish()
        global AUTOLOAD_NEWEST_AUDIO, AUDIO_DIR
        if not AUTOLOAD_NEWEST_AUDIO:
            return
        video = video['video']
        mp3_file = f'{AUDIO_DIR}/{video}.mp3'
        if playlist[1] == 'audio' and not os.path.exists(mp3_file) and video not in conversion_queue.keys():
            conversion_queue[video] = {
                'status': False,
                'added': datetime.datetime.now()
            }

class VideoHandler(web.RequestHandler):
    def get(self, video):
        """
        Get the video URL from YouTube using the provided video ID, and handle the redirection or error response accordingly.
        
        Parameters:
            video (str): The ID of the video to retrieve from YouTube.
        
        Returns:
            None
        """
        logging.info('Getting Video: %s', video)
        yt_url = get_youtube_url(video)
        logging.debug("Redirect to %s", yt_url)
        self.redirect( yt_url )

class AudioHandler(web.RequestHandler):
    def initialize(self):
        """
        Initialize the object.
        """
        self.disconnected = False

    @gen.coroutine
    def head(self, audio):
        """
        Coroutine function to set headers for audio file response.

        Args:
            self: The instance of the class.
            audio: The audio file to be served.

        Returns:
            None
        """
        self.set_header('Accept-Ranges', 'bytes')
        self.set_header("Content-Type", "audio/mpeg")

    @gen.coroutine
    def get(self, audio):
        """
        A coroutine function that handles the GET request for audio files. It checks if the requested audio is available and, if so, streams the audio content to the client. If the audio is not available or an error occurs during the conversion, appropriate status codes are set and returned.
        """
        global AUDIO_DIR
        logging.info('Audio: %s (%s)', audio, self.request.remote_ip)
        if audio in video_links and 'unavailable' in video_links[audio] and video_links[audio]['unavailable'] == True:
            # logging.info('Audio: %s is not available (%s)', audio, self.request.remote_ip)
            self.set_status(422) # Unprocessable Content. E.g. the video is a live stream
            return
        mp3_file = f'{AUDIO_DIR}/{audio}.mp3'
        if not os.path.exists(mp3_file):
            if audio not in conversion_queue.keys():
                conversion_queue[audio] = {
                    'status': False,
                    'added': datetime.datetime.now()
                }
            while audio in conversion_queue:
                yield gen.sleep(0.5)
                if self.disconnected:
                    # logging.info('User was disconnected while requested audio: %s (%s)', audio, self.request.remote_ip)
                    self.set_status(408)
                    return
        if audio in video_links and 'unavailable' in video_links[audio] and video_links[audio]['unavailable'] == True:
            # logging.info('Audio: %s is not available (%s)', audio, self.request.remote_ip)
            self.set_status(422) # Unprocessable Content. E.g. the video is a live stream
            return
        if not os.path.exists(mp3_file):
            self.set_status(404) # An error occurred during the conversion and the file was not created
            return
        request_range = None
        range_header = self.request.headers.get("Range")
        if range_header:
            # As per RFC 2616 14.16, if an invalid Range header is specified,
            # the request will be treated as if the header didn't exist.
            request_range = httputil._parse_request_range(range_header)

        size = os.stat(mp3_file).st_size
        if request_range:
            start, end = request_range
            if (start is not None and start >= size) or end == 0:
                # As per RFC 2616 14.35.1, a range is not satisfiable only: if
                # the first requested byte is equal to or greater than the
                # content, or when a suffix with length 0 is specified
                self.set_status(416)  # Range Not Satisfiable
                self.set_header("Content-Type", "audio/mpeg")
                self.set_header("Content-Range", "bytes */%s" % (size,))
                return
            if start is not None and start < 0:
                start += size
            if end is not None and end > size:
                # Clients sometimes blindly use a large range to limit their
                # download size; cap the endpoint at the actual file size.
                end = size
            # Note: only return HTTP 206 if less than the entire range has been
            # requested. Not only is this semantically correct, but Chrome
            # refuses to play audio if it gets an HTTP 206 in response to
            # ``Range: bytes=0-``.
            if size != (end or size) - (start or 0):
                self.set_status(206)  # Partial Content
                self.set_header(
                    "Content-Range",
                    httputil._get_content_range(start, end, size)
                )
        else:
            start = end = None
        if start is not None and end is not None:
            content_length = end - start
        elif end is not None:
            content_length = end
        elif start is not None:
            content_length = size - start
        else:
            content_length = size
        self.set_header("Accept-Ranges", "bytes")
        self.set_header("Content-Length", content_length)
        self.set_header('Content-Type', 'audio/mpeg')
        content = self.get_content(mp3_file, start, end)
        if isinstance(content, bytes):
            content = [content]
        for chunk in content:
            try:
                self.write(chunk)
                yield self.flush()
            except iostream.StreamClosedError:
                return

    @classmethod
    def get_content(cls, abspath, start=None, end=None):
        """Retrieve the content of the requested resource which is located
        at the given absolute path.

        This class method may be overridden by subclasses.  Note that its
        signature is different from other overridable class methods
        (no ``settings`` argument); this is deliberate to ensure that
        ``abspath`` is able to stand on its own as a cache key.

        This method should either return a byte string or an iterator
        of byte strings.  The latter is preferred for large files
        as it helps reduce memory fragmentation.

        .. versionadded:: 3.1
        """
        Path(abspath).touch(exist_ok=True)
        with open(abspath, "rb") as audio_file:
            if start is not None:
                audio_file.seek(start)
            if end is not None:
                remaining = end - (start or 0)
            else:
                remaining = None
            while True:
                chunk_size = 1024 ** 2
                if remaining is not None and remaining < chunk_size:
                    chunk_size = remaining
                chunk = audio_file.read(chunk_size)
                if chunk:
                    if remaining is not None:
                        remaining -= len(chunk)
                    yield chunk
                else:
                    if remaining is not None:
                        assert remaining == 0
                    return

    def on_connection_close(self):
        """
        Handle the event when the connection is closed. It sets the 'disconnected' attribute to True.
        """
        logging.warning('Audio: User quit during transcoding (%s)', self.request.remote_ip)
        self.disconnected = True

class UserHandler(web.RequestHandler):
    def initialize(self, channel_handler_path: str):
        """
        Initialize the channel handler with the specified path.

        Args:
            channel_handler_path (str): The path to the channel handler.

        Returns:
            None
        """
        self.channel_handler_path = channel_handler_path

    def get_canonical(self, url):
        """
        Get the canonical URL from the given input URL.

        Args:
            url (str): The input URL for which the canonical URL needs to be retrieved.

        Returns:
            str: The canonical URL if found, otherwise None.
        """
        global PROXIES
        logging.info("Getting canonical for %s" % url)
        req = requests.get( url, proxies=PROXIES )
        if req.status_code == 200:
            from bs4 import BeautifulSoup
            bs = BeautifulSoup( req.text, 'lxml' )
            can_url = None

            # loop through all links and find the canonical url
            for link in bs.find_all("link"):
                try:
                    if link['rel'][0] == 'canonical':
                        can_url = link['href']
                        break
                except:
                    # not all links have a rel
                    pass
            return can_url
        return None

    def get_channel_token(self, username: str) -> str:
        """
        Get the channel token for the given username.

        Args:
            username (str): The username for which the channel token is being retrieved.

        Returns:
            str: The channel token associated with the given username.
        """
        global channel_name_to_id
        if username in channel_name_to_id and channel_name_to_id[username]['expire'] > datetime.datetime.now():
            return channel_name_to_id[username]['id']
        yt_url = f"https://www.youtube.com/@{username}/about"
        canon_url = self.get_canonical( yt_url )
        logging.debug('Canonical url: %s' % canon_url)
        if canon_url is None:
            return None
        token_index = canon_url.rfind("/") + 1
        channel_token = canon_url[token_index:]
        channel_name_to_id[username] = {
            'id': channel_token,
            'expire': datetime.datetime.now() + datetime.timedelta(hours=24)
        }
        return channel_token

    def get(self, username):
        """
        A method to handle a Youtube channel by name and redirect to the corresponding URL.
        
        Args:
            username (str): The username of the Youtube channel.
        
        Returns:
            None
        """
        logging.debug('Handling Youtube channel by name: %s' % username)
        append = None
        append_index = username.find('/')
        if append_index > -1:
            append = username[append_index:]
            username = username[:append_index]
        channel_token = self.get_channel_token(username)

        if channel_token is None:
            logging.error("Failed to get canonical URL of %s" % username)
        else:
            selfurl = self.channel_handler_path + channel_token
            if append is not None:
                selfurl += append
            logging.info('Redirect to %s' % selfurl)
            self.redirect( selfurl, permanent = False )
        return None

class ClearCacheHandler(web.RequestHandler):
    ALL = "ALL"
    NONE = "NONE"

    VIDEO_FILES = "VIDEO_FILES"
    AUDIO_FILES = "AUDIO_FILES"
    VIDEO_LINKS = "VIDEO_LINKS"
    PLAYLIST_FEED = "PLAYLIST_FEED"
    CHANNEL_FEED = "CHANNEL_FEED"
    CHANNEL_NAME_TO_ID = "CHANNEL_NAME_TO_ID"

    def post(self):
        """
        A description of the entire function, its parameters, and its return types.
        """
        self.get()

    def get(self):
        """
        A function to handle clearing the cache for various video and playlist items.
        """
        global video_links, playlist_feed, channel_feed, channel_name_to_id, AUDIO_DIR, VIDEO_DIR

        videoFile = self.get_argument(ClearCacheHandler.VIDEO_FILES, ClearCacheHandler.NONE, True)
        audioFile = self.get_argument(ClearCacheHandler.AUDIO_FILES, ClearCacheHandler.NONE, True)
        videoLink = self.get_argument(ClearCacheHandler.VIDEO_LINKS, ClearCacheHandler.NONE, True)
        playlistFeed = self.get_argument(ClearCacheHandler.PLAYLIST_FEED, ClearCacheHandler.NONE, True)
        channelFeed = self.get_argument(ClearCacheHandler.CHANNEL_FEED, ClearCacheHandler.NONE, True)
        channelNameToId = self.get_argument(ClearCacheHandler.CHANNEL_NAME_TO_ID, ClearCacheHandler.NONE, True)

        needClear = False

        if any(element != ClearCacheHandler.NONE for element in [videoFile, audioFile, videoLink, playlistFeed, channelFeed, channelNameToId]):
            logging.info('Force clear cache started (%s)', self.request.remote_ip)
            needClear = True

        if (videoFile == ClearCacheHandler.ALL):
            for f in glob.glob(f'{VIDEO_DIR}/*mp4'):
                try:
                    os.remove(f)
                    logging.info('Deleted %s', f)
                except Exception as e:
                    logging.error('Error remove file %s: %s', f, e)
        elif videoFile != ClearCacheHandler.NONE:
            f = f"{VIDEO_DIR}/{videoFile}"
            try:
                os.remove(f)
                logging.info('Deleted %s', f)
            except Exception as e:
                logging.error('Error remove file %s: %s', f, e)

        if (audioFile == ClearCacheHandler.ALL):
            for f in glob.glob(f'{AUDIO_DIR}/*mp3'):
                try:
                    os.remove(f)
                    logging.info('Deleted %s', f)
                except Exception as e:
                    logging.error('Error remove file %s: %s', f, e)
        elif audioFile != ClearCacheHandler.NONE:
            f = f"{AUDIO_DIR}/{audioFile}"
            try:
                os.remove(f)
                logging.info('Deleted %s', f)
            except Exception as e:
                logging.error('Error remove file %s: %s', f, e)

        if (videoLink == ClearCacheHandler.ALL):
            video_links_length = len(video_links)
            video_links = {}
            logging.info('Cleaned %s items from video list', video_links_length)
        elif videoLink != ClearCacheHandler.NONE:
            if videoLink in video_links:
                del video_links[videoLink]
                logging.info('Cleaned 1 items from video list')

        if (playlistFeed == ClearCacheHandler.ALL):
            playlist_feed_length = len(playlist_feed)
            playlist_feed = {}
            logging.info('Cleaned %s items from playlist feeds', playlist_feed_length)
        elif playlistFeed != ClearCacheHandler.NONE:
            if playlistFeed in playlist_feed:
                del playlist_feed[playlistFeed]
                logging.info('Cleaned 1 items from playlist feeds')

        if (channelFeed == ClearCacheHandler.ALL):
            channel_feed_length = len(channel_feed)
            channel_feed = {}
            logging.info('Cleaned %s items from channel feeds', channel_feed_length)
        elif channelFeed != ClearCacheHandler.NONE:
            if channelFeed in channel_feed:
                del channel_feed[channelFeed]
                logging.info('Cleaned 1 items from channel feeds')

        if (channelNameToId == ClearCacheHandler.ALL):
            channel_name_to_id_length = len(channel_name_to_id)
            channel_name_to_id = {}
            logging.info('Cleaned %s items from channel name map', channel_name_to_id_length)
        elif channelNameToId != ClearCacheHandler.NONE:
            if channelNameToId in channel_name_to_id:
                del channel_name_to_id[channelNameToId]
                logging.info('Cleaned 1 items from channel name map')

        if needClear:
            selfurl = f'{self.request.protocol}://{self.request.host}{self.request.uri}'
            self.redirect( selfurl, permanent = False )
            return

        self.write(f'<html><head><title>PodTube (v{__version__}) cache</title>')
        self.write('<link rel="shortcut icon" href="favicon.ico">')
        self.write('</head><body>')

        self.write(f"<label>Clear cache</label>")
        self.write("<br/><br/>")
        self.write("<form method='POST'>")
        self.write(f"<label for='{ClearCacheHandler.VIDEO_LINKS}'>Cached video links: </label>")
        self.write(f"<select id='{ClearCacheHandler.VIDEO_LINKS}' name='{ClearCacheHandler.VIDEO_LINKS}'>")
        self.write(f"<option value='{ClearCacheHandler.NONE}' selected>{ClearCacheHandler.NONE}</option>")
        self.write(f"<option value='{ClearCacheHandler.ALL}'>{ClearCacheHandler.ALL}</option>")
        for video, info in video_links.items():
            self.write(f"<option value='{video}'>{video}</option>")
        self.write("</select>")
        self.write("<br/><br/>")

        self.write(f"<label for='{ClearCacheHandler.PLAYLIST_FEED}'>Cached playlist feed: </label>")
        self.write(f"<select id='{ClearCacheHandler.PLAYLIST_FEED}' name='{ClearCacheHandler.PLAYLIST_FEED}'>")
        self.write(f"<option value='{ClearCacheHandler.NONE}' selected>{ClearCacheHandler.NONE}</option>")
        self.write(f"<option value='{ClearCacheHandler.ALL}'>{ClearCacheHandler.ALL}</option>")
        for playlist, info in playlist_feed.items():
            caption = playlist
            if 'title' in info:
                caption = f"{info['title']} ({caption})"
            self.write(f"<option value='{playlist}'>{caption}</option>")
        self.write("</select>")
        self.write("<br/><br/>")

        self.write(f"<label for='{ClearCacheHandler.CHANNEL_FEED}'>Cached channel feed: </label>")
        self.write(f"<select id='{ClearCacheHandler.CHANNEL_FEED}' name='{ClearCacheHandler.CHANNEL_FEED}'>")
        self.write(f"<option value='{ClearCacheHandler.NONE}' selected>{ClearCacheHandler.NONE}</option>")
        self.write(f"<option value='{ClearCacheHandler.ALL}'>{ClearCacheHandler.ALL}</option>")
        for channel, info in channel_feed.items():
            caption = channel
            if 'title' in info:
                caption = f"{info['title']} ({caption})"
            self.write(f"<option value='{channel}'>{caption}</option>")
        self.write("</select>")
        self.write("<br/><br/>")

        self.write(f"<label for='{ClearCacheHandler.CHANNEL_NAME_TO_ID}'>Cached channel name to id: </label>")
        self.write(f"<select id='{ClearCacheHandler.CHANNEL_NAME_TO_ID}' name='{ClearCacheHandler.CHANNEL_NAME_TO_ID}'>")
        self.write(f"<option value='{ClearCacheHandler.NONE}' selected>{ClearCacheHandler.NONE}</option>")
        self.write(f"<option value='{ClearCacheHandler.ALL}'>{ClearCacheHandler.ALL}</option>")
        for channel, info in channel_name_to_id.items():
            self.write(f"<option value='{channel}'>@{channel}</option>")
        self.write("</select>")
        self.write("<br/><br/>")

        self.write(f"<label for='{ClearCacheHandler.VIDEO_FILES}'>Cached video files: </label>")
        self.write(f"<select id='{ClearCacheHandler.VIDEO_FILES}' name='{ClearCacheHandler.VIDEO_FILES}'>")
        self.write(f"<option value='{ClearCacheHandler.NONE}' selected>{ClearCacheHandler.NONE}</option>")
        self.write(f"<option value='{ClearCacheHandler.ALL}'>{ClearCacheHandler.ALL}</option>")
        for f in sorted(glob.glob(f'{VIDEO_DIR}/*mp4'), key=lambda a_file: os.path.getctime(a_file)):
            size = os.path.getsize(f)
            if size > 10**12:
                size = str(size // 2**40) + 'TiB'
            elif size > 10**9:
                size = str(size // 2**30) + 'GiB'
            elif size > 10**6:
                size = str(size // 2**20) + 'MiB'
            elif size > 10**3:
                size = str(size // 2**10) + 'KiB'
            else:
                size = str(size) + 'B'
            f = os.path.basename(f)
            self.write(f"<option value='{f}'>{f} ({size})</option>")
        self.write("</select>")
        self.write("<br/><br/>")

        self.write(f"<label for='{ClearCacheHandler.AUDIO_FILES}'>Cached audio files: </label>")
        self.write(f"<select id='{ClearCacheHandler.AUDIO_FILES}' name='{ClearCacheHandler.AUDIO_FILES}'>")
        self.write(f"<option value='{ClearCacheHandler.NONE}' selected>{ClearCacheHandler.NONE}</option>")
        self.write(f"<option value='{ClearCacheHandler.ALL}'>{ClearCacheHandler.ALL}</option>")
        for f in sorted(glob.glob(f'{AUDIO_DIR}/*mp3'), key=lambda a_file: os.path.getctime(a_file)):
            size = os.path.getsize(f)
            if size > 10**12:
                size = str(size // 2**40) + 'TiB'
            elif size > 10**9:
                size = str(size // 2**30) + 'GiB'
            elif size > 10**6:
                size = str(size // 2**20) + 'MiB'
            elif size > 10**3:
                size = str(size // 2**10) + 'KiB'
            else:
                size = str(size) + 'B'
            f = os.path.basename(f)
            self.write(f"<option value='{f}'>{f} ({size})</option>")
        self.write("</select>")
        self.write("<br/><br/>")

        self.write("<input type='submit' value='CLEAR SELECTED CACHE' />")
        self.write("</form>")
        self.write("<br/>")

        self.write('</body></html>')
