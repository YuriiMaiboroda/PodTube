from typing import TypedDict

from youtube.handlers.youtube_response.common_structure import YoutubeLocalized, YoutubePageInfo, YoutubeThumbnail

class YoutubeVideoItemSnippet(TypedDict):
    """
    A TypedDict representing the snippet of a YouTube video.
    """
    publishedAt: str | None
    channelId: str | None
    title: str | None
    description: str | None
    thumbnails: dict[str, YoutubeThumbnail] | None
    channelTitle: str | None
    tags: list[str] | None
    categoryId: str | None
    liveBroadcastContent: str | None
    defaultLanguage: str | None
    defaultAudioLanguage: str | None
    localized: YoutubeLocalized | None

class YoutubeVideoItemContentDetailsRegionRestriction(TypedDict):
    """
    A TypedDict representing region restrictions for YouTube video content details.
    """
    allowed: list[str] | None
    blocked: list[str] | None

class YoutubeVideoItemContentRating(TypedDict):
    """
    A TypedDict representing content rating for YouTube video content details.
    """
    acbRating: str | None
    agcomRating: str | None
    anatelRating: str | None
    bbfcRating: str | None
    bfvcRating: str | None
    bmukkRating: str | None
    catvRating: str | None
    catvfrRating: str | None
    cbfcRating: str | None
    cccRating: str | None
    cceRating: str | None
    chfilmRating: str | None
    chvrsRating: str | None
    cicfRating: str | None
    cnaRating: str | None
    cncRating: str | None
    csaRating: str | None
    cscRating: str | None
    czfilmRating: str | None
    djctqRating: str | None
    djctqRatingReasons: list[str] | None
    ecbmctRating: str | None
    eefilmRating: str | None
    egfilmRating: str | None
    eirinRating: str | None
    fcbmRating: str | None
    fcoRating: str | None
    fmocRating: str | None
    fpbRating: str | None
    fpbRatingReasons: list[str] | None
    fskRating: str | None
    grfilmRating: str | None
    icaaRating: str | None
    ifcoRating: str | None
    ilfilmRating: str | None
    incaaRating: str | None
    kfcbRating: str | None
    kijkwijzerRating: str | None
    kmrbRating: str | None
    lsfRating: str | None
    mccaaRating: str | None
    mccypRating: str | None
    mcstRating: str | None
    mdaRating: str | None
    medietilsynetRating: str | None
    mekuRating: str | None
    mibacRating: str | None
    mocRating: str | None
    moctwRating: str | None
    mpaaRating: str | None
    mpaatRating: str | None
    mtrcbRating: str | None
    nbcRating: str | None
    nbcplRating: str | None
    nfrcRating: str | None
    nfvcbRating: str | None
    nkclvRating: str | None
    oflcRating: str | None
    pefilmRating: str | None
    rcnofRating: str | None
    resorteviolenciaRating: str | None
    rtcRating: str | None
    rteRating: str | None
    russiaRating: str | None
    skfilmRating: str | None
    smaisRating: str | None
    smsaRating: str | None
    tvpgRating: str | None
    ytRating: str | None

class YoutubeVideoItemContentDetails(TypedDict):
    """
    A TypedDict representing the content details of a YouTube video.
    """
    duration: str | None
    dimension: str | None
    definition: str | None
    caption: str | None
    licensedContent: bool | None
    regionRestriction: YoutubeVideoItemContentDetailsRegionRestriction | None
    contentRating: YoutubeVideoItemContentRating | None
    projection: str | None
    hasCustomThumbnail: str | None

class YoutubeVideoItemStatistics(TypedDict):
    """
    A TypedDict representing the statistics of a YouTube video.
    """
    viewCount: str | None
    likeCount: str | None
    dislikeCount: str | None
    favoriteCount: str | None
    commentCount: str | None

class YoutubeVideoItemStatus(TypedDict):
    """
    A TypedDict representing the status of a YouTube video.
    """
    uploadStatus: str | None
    failureReason: str | None
    rejectionReason: str | None
    privacyStatus: str | None
    publishAt: str | None
    license: str | None
    embeddable: bool | None
    publicStatsViewable: bool | None
    madeForKids: bool | None
    selfDeclaredMadeForKids: bool | None
    containsSyntheticMedia: bool | None

class YoutubeVideoItempaidProductPlacementDetails(TypedDict):
    """
    A TypedDict representing paid product placement details of a YouTube video.
    """
    hasPaidProductPlacement: bool | None

class YoutubeVideoItemPlayer(TypedDict):
    """
    A TypedDict representing the player details of a YouTube video.
    """
    embedHtml: str | None
    embedWidth: int | None
    embedHeight: int | None

class YoutubeVideoItemTopicDetails(TypedDict):
    """
    A TypedDict representing topic details of a YouTube video.
    """
    topicCategories: list[str] | None
    relevantTopicIds: list[str] | None
    topicIds: list[str] | None

class YoutubeVideoItemLiveStreamingDetails(TypedDict):
    """
    A TypedDict representing live streaming details of a YouTube video.
    """
    actualStartTime: str | None
    actualEndTime: str | None
    scheduledStartTime: str | None
    scheduledEndTime: str | None
    concurrentViewers: int | None
    activeLiveChatId: str | None

class YoutubeVideoItem(TypedDict):
    """
    A TypedDict representing a single YouTube video item.
    """
    id: str | None
    snippet: YoutubeVideoItemSnippet | None
    contentDetails: YoutubeVideoItemContentDetails | None
    statistics: YoutubeVideoItemStatistics | None
    status: YoutubeVideoItemStatus | None
    paidProductPlacementDetails: YoutubeVideoItempaidProductPlacementDetails | None
    player: YoutubeVideoItemPlayer | None
    topicDetails: YoutubeVideoItemTopicDetails | None
    liveStreamingDetails: YoutubeVideoItemLiveStreamingDetails | None
    localizations: dict[str, YoutubeLocalized] | None

class YoutubeVideosResponse(TypedDict):
    """
    A TypedDict representing a YouTube videos response.
    """
    nextPageToken: str | None
    prevPageToken: str | None
    pageInfo: YoutubePageInfo | None
    items: list[YoutubeVideoItem] | None