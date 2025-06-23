from typing import TypedDict

from youtube.handlers.youtube_response.common_structure import YoutubePageInfo, YoutubeLocalized, YoutubeThumbnail

class YoutubePlaylistSnippet(TypedDict):
    """
    A TypedDict representing the snippet of a YouTube playlist.
    """
    publishedAt: str | None
    channelId: str | None
    title: str | None
    description: str | None
    thumbnails: dict[str, YoutubeThumbnail] | None
    channelTitle: str | None
    defaultLanguage: str | None
    localized: YoutubeLocalized | None

class YoutubePlaylistStatus(TypedDict):
    """
    A TypedDict representing the status of a YouTube playlist.
    """
    privacyStatus: str | None
    podcastStatus: str | None

class YoutubePlaylistContentDetails(TypedDict):
    """
    A TypedDict representing the content details of a YouTube playlist.
    """
    itemCount: int | None

class YoutubePlaylistPlayer(TypedDict):
    """
    A TypedDict representing the player details of a YouTube playlist.
    """
    embedHtml: str | None

class YoutubePlaylistsResponseItem(TypedDict):
    """
    A TypedDict representing a single item in the YouTube playlists response.
    """
    id: str | None
    snippet: YoutubePlaylistSnippet | None
    status: YoutubePlaylistStatus | None
    contentDetails: YoutubePlaylistContentDetails | None
    player: YoutubePlaylistPlayer | None
    localizations: dict[str, YoutubeLocalized] | None 

class YoutubePlaylistsResponse(TypedDict):
    """
    A TypedDict representing the response structure for YouTube playlist.
    """
    nextPageToken: str | None
    prevPageToken: str | None
    pageInfo: YoutubePageInfo | None
    items: list[YoutubePlaylistsResponseItem] | None