
from typing import TypedDict

class YoutubeThumbnail(TypedDict):
    """
    A TypedDict representing a thumbnail
    """
    url: str | None
    width: int | None
    height: int | None

class YoutubeLocalized(TypedDict):
    """
    A TypedDict representing localized information
    """
    title: str | None
    description: str | None


class YoutubePageInfo(TypedDict):
    """
    A TypedDict representing the page information
    """
    totalResults: int | None
    resultsPerPage: int | None