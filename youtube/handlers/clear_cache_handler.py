from youtube.cache import CacheItem
from youtube.logging_utils import TaggedLogger
import youtube.youtube

from tornado import web

logger = TaggedLogger(__name__)

class ClearCacheHandler(web.RequestHandler):
    ALL = "ALL"
    NONE = "NONE"

    AUDIO_FILES = "AUDIO_FILES"
    VIDEO_LINKS = "VIDEO_LINKS"
    PLAYLIST_FEED = "PLAYLIST_FEED"
    CHANNEL_FEED = "CHANNEL_FEED"

    def post(self):
        """
        A description of the entire function, its parameters, and its return types.
        """
        self.get()

    def get(self):
        """
        A function to handle clearing the cache for various video and playlist items.
        """
        
        all_cache = youtube.youtube.cache_manager.get_all_cache_items()

        clear_cache_requests = {}
        for cache_type in all_cache:
            arg_value = self.get_argument(cache_type, ClearCacheHandler.NONE, True)
            if arg_value != ClearCacheHandler.NONE:
                clear_cache_requests[cache_type] = arg_value

        needClear = False

        if clear_cache_requests:
            logger.info(f'Force clear cache started ({self.request.remote_ip})', 'ClearCache')
            needClear = True

        for cache_type, value in clear_cache_requests.items():
            if value == ClearCacheHandler.ALL:
                deleted_count = youtube.youtube.cache_manager.cleanup_cache(cache_type)
                logger.info(f'Cleared all items from {cache_type} cache ({deleted_count} items deleted)', 'ClearCache')
            else:
                deleted_count = youtube.youtube.cache_manager.cleanup_cache(cache_type, value)
                logger.info(f'Cleared item \"{value}\" from {cache_type} cache ({deleted_count} items deleted)', 'ClearCache')

        if needClear:
            selfurl = f'{self.request.protocol}://{self.request.host}{self.request.path}'
            logger.info(f'Redirect to {selfurl}', 'ClearCache')
            self.redirect(selfurl, permanent = False)
            return

        self.write(f'<html><head><title>PodTube (v{youtube.youtube.__version__}) cache</title>')
        self.write('<link rel="shortcut icon" href="favicon.ico">')
        self.write('</head><body>')

        self.write(f"<label>Clear cache</label>")
        self.write("<br/><br/>")
        self.write("<form method='POST'>")

        def by_expire(pair: tuple[str, CacheItem]):
            return pair[1].expire

        for cache_type, items in all_cache.items():
            self.write(f"<label for='{cache_type}'>Cached {cache_type.lower().replace('_', ' ')}: </label>")
            self.write(f"<select id='{cache_type}' name='{cache_type}'>")
            self.write(f"<option value='{ClearCacheHandler.NONE}' selected>{ClearCacheHandler.NONE}</option>")
            self.write(f"<option value='{ClearCacheHandler.ALL}'>{ClearCacheHandler.ALL}</option>")
            for key, info in sorted(items.items(), key=by_expire, reverse=True):
                name = info.name
                caption = name if name is not None else key
                self.write(f"<option value='{key}'>{caption}</option>")
            self.write("</select>")
            self.write("<br/><br/>")

        self.write("<input type='submit' value='CLEAR SELECTED CACHE' />")
        self.write("</form>")
        self.write("<br/>")

        self.write('</body></html>')