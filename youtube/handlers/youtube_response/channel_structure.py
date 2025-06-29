from pydantic import BaseModel

from youtube.handlers.youtube_response.common_structure import YoutubeThumbnail, YoutubeLocalized

class YoutubeChannelItemSnippet(BaseModel):
    """
    Representing the snippet of a YouTube channel item.
    """
    title: str | None = None
    description: str | None = None
    customUrl: str | None = None
    publishedAt: str | None = None
    thumbnails: dict[str, YoutubeThumbnail] | None = None
    defaultLanguage: str | None = None
    localized: YoutubeLocalized | None = None
    country: str | None = None


class YoutubeChannelItemContentDetailsRelatedPlaylists(BaseModel):
    """
    Representing related playlists in the content details of a YouTube channel item.
    """
    uploads: str | None = None
    likes: str | None = None


class YoutubeChannelItemContentDetails(BaseModel):
    """
    Representing the content details of a YouTube channel item.
    """
    relatedPlaylists: YoutubeChannelItemContentDetailsRelatedPlaylists | None = None


class YoutubeChannelItemTopicDetails(BaseModel):
    """
    Representing topic details of a YouTube channel item.
    """
    topicCategories: list[str] | None = None


class YoutubeChannelItemStatus(BaseModel):
    """
    Representing the status of a YouTube channel item.
    """
    privacyStatus: str | None = None
    isLinked: bool | None = None
    longUploadsStatus: str | None = None
    madeForKids: bool | None = None
    selfDeclaredMadeForKids: bool | None = None


class YoutubeChannelItemContentOwnerDetails(BaseModel):
    """
    Representing content owner details of a YouTube channel item.
    """
    contentOwner: str | None = None
    timeLinked: str | None = None


class YoutubeChannelItem(BaseModel):
    """
    Representing a YouTube channel item.
    """
    id: str | None = None
    snippet: YoutubeChannelItemSnippet | None = None
    contentDetails: YoutubeChannelItemContentDetails | None = None
    topicDetails: YoutubeChannelItemTopicDetails | None = None
    status: YoutubeChannelItemStatus | None = None
    contentOwnerDetails: YoutubeChannelItemContentOwnerDetails | None = None
    localizations: dict[str, YoutubeLocalized] | None = None


class YoutubeChannelResponseStructure(BaseModel):
    """
    Representing the structure of a YouTube channel response.
    """
    items: list[YoutubeChannelItem]