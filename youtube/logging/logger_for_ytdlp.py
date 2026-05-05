from __future__ import annotations


from utils.logging.processing_logger import ProcessingLogger


class LoggerForYoutubeDL(ProcessingLogger):
    """
    Adapter for yt-dlp logger API.

    yt-dlp sends both debug and info messages via debug().
    Real debug messages are prefixed with '[debug] '.
    """

    def debug(self, msg: str) -> None:
        if msg.startswith("[debug] "):
            super().debug(msg)
        else:
            super().info(msg)
