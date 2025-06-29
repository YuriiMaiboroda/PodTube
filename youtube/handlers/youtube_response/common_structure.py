
from pydantic import BaseModel

class YoutubeThumbnail(BaseModel):
    """
    Representing a thumbnail
    """
    url: str | None = None
    """The URL of the thumbnail image."""
    width: int | None = None
    """The width of the thumbnail image."""
    height: int | None = None
    """The height of the thumbnail image."""

class YoutubeLocalized(BaseModel):
    """
    Representing localized information
    """
    title: str | None = None
    """The localized title of the item."""
    description: str | None = None
    """The localized description of the item."""

class YoutubePageInfo(BaseModel):
    """
    Encapsulates paging information for the result set.
    """
    totalResults: int | None = None
    """The total number of results in the result set."""
    resultsPerPage: int | None = None
    """The number of results included in the API response."""

class YoutubeBaseItem(BaseModel):
    """
    Base structure for YouTube API items.
    """
    id: str | None = None
    """The unique identifier for the item."""
    etag: str | None = None
    """The Etag of this resource."""
    kind: str | None = None
    """Identifies the API resource's type."""

class YoutubeBaseResponseStructure(BaseModel):
    """
    Base structure for YouTube API responses.
    """
    kind: str | None = None
    """Identifies the API resource's type."""
    etag: str | None = None
    """The Etag of this resource."""
    nextPageToken: str | None = None
    """The token that can be used as the value of the pageToken parameter to retrieve the next page in the result set."""
    prevPageToken: str | None = None
    """The token that can be used as the value of the pageToken parameter to retrieve the previous page in the result set."""
    pageInfo: YoutubePageInfo | None = None
    """Information about the page."""