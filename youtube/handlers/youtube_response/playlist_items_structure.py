from pydantic import BaseModel

from youtube.handlers.youtube_response.common_structure import YoutubePageInfo, YoutubeThumbnail

class YoutubePlaylistItemResourceId(BaseModel):
    """
    Representing the resource ID of a YouTube playlist item.
    Typically contains 'videoId'.
    """
    videoId: str | None = None

class YoutubePlaylistItemSnippet(BaseModel):
    """
    Representing the snippet of a YouTube playlist item.
    """
    publishedAt: str | None = None
    channelId: str | None = None
    title: str | None = None
    description: str | None = None
    thumbnails: dict[str, YoutubeThumbnail] | None = None
    channelTitle: str | None = None
    videoOwnerChannelTitle: str | None = None
    videoOwnerChannelId: str | None = None
    playlistId: str | None = None
    position: int | None = None
    resourceId: YoutubePlaylistItemResourceId | None = None

class YoutubePlaylistItemContentDetails(BaseModel):
    """
    Representing the content details of a YouTube playlist item.
    """
    videoId: str | None = None
    videoPublishedAt: str | None = None
    note: str | None = None

class YoutubePlaylistItemStatus(BaseModel):
    """
    Representing the status of a YouTube playlist item.
    """
    privacyStatus: str | None = None

class YoutubePlaylistItem(BaseModel):
    """
    Representing a YouTube playlist item.
    """
    id: str | None = None
    snippet: YoutubePlaylistItemSnippet | None = None
    contentDetails: YoutubePlaylistItemContentDetails | None = None
    status: YoutubePlaylistItemStatus | None = None

class YoutubePlaylistItemsResponse(BaseModel):
    """
    Representing the response structure for YouTube playlist items.
    """
    items: list[YoutubePlaylistItem] | None = None
    nextPageToken: str | None = None
    prevPageToken: str | None = None
    pageInfo: YoutubePageInfo | None = None
