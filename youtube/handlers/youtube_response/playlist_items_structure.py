from typing import TypedDict

from youtube.handlers.youtube_response.common_structure import YoutubePageInfo, YoutubeThumbnail

class YoutubePlaylistItemResourceId(TypedDict):
    """
    A TypedDict representing the resource ID of a YouTube playlist item.
    Typically contains 'videoId'.
    """
    videoId: str | None

class YoutubePlaylistItemSnippet(TypedDict):
    """
    A TypedDict representing the snippet of a YouTube playlist item.
    """
    publishedAt: str | None
    channelId: str | None
    title: str | None
    description: str | None
    thumbnails: dict[str, YoutubeThumbnail] | None
    channelTitle: str | None
    videoOwnerChannelTitle: str | None
    videoOwnerChannelId: str | None
    playlistId: str | None
    position: int | None
    resourceId: YoutubePlaylistItemResourceId | None

class YoutubePlaylistItemContentDetails(TypedDict):
    """
    A TypedDict representing the content details of a YouTube playlist item.
    """
    videoId: str | None
    videoPublishedAt: str | None
    note: str | None

class YoutubePlaylistItemStatus(TypedDict):
    """
    A TypedDict representing the status of a YouTube playlist item.
    """
    privacyStatus: str | None

class YoutubePlaylistItem(TypedDict):
    """
    A TypedDict representing a YouTube playlist item.
    """
    id: str | None
    snippet: YoutubePlaylistItemSnippet | None
    contentDetails: YoutubePlaylistItemContentDetails | None
    status: YoutubePlaylistItemStatus | None

class YoutubePlaylistItemsResponse(TypedDict):
    """
    A TypedDict representing the response structure for YouTube playlist items.
    """
    items: list[YoutubePlaylistItem] | None
    nextPageToken: str | None
    prevPageToken: str | None
    pageInfo: YoutubePageInfo | None
