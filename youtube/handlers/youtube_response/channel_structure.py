from typing import TypedDict

from youtube.handlers.youtube_response.common_structure import YoutubeThumbnail, YoutubeLocalized

class YoutubeChannelItemSnippet(TypedDict):
    """
    A TypedDict representing the snippet of a YouTube channel item.
    """
    title: str | None
    description: str | None
    customUrl: str | None
    publishedAt: str | None
    thumbnails: dict[str, YoutubeThumbnail] | None
    defaultLanguage: str | None
    localized: YoutubeLocalized | None
    country: str | None


class YoutubeChannelItemContentDetailsRelatedPlaylists(TypedDict):
    """
    A TypedDict representing related playlists in the content details of a YouTube channel item.
    """
    uploads: str | None
    likes: str | None


class YoutubeChannelItemContentDetails(TypedDict):
    """
    A TypedDict representing the content details of a YouTube channel item.
    """
    relatedPlaylists: YoutubeChannelItemContentDetailsRelatedPlaylists | None


class YoutubeChannelItemTopicDetails(TypedDict):
    """
    A TypedDict representing topic details of a YouTube channel item.
    """
    topicCategories: list[str] | None


class YoutubeChannelItemStatus(TypedDict):
    """
    A TypedDict representing the status of a YouTube channel item.
    """
    privacyStatus: str | None
    isLinked: bool | None
    longUploadsStatus: str | None
    madeForKids: bool | None
    selfDeclaredMadeForKids: bool | None


class YoutubeChannelItemContentOwnerDetails(TypedDict):
    """
    A TypedDict representing content owner details of a YouTube channel item.
    """
    contentOwner: str | None
    timeLinked: str | None


class YoutubeChannelItem(TypedDict):
    """
    A TypedDict representing a YouTube channel item.
    """
    id: str | None
    snippet: YoutubeChannelItemSnippet | None
    contentDetails: YoutubeChannelItemContentDetails | None
    topicDetails: YoutubeChannelItemTopicDetails | None
    status: YoutubeChannelItemStatus | None
    contentOwnerDetails: YoutubeChannelItemContentOwnerDetails | None
    localizations: dict[str, YoutubeLocalized] | None


class YoutubeChannelResponseStructure(TypedDict):
    """
    A TypedDict representing the structure of a YouTube channel response.
    """
    items: list[YoutubeChannelItem]