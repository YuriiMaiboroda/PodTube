from pydantic import BaseModel

from youtube.handlers.youtube_response.common_structure import YoutubePageInfo, YoutubeLocalized, YoutubeThumbnail

class YoutubePlaylistSnippet(BaseModel):
    """
    Representing the snippet of a YouTube playlist.
    """
    publishedAt: str | None = None
    channelId: str | None = None
    title: str | None = None
    description: str | None = None
    thumbnails: dict[str, YoutubeThumbnail] | None = None
    channelTitle: str | None = None
    defaultLanguage: str | None = None
    localized: YoutubeLocalized | None = None

class YoutubePlaylistStatus(BaseModel):
    """
    Representing the status of a YouTube playlist.
    """
    privacyStatus: str | None = None
    podcastStatus: str | None = None

class YoutubePlaylistContentDetails(BaseModel):
    """
    Representing the content details of a YouTube playlist.
    """
    itemCount: int | None = None

class YoutubePlaylistPlayer(BaseModel):
    """
    Representing the player details of a YouTube playlist.
    """
    embedHtml: str | None = None

class YoutubePlaylistsResponseItem(BaseModel):
    """
    Representing a single item in the YouTube playlists response.
    """
    id: str | None = None
    snippet: YoutubePlaylistSnippet | None = None
    status: YoutubePlaylistStatus | None = None
    contentDetails: YoutubePlaylistContentDetails | None = None
    player: YoutubePlaylistPlayer | None = None
    localizations: dict[str, YoutubeLocalized] | None 

class YoutubePlaylistsResponse(BaseModel):
    """
    Representing the response structure for YouTube playlist.
    """
    nextPageToken: str | None = None
    prevPageToken: str | None = None
    pageInfo: YoutubePageInfo | None = None
    items: list[YoutubePlaylistsResponseItem] | None = None