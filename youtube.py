import datetime, logging, os, time
import glob, requests, utils

from configparser import ConfigParser
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

video_links = {}
playlist_feed = {}
channel_feed = {}
channel_name_to_id = {}

__version__ = 'v2023.04.21.5'

conversion_queue = {}
converting_lock = Semaphore(2)

def get_env_or_config_option(conf: ConfigParser, env_name: str, config_name: str, default_value = None):
    return utils.get_env_or_config_option(conf, env_name, config_name, "youtube", default_value=default_value)

def init(conf: ConfigParser):
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

def set_key( new_key=None ):
    global KEY
    KEY = new_key

def cleanup():
    # Globals
    global video_links, playlist_feed, channel_name_to_id, channel_feed, AUDIO_EXPIRATION_TIME
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
    for f in sorted(glob.glob('./audio/*mp3') + glob.glob('./video/*mp4'), key=lambda a_file: os.path.getctime(a_file)):
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
            logging.exception('Error converting file: %s', ex)
            if isinstance(ex, (exceptions.LiveStreamError, exceptions.VideoUnavailable)):
                if video not in video_links:
                    video_links[video] = {
                        'url': None,
                        'expire': datetime.datetime.now() + datetime.timedelta(hours=6)
                    }
                video_links[video]['unavailable'] = True
        finally:
            del conversion_queue[video]

async def download_youtube_audio(video) -> bool:
    global PROXIES, USE_OAUTH
    yturl = get_youtube_url(video)
    logging.debug("Full URL: %s", yturl)

    audio_file = './audio/%s.mp3' % video
    audio_file_temp = audio_file + '.temp'
    video_file = None

    try:
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
        yt.streams.get_audio_only().download(filename=audio_file_temp)

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

    return True

def download_youtube_video(video) -> str:
    global PROXIES, USE_OAUTH
    yturl = get_youtube_url(video)
    logging.debug("Full URL: %s", yturl)

    video_file = './video/%s.mp4' % video
    video_file_temp = video_file + '.temp'

    try:
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
        stream.download(filename=video_file_temp)

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
    return "https://www.youtube.com/watch?v=%s" % video

class ChannelHandler(web.RequestHandler):
    def initialize(self, video_handler_path: str, audio_handler_path: str):
        self.video_handler_path = video_handler_path
        self.audio_handler_path = audio_handler_path

    @gen.coroutine
    def head(self, channel):
        self.set_header('Content-type', 'application/rss+xml')
        self.set_header('Accept-Ranges', 'bytes')

    @gen.coroutine
    def get(self, channel):
        global KEY
        channel = channel.split('/')
        if len(channel) < 2:
            channel.append('video')
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
            'part': 'snippet',
            'maxResults': 1,
            'id': channel[0],
            'key': KEY
        }
        request = requests.get(
             'https://www.googleapis.com/youtube/v3/channels',
             params=payload
        )
        calls += 1
        if request.status_code != 200:
            payload = {
                'part': 'snippet',
                'maxResults': 1,
                'forUsername': channel[0],
                'key': KEY
            }
            request = requests.get(
                'https://www.googleapis.com/youtube/v3/channels',
                params=payload
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
        pageCount = itemCount = 0
        while 'nextPageToken' in response.keys():
            pageCount += 1
            next_page = response['nextPageToken']
            payload = {
                'part': 'snippet,contentDetails',
                'maxResults': 50,
                'channelId': channel[0],
                'key': KEY,
                'pageToken': next_page
            }
            request = requests.get(
                'https://www.googleapis.com/youtube/v3/activities',
                params=payload
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
                if snippet['type'] != 'upload':
                    continue
                if 'private' in snippet['title'].lower():
                    continue
                current_video = item['contentDetails']['upload']['videoId']

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
                itemCount += 1
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
        
        logging.info("Got %s videos from %s pages" % (itemCount, pageCount))

        self.write(feed['feed'])
        self.finish()

        global AUTOLOAD_NEWEST_AUDIO
        if not AUTOLOAD_NEWEST_AUDIO:
            return
        video = video['video']
        mp3_file = './audio/%s.mp3' % video
        if channel[1] == 'audio' and not os.path.exists(mp3_file) and video not in conversion_queue.keys():
            conversion_queue[video] = {
                'status': False,
                'added': datetime.datetime.now()
            }

class PlaylistHandler(web.RequestHandler):
    def initialize(self, video_handler_path: str, audio_handler_path: str):
        self.video_handler_path = video_handler_path
        self.audio_handler_path = audio_handler_path

    @gen.coroutine
    def head(self, playlist):
        self.set_header('Content-type', 'application/rss+xml')
        self.set_header('Accept-Ranges', 'bytes')

    @gen.coroutine
    def get(self, playlist):
        global KEY
        playlist = playlist.split('/')
        if len(playlist) < 2:
            playlist.append('video')
        playlist_name = '/'.join(playlist)
        self.set_header('Content-type', 'application/rss+xml')
        if playlist_name in playlist_feed and playlist_feed[playlist_name]['expire'] > datetime.datetime.now():
            self.write(playlist_feed[playlist_name]['feed'])
            self.finish()
            return
        calls = 0
        payload = {
            'part': 'snippet',
            'id': playlist[0],
            'key': KEY
        }
        request = requests.get(
            'https://www.googleapis.com/youtube/v3/playlists',
            params=payload
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
        icon = max(
            snippet['thumbnails'],
            key=lambda x: snippet['thumbnails'][x]['width']
        )
        logging.info(
            'Playlist: %s (%s)',
            playlist[0],
            snippet['title']
        )
        fg.title(snippet['title'])
        fg.id(f'{self.request.protocol}://{self.request.host}{self.request.uri}')
        fg.description(snippet['description'] or ' ')
        fg.author(
            name='Podtube',
            email='armware+podtube@gmail.com',
            uri='https://github.com/amckee/PodTube'
        )
        fg.podcast.itunes_author(snippet['channelTitle'])
        fg.image(snippet['thumbnails'][icon]['url'])
        fg.link(
            href=f'https://www.youtube.com/playlist/?list={playlist}',
            rel='self'
        )
        fg.language('en-US')
        fg.podcast.itunes_image(snippet['thumbnails'][icon]['url'])
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
        while 'nextPageToken' in response.keys():
            payload = {
                'part': 'snippet',
                'maxResults': 50,
                'playlistId': playlist[0],
                'key': KEY,
                'pageToken': response['nextPageToken']
            }
            request = requests.get(
                'https://www.googleapis.com/youtube/v3/playlistItems',
                params=payload
            )
            calls += 1
            response = request.json()
            if request.status_code == 200:
                logging.debug('Downloaded Playlist Information')
            else:
                logging.error('Error Downloading Playlist: %s', request.reason)
                self.send_error(reason='Error Downloading Playlist Items')
                return
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
        feed = {
            'feed': fg.rss_str(),
            'expire': datetime.datetime.now() + datetime.timedelta(hours=calls),
            'title': playlist_data['title']
        }
        playlist_feed[playlist_name] = feed
        self.write(feed['feed'])
        self.finish()
        global AUTOLOAD_NEWEST_AUDIO
        if not AUTOLOAD_NEWEST_AUDIO:
            return
        video = video['video']
        mp3_file = './audio/%s.mp3' % video
        if playlist[1] == 'audio' and not os.path.exists(mp3_file) and video not in conversion_queue.keys():
            conversion_queue[video] = {
                'status': False,
                'added': datetime.datetime.now()
            }

class VideoHandler(web.RequestHandler):
    def get(self, video):
        logging.info('Getting Video: %s', video)
        yt_url = get_youtube_url(video)
        if type(yt_url) != str:
            self.write( "Error returned by Youtube: %s - %s" % (yt_url.code, yt_url.msg) )

        logging.debug("Got video URL: %s" % yt_url)
        self.redirect( yt_url )

class AudioHandler(web.RequestHandler):
    def initialize(self):
        self.disconnected = False

    @gen.coroutine
    def head(self, audio):
        self.set_header('Accept-Ranges', 'bytes')
        self.set_header("Content-Type", "audio/mpeg")

    @gen.coroutine
    def get(self, audio):
        logging.info('Audio: %s (%s)', audio, self.request.remote_ip)
        if audio in video_links and 'unavailable' in video_links[audio] and video_links[audio]['unavailable'] == True:
            # logging.info('Audio: %s is not available (%s)', audio, self.request.remote_ip)
            self.set_status(422) # Unprocessable Content. E.g. the video is a live stream
            return
        mp3_file = './audio/%s.mp3' % audio
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
        logging.warning('Audio: User quit during transcoding (%s)', self.request.remote_ip)
        self.disconnected = True

class UserHandler(web.RequestHandler):
    def initialize(self, channel_handler_path: str):
        self.channel_handler_path = channel_handler_path

    def get_canonical(self, url):
        logging.info("Getting canonical for %s" % url)
        req = requests.get( url )
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
        self.get()

    def get(self):
        global video_links, playlist_feed, channel_feed, channel_name_to_id

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
            for f in glob.glob('./video/*mp4'):
                try:
                    os.remove(f)
                    logging.info('Deleted %s', f)
                except Exception as e:
                    logging.error('Error remove file %s: %s', f, e)
        elif videoFile != ClearCacheHandler.NONE:
            f = f"./video/{videoFile}"
            try:
                os.remove(f)
                logging.info('Deleted %s', f)
            except Exception as e:
                logging.error('Error remove file %s: %s', f, e)

        if (audioFile == ClearCacheHandler.ALL):
            for f in glob.glob('./audio/*mp3'):
                try:
                    os.remove(f)
                    logging.info('Deleted %s', f)
                except Exception as e:
                    logging.error('Error remove file %s: %s', f, e)
        elif audioFile != ClearCacheHandler.NONE:
            f = f"./audio/{audioFile}"
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
        for f in sorted(glob.glob('./video/*mp4'), key=lambda a_file: os.path.getctime(a_file)):
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
        for f in sorted(glob.glob('./audio/*mp3'), key=lambda a_file: os.path.getctime(a_file)):
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
