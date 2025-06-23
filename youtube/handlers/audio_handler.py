from youtube.logging_utils import TaggedLogger
from youtube.youtube import (
    UnavailableType,
    VideoLinkCacheItem,
    add_video_to_conversion_queue,
    get_audio_file_path,
    is_video_in_conversion_queue,
    VIEDO_LINKS_CACHE_NAME,
    cache_manager,
)

from tornado import gen, httputil, iostream, web

import os
from pathlib import Path

logger = TaggedLogger(__name__)

class AudioHandler(web.RequestHandler):
    def initialize(self):
        """
        Initialize the object.
        """
        self.disconnected = False

    async def head(self, audio):
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

    def checkUnavailable(self, audio:str) -> bool:
        """
        Check if the requested audio is unavailable by looking it up in the cache.
        If the audio is unavailable, it sets the appropriate HTTP status code based on the type of unavailability.
        Args:
            audio (str): The audio file to check for availability.
        Returns:
            bool: True if the audio is unavailable, False otherwise.
        """
        video_link_item:VideoLinkCacheItem = cache_manager.get(VIEDO_LINKS_CACHE_NAME, audio)
        if video_link_item:
            # logger.info(f'Audio: {audio} is not available ({self.request.remote_ip})', audio)
            match video_link_item.unavailable_type:
                case UnavailableType.STREAM:
                    self.set_status(422) # Unprocessable Content. E.g. the video is a live stream
                    return True
                case UnavailableType.SPONSOR:
                    self.set_status(402) # Payment required
                    return True
                case UnavailableType.LOGIN:
                    self.set_status(401) # Unauthorized. E.g. age restriction
                    return True
                case UnavailableType.REMOVED:
                    self.set_status(410) # Gone
                    return True
                case UnavailableType.PRIVATE:
                    self.set_status(403)
                    return True
        return False

    async def get(self, audio):
        """
        A coroutine function that handles the GET request for audio files. It checks if the requested audio is available and, if so, streams the audio content to the client. If the audio is not available or an error occurs during the conversion, appropriate status codes are set and returned.
        """
        logger.info(f'Audio: {audio} ({self.request.remote_ip})', audio)

        if (self.checkUnavailable(audio)):
            return
        mp3_file = get_audio_file_path(audio)
        if not os.path.exists(mp3_file):
            add_video_to_conversion_queue(audio)
            while is_video_in_conversion_queue(audio):
                await gen.sleep(0.5)
                if self.disconnected:
                    # logger.info(f'User was disconnected while requested audio: {audio} ({self.request.remote_ip})', audio)
                    self.set_status(408)
                    return
#        if audio in video_links and 'unavailable' in video_links[audio] and video_links[audio]['unavailable'] == True:
#            # logger.info(f'Audio: {audio} is not available ({self.request.remote_ip})', audio)
#            self.set_status(422) # Unprocessable Content. E.g. the video is a live stream
#            return
        if (self.checkUnavailable(audio)):
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
                self.set_header("Content-Range", f"bytes */{size}")
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
                await self.flush()
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
        logger.warning(f'Audio: User quit during transcoding ({self.request.remote_ip})', self.request.path)
        self.disconnected = True