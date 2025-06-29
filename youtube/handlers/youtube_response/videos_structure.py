from datetime import datetime
from pydantic import BaseModel

from youtube.handlers.youtube_response.common_structure import YoutubeBaseResponseStructure, YoutubeBaseItem, YoutubeLocalized, YoutubeThumbnail

class YoutubeVideoItemSnippet(BaseModel):
    """
    Representing the snippet of a YouTube video.
    """
    publishedAt: datetime | None = None
    """The date and time when the video was published."""
    channelId: str | None = None
    """The ID that YouTube uses to uniquely identify the channel that the video was uploaded to."""
    title: str | None = None
    """The title of the video."""
    description: str | None = None
    """The description of the video."""
    thumbnails: dict[str, YoutubeThumbnail] | None = None
    """A map of thumbnail images associated with the video, with keys representing the thumbnail quality (e.g., `default`, `medium`, `high`)."""
    channelTitle: str | None = None
    """The name of the channel that the video belongs to."""
    tags: list[str] | None = None
    """A list of keyword tags associated with the video. Tags may contain spaces."""
    categoryId: str | None = None
    """The YouTube [video category](https://developers.google.com/youtube/v3/docs/videoCategories/list) associated with the video."""
    liveBroadcastContent: str | None = None
    """
    Indicates if the video is a live broadcast and its status.
    Valid values are:
    - `live` - The video is an active live broadcast.
    - `upcoming` - The video is an upcoming live broadcast.
    - `none` - The video is not an upcoming/active live broadcast.
    """
    defaultLanguage: str | None = None
    """The language of the text in the video resource's snippet.title and snippet.description properties."""
    localized: YoutubeLocalized | None = None
    """Localized information about the video"""
    defaultAudioLanguage: str | None = None
    """Specifies the language spoken in the video's default audio track."""

class YoutubeVideoItemContentDetailsRegionRestriction(BaseModel):
    """
    Representing region restrictions for YouTube video content details.
    The object will contain either the `allowed` property or the `blocked` property
    """
    allowed: list[str] | None = None
    """A list of regions where the video is viewable."""
    blocked: list[str] | None = None
    """A list of regions where the video is blocked."""

    def isAllowedRegion(self, region_code: str) -> bool:
        """
        Check if a region is allowed to view the video.

        Args:
            region_code (str): The region code to check.

        Returns:
            bool: True if the region is allowed, False otherwise.
        """
        return self.allowed is not None and region_code in self.allowed or self.blocked is not None and region_code not in self.blocked

class YoutubeVideoItemContentRating(BaseModel):
    """
    Representing content rating for YouTube video content details.
    """
    acbRating: str | None = None
    """
    The video's Australian Classification Board (ACB) or Australian Communications and Media Authority (ACMA) rating.

    Valid values:
    - `acbC` - The video is classified as suitable for children.
    - `acbE` - E
    - `acbG` - G
    - `acbM` - M
    - `acbMa15plus` - MA15+
    - `acbP` - These programs are intended for preschool children.
    - `acbPg` - PG
    - `acbR18plus` - R18+
    - `acbUnrated`
    """
    agcomRating: str | None = None
    """
    The Italian Autorità per le Garanzie nelle Comunicazioni (AGCOM) rating.

    Valid values:
    - `agcomT` - T
    - `agcomVm14` - VM14
    - `agcomVm18` - VM18
    - `agcomUnrated`
    """
    anatelRating: str | None = None
    """
    The video's Anatel (Asociación Nacional de Televisión) rating for Chilean television

    Valid values:
    - `anatelA` - A
    - `anatelF` - F
    - `anatelI` - I
    - `anatelI10` - I-10
    - `anatelI12` - I-12
    - `anatelI7` - I-7
    - `anatelR` - R
    - `anatelUnrated`
    """
    bbfcRating: str | None = None
    """
    The British Board of Film Classification (BBFC) rating.

    Valid values:
    - `bbfc12` - 12
    - `bbfc12a` - 12A
    - `bbfc15` - 15
    - `bbfc18` - 18
    - `bbfcPg` - PG
    - `bbfcR18` - R18
    - `bbfcU` - U
    - `bbfcUnrated`
    """
    bfvcRating: str | None = None
    """
    The video's rating from Thailand's Board of Film and Video Censors (BFVC).

    Valid values:
    - `bfvc13` - 13
    - `bfvc15` - 15
    - `bfvc18` - 18
    - `bfvc20` - 20
    - `bfvcB` - B
    - `bfvcE` - E
    - `bfvcG` - G
    - `bfvcUnrated`
    """
    bmukkRating: str | None = None
    """
    The video's rating from the Austrian Board of Media Classification (Bundesministerium für Unterricht, Kunst und Kultur).

    Valid values:
    `bmukk6` - 6+
    `bmukk8` - 8+
    `bmukk10` - 10+
    `bmukk12` - 12+
    `bmukk14` - 14+
    `bmukk16` - 16+
    `bmukkAa` - Unrestricted
    `bmukkUnrated`
    """
    catvRating: str | None = None
    """
    The video's rating from the Canadian Radio-television and Telecommunications Commission (CRTC) for Canadian English-language broadcasts.

    Valid values:
    - `catvC` - C
    - `catvC8` - C8
    - `catvG` - G
    - `catvPG` - PG
    - `catv14` - 14+
    - `catv18` - 18+
    - `catvUnrated`
    """
    catvfrRating: str | None = None
    """
    The video's rating from the Canadian Radio-television and Telecommunications Commission (CRTC) for Canadian French-language broadcasts.

    Valid values:
    - `catvfrG` - G
    - `catvfr8plus` - 8+
    - `catvfr13plus` - 13+
    - `catvfr16plus` - 16+
    - `catvfr18plus` - 18+
    - `catvfrUnrated`
    """
    cbfcRating: str | None = None
    """
    The Central Board of Film Certification (CBFC) rating for India.

    Valid values:
    - `cbfcA` - A
    - `cbfcS` - S
    - `cbfcU` - U
    - `cbfcUA` - U/A
    - `cbfcUA7plus` - U/A
    - `cbfcUA13plus` - U/A 13+
    - `cbfcUA16plus` - U/A 16+
    - `cbfcUnrated`
    """
    cccRating: str | None = None
    """
    The Consejo de Comunicación Audiovisual (CCA) rating (Chile).

    Valid values:
    - `ccc6` - 6+
    - `ccc14` - 14+
    - `ccc18` - 18+
    - `ccc18s` - 18+ contenido pornográfico
    - `ccc18v` - 18+ contenido excesivamente violento
    - `cccTe`- Todo espectador
    - `cccUnrated`
    """
    cceRating: str | None = None
    """
    The video's rating from Portugal's Comissão de Classificação de Espect´culos.

    Valid values:
    - `cceM4` - 4
    - `cceM6` - 6
    - `cceM12` - 12
    - `cceM14` - 14
    - `cceM16` - 16
    - `cceM18` - 18
    - `cceUnrated`
    """
    chfilmRating: str | None = None
    """
    The video's rating in Switzerland.

    Valid values:
    `chfilm0` - 0
    `chfilm6` - 6
    `chfilm12` - 12
    `chfilm16` - 16
    `chfilm18` - 18
    `chfilmUnrated`
    """
    chvrsRating: str | None = None
    """
    The video's Canadian Home Video Rating System (CHVRS) rating.

    Valid values:
    `chvrs14a` - 14A
    `chvrs18a` - 18A
    `chvrsE` - E
    `chvrsG` - G
    `chvrsPg` - PG
    `chvrsR` - R
    `chvrsUnrated`
    """
    cicfRating: str | None = None
    """
    The video's rating from the Commission de Contrôle des Films (Belgium).

    Valid values:
    `cicfE` - E
    `cicfKntEna` - KNT/ENA
    `cicfKtEa` - KT/EA
    `cicfUnrated`
    """
    cnaRating: str | None = None
    """
    The video's rating from Romania's CONSILIUL NATIONAL AL AUDIOVIZUALULUI (CNA).

    Valid values:
    `cna12` - 12
    `cna15` - 15
    `cna18` - 18
    `cna18plus` - 18+
    `cnaAp` - AP
    `cnaUnrated`
    """
    cncRating: str | None = None
    """
    Rating system in France - Commission de classification cinematographique

    Valid values:
    `cnc10` - 10
    `cnc12` - 12
    `cnc16` - 16
    `cnc18` - 18
    `cncE` - E
    `cncT` - T
    `cncUnrated`
    """
    csaRating: str | None = None
    """
    The video's rating from France's Conseil supérieur de l?audiovisuel, which rates broadcast content.

    Valid values:
    `csa10` - 10
    `csa12` - 12
    `csa16` - 16
    `csa18` - 18
    `csaInterdiction` - Interdiction
    `csaT` - T
    `csaUnrated`
    """
    cscRating: str | None = None
    """
    The video's rating from Luxembourg's Commission de surveillance de la classification des films (CSCF).

    Valid values:
    `cscf12` - 12
    `cscf16` - 16
    `cscf18` - 18
    `cscf6` - 6
    `cscf9` - 9
    `cscfA` - A
    `cscfAl` - AL
    `cscfUnrated`
    """
    czfilmRating: str | None = None
    """
    The video's rating in the Czech Republic.

    Valid values:
    `czfilm12` - 12
    `czfilm14` - 14
    `czfilm18` - 18
    `czfilmU` - U
    `czfilmUnrated`
    """
    djctqRating: str | None = None
    """
    The video's Departamento de Justiça, Classificação, Qualificação e Títulos (DJCQT - Brazil) rating.

    Valid values:
    `djctq10` - 10
    `djctq12` - 12
    `djctq14` - 14
    `djctq16` - 16
    `djctq18` - 18
    `djctqL` - L
    `djctqUnrated`
    """
    djctqRatingReasons: list[str] | None = None
    """Reasons that explain why the video received its DJCQT (Brazil) rating."""
    ecbmctRating: str | None = None
    """
    Rating system in Turkey - Evaluation and Classification Board of the Ministry of Culture and Tourism

    Valid values:
    `ecbmct13a` - 13A
    `ecbmct13plus` - 13+
    `ecbmct15a` - 15A
    `ecbmct15plus` - 15+
    `ecbmct18plus` - 18+
    `ecbmct7a` - 7A
    `ecbmct7plus` - 7+
    `ecbmctG` - G
    `ecbmctUnrated`
    `ecbmct6a` - 6A
    `ecbmct6plus` - 6+
    `ecbmct10a` - 10A
    `ecbmct10plus` - 10+
    `ecbmct16plus` - 16+
    """
    eefilmRating: str | None = None
    """
    The video's rating in Estonia.

    Valid values:
    `eefilmK12` - K-12
    `eefilmK14` - K-14
    `eefilmK16` - K-16
    `eefilmK6` - K-6
    `eefilmL` - L
    `eefilmMs12` - MS-12
    `eefilmMs6` - MS-6
    `eefilmPere` - Pere
    `eefilmUnrated`
    """
    egfilmRating: str | None = None
    """
    The video's rating in Egypt.

    Valid values:
    `egfilm18` - 18
    `egfilmBn` - BN
    `egfilmGn` - GN
    `egfilmUnrated`
    """
    eirinRating: str | None = None
    """
    The video's Eirin (映倫) rating. Eirin is the Japanese rating system.

    Valid values:
    `eirinG` - G
    `eirinPg12` - PG-12
    `eirinR15plus` - R15+
    `eirinR18plus` - R18+
    `eirinUnrated`
    """
    fcbmRating: str | None = None
    """
    The video's rating from Malaysia's Film Censorship Board.

    Valid values:
    `fcbm13` - 13
    `fcbm16` - 16
    `fcbm18` - 18
    `fcbm18pa` - 18PA
    `fcbm18pl` - 18PL
    `fcbm18sg` - 18SG
    `fcbm18sx` - 18SX
    `fcbmP12` - P12
    `fcbmP13` - P13
    `fcbmPg13` - PG13
    `fcbmU` - U
    `fcbmUnrated`
    """
    fcoRating: str | None = None
    """
    The video's rating from Hong Kong's Office for Film, Newspaper and Article Administration.

    Valid values:
    `fcoI` - I
    `fcoIi` - II
    `fcoIia` - IIA
    `fcoIib` - IIB
    `fcoIii` - III
    `fcoUnrated`
    """
    fpbRating: str | None = None
    """
    The video's rating from South Africa's Film and Publication Board.

    Valid values:
    `fpb10` - 10
    `fpb1012Pg` - 10-12PG
    `fpb13` - 13
    `fpb16` - 16
    `fpb18` - 18
    `fpb79Pg` - 7-9PG
    `fpbA` - A
    `fpbPg` - PG
    `fpbUnrated`
    `fpbX18` - X18
    `fpbXx` - XX
    """
    fpbRatingReasons: list[str] | None = None
    """Reasons that explain why the video received its FPB (South Africa) rating."""
    fskRating: str | None = None
    """
    The video's Freiwillige Selbstkontrolle der Filmwirtschaft (FSK - Germany) rating.

    Valid values:
    `fsk0` - FSK 0
    `fsk12` - FSK 12
    `fsk16` - FSK 16
    `fsk18` - FSK 18
    `fsk6` - FSK 6
    `fskUnrated`
    """
    grfilmRating: str | None = None
    """
    The video's rating in Greece.

    Valid values:
    `grfilmE` - E
    `grfilmK` - K
    `grfilmK12` - K-12
    `grfilmK13` - K-13
    `grfilmK15` - K-15
    `grfilmK17` - K-17
    `grfilmK18` - K-18
    `grfilmUnrated`
    """
    icaaRating: str | None = None
    """
    The video's Instituto de la Cinematografía y de las Artes Audiovisuales (ICAA - Spain) rating.

    Valid values:
    `icaa12` - 12
    `icaa13` - 13
    `icaa16` - 16
    `icaa18` - 18
    `icaa7` - 7
    `icaaApta` - APTA
    `icaaUnrated`
    `icaaX` - X
    """
    ifcoRating: str | None = None
    """
    The video's Irish Film Classification Office (IFCO - Ireland) rating. See the IFCO website for more information.

    Valid values:
    `ifco12` - 12
    `ifco12a` - 12A
    `ifco15` - 15
    `ifco15a` - 15A
    `ifco16` - 16
    `ifco18` - 18
    `ifcoG` - G
    `ifcoPg` - PG
    `ifcoUnrated`
    """
    ilfilmRating: str | None = None
    """
    The video's rating in Israel.

    Valid values:
    `ilfilm12` - 12
    `ilfilm16` - 16
    `ilfilm18` - 18
    `ilfilmAa` - AA
    `ilfilmUnrated`
    """
    incaaRating: str | None = None
    """
    The video's INCAA (Instituto Nacional de Cine y Artes Audiovisuales - Argentina) rating.

    Valid values:
    `incaaAtp` - ATP (Apta para todo publico)
    `incaaC` - X (Solo apta para mayores de 18 años, de exhibición condicionada)
    `incaaSam13` - 13 (Solo apta para mayores de 13 años)
    `incaaSam16` - 16 (Solo apta para mayores de 16 años)
    `incaaSam18` - 18 (Solo apta para mayores de 18 años)
    `incaaUnrated`
    """
    kfcbRating: str | None = None
    """
    The video's rating from the Kenya Film Classification Board.

    Valid values:
    `kfcb16plus` - 16
    `kfcbG` - GE
    `kfcbPg` - PG
    `kfcbR` - 18
    `kfcbUnrated`
    """
    kijkwijzerRating: str | None = None
    """
    voor de Classificatie van Audiovisuele Media (Netherlands).

    Valid values:
    `kijkwijzer12` - 12
    `kijkwijzer14` - 14
    `kijkwijzer16` - 16
    `kijkwijzer18` - 18
    `kijkwijzer6` - 6
    `kijkwijzer9` - 9
    `kijkwijzerAl` - AL
    `kijkwijzerUnrated`
    """
    kmrbRating: str | None = None
    """
    The video's Korea Media Rating Board (영상물등급위원회) rating. The KMRB rates videos in South Korea.

    Valid values:
    `kmrb12plus` - 12세 이상 관람가
    `kmrb15plus` - 15세 이상 관람가
    `kmrbAll` - 전체관람가
    `kmrbR` - 청소년 관람불가
    `kmrbTeenr`
    `kmrbUnrated`
    """
    lsfRating: str | None = None
    """
    The video's rating from Indonesia's Lembaga Sensor Film.

    Valid values:
    - `lsf13` - 13
    - `lsf17` - 17
    - `lsf21` - 21
    - `lsfA` - A
    - `lsfBo` - BO
    - `lsfD` - D
    - `lsfR` - R
    - `lsfSu` - SU
    - `lsfUnrated`
    """
    mccaaRating: str | None = None
    """
    The video's rating from Malta's Film Age-Classification Board.

    Valid values:
    - `mccaa12` - 12
    - `mccaa12a` - 12A
    - `mccaa14` - 14 - this rating was removed from the new classification structure introduced in 2013.
    - `mccaa15` - 15
    - `mccaa16` - 16 - this rating was removed from the new classification structure introduced in 2013.
    - `mccaa18` - 18
    - `mccaaPg` - PG
    - `mccaaU` - U
    - `mccaaUnrated`
    """
    mccypRating: str | None = None
    """
    The video's rating from the Danish Film Institute's (Det Danske Filminstitut) Media Council for Children and Young People.

    Valid values:
    - `mccyp11` - 11
    - `mccyp15` - 15
    - `mccyp7` - 7
    - `mccypA` - A
    - `mccypUnrated`
    """
    mcstRating: str | None = None
    """
    The video's rating system for Vietnam - MCST

    Valid values:
    - `mcst0` - 0
    - `mcst16plus` - 16+
    - `mcstC13` - C13
    - `mcstC16` - C16
    - `mcstC18` - C18
    - `mcstP` - P
    - `mcstT13` - T13
    - `mcstT16` - T16
    - `mcstT18` - T18
    - `mcstK` - K
    - `mcstUnrated`
    """
    mdaRating: str | None = None
    """
    The video's rating from Singapore's Media Development Authority (MDA) and, specifically, it's Board of Film Censors (BFC).

    Valid values:
    - `mdaG` - G
    - `mdaM18` - M18
    - `mdaNc16` - NC16
    - `mdaPg` - PG
    - `mdaPg13` - PG13
    - `mdaR21` - R21
    - `mdaUnrated`
    """
    medietilsynetRating: str | None = None
    """
    The video's rating from Medietilsynet, the Norwegian Media Authority.

    Valid values:
    - `medietilsynet11` - 11
    - `medietilsynet12` - 12
    - `medietilsynet15` - 15
    - `medietilsynet18` - 18
    - `medietilsynet6` - 6
    - `medietilsynet7` - 7
    - `medietilsynet9` - 9
    - `medietilsynetA` - A
    - `medietilsynetUnrated`
    """
    mekuRating: str | None = None
    """
    The video's rating from Finland's Kansallinen Audiovisuaalinen Instituutti (National Audiovisual Institute).

    Valid values:
    - `meku12` - 12
    - `meku16` - 16
    - `meku18` - 18
    - `meku7` - 7
    - `mekuS` - S
    - `mekuUnrated`
    """
    mibacRating: str | None = None
    """
    The video's rating from the Ministero dei Beni e delle Attività Culturali e del Turismo (Italy).

    Valid values:
    - `mibacT`
    - `mibacVap`
    - `mibacVm6`
    - `mibacVm12`
    - `mibacVm14`
    - `mibacVm18`
    - `mibacUnrated`
    """
    mocRating: str | None = None
    """
    The video's Ministerio de Cultura (Colombia) rating.

    Valid values:
    - `moc12` - 12
    - `moc15` - 15
    - `moc18` - 18
    - `moc7` - 7
    - `mocBanned` - Banned
    - `mocE` - E
    - `mocT` - T
    - `mocX` - X
    - `mocUnrated`
    """
    moctwRating: str | None = None
    """
    The video's rating from Taiwan's Ministry of Culture (文化部).

    Valid values:
    - `moctwG` - G
    - `moctwP` - P
    - `moctwPg` - PG
    - `moctwR` - R
    - `moctwR12` - R-12
    - `moctwR15` - R-15
    - `moctwUnrated`
    """
    mpaaRating: str | None = None
    """
    The video's Motion Picture Association of America (MPAA) rating.

    Valid values:
    - `mpaaG` - G
    - `mpaaNc17` - NC-17
    - `mpaaPg` - PG
    - `mpaaPg13` - PG-13
    - `mpaaR` - R
    - `mpaaUnrated`
    """
    mpaatRating: str | None = None
    """
    The Motion Picture Association of America's rating for movie trailers and preview.

    Valid values:
    - `mpaatGb` - GB (Green Band - Approved for all audiences)
    - `mpaatRb` - RB (Red Band - Recommended for ages 17+)
    """
    mtrcbRating: str | None = None
    """
    The video's rating from the Movie and Television Review and Classification Board (Philippines).

    Valid values:
    - `mtrcbG` - G
    - `mtrcbPg` - PG
    - `mtrcbR13` - R-13
    - `mtrcbR16` - R-16
    - `mtrcbR18` - R-18
    - `mtrcbX` - X
    - `mtrcbUnrated`
    """
    nbcRating: str | None = None
    """
    The video's rating from the Maldives National Bureau of Classification.

    Valid values:
    - `nbc12plus` - 12+
    - `nbc15plus` - 15+
    - `nbc18plus` - 18+
    - `nbc18plusr` - 18+R
    - `nbcG` - G
    - `nbcPg` - PG
    - `nbcPu` - PU
    - `nbcUnrated`
    """
    nfrcRating: str | None = None
    """
    The video's rating from the Bulgarian National Film Center.

    Valid values:
    - `nfrcA` - A
    - `nfrcB` - B
    - `nfrcC` - C
    - `nfrcD` - D
    - `nfrcX` - X
    - `nfrcUnrated`
    """
    nfvcbRating: str | None = None
    """
    The video's rating from Nigeria's National Film and Video Censors Board.

    Valid values:
    - `nfvcb12` - 12
    - `nfvcb12a` - 12A
    - `nfvcb15` - 15
    - `nfvcb18` - 18
    - `nfvcbG` - G
    - `nfvcbPg` - PG
    - `nfvcbRe` - RE
    - `nfvcbUnrated`
    """
    nkclvRating: str | None = None
    """
    The video's rating from the Nacionãlais Kino centrs (National Film Centre of Latvia).

    Valid values:
    - `nkclv12plus` - 12+
    - `nkclv18plus` - 18+
    - `nkclv7plus` - 7+
    - `nkclvU` - U
    - `nkclvUnrated`
    """
    oflcRating: str | None = None
    """
    The video's Office of Film and Literature Classification (OFLC - New Zealand) rating.

    Valid values:
    - `oflcG` - G
    - `oflcM` - M
    - `oflcPg` - PG
    - `oflcR13` - R13
    - `oflcR15` - R15
    - `oflcR16` - R16
    - `oflcR18` - R18
    - `oflcRp13` - RP13
    - `oflcRp16` - RP16
    - `oflcUnrated`
    """
    pefilmRating: str | None = None
    """
    The video's rating in Peru.

    Valid values:
    - `pefilm14` - 14
    - `pefilm18` - 18
    - `pefilmPg` - PG
    - `pefilmPt` - PT
    - `pefilmUnrated`
    """
    resorteviolenciaRating: str | None = None
    """
    The video's rating in Venezuela.

    Valid values:
    - `resorteviolenciaA` - A
    - `resorteviolenciaB` - B
    - `resorteviolenciaC` - C
    - `resorteviolenciaD` - D
    - `resorteviolenciaE` - E
    - `resorteviolenciaUnrated`
    """
    rtcRating: str | None = None
    """
    The video's General Directorate of Radio, Television and Cinematography (Mexico) rating.

    Valid values:
    - `rtcA` - A
    - `rtcAa` - AA
    - `rtcB` - B
    - `rtcB15` - B15
    - `rtcC` - C
    - `rtcD` - D
    - `rtcUnrated`
    """
    rteRating: str | None = None
    """
    The video's rating from Ireland's Raidió Teilifís Éireann.

    Valid values:
    - `rteCh` - CH
    - `rteGa` - GA
    - `rteMa` - MA
    - `rtePs` - PS
    - `rteUnrated`
    """
    russiaRating: str | None = None
    """
    The video's National Film Registry of the Russian Federation (MKRF - Russia) rating.

    Valid values:
    - `russia0` - 0+
    - `russia12` - 12+
    - `russia16` - 16+
    - `russia18` - 18+
    - `russia6` - 6+
    - `russiaUnrated`
    """
    skfilmRating: str | None = None
    """
    The video's rating in Slovakia.

    Valid values:
    - `skfilmG` - G
    - `skfilmP2` - P2
    - `skfilmP5` - P5
    - `skfilmP8` - P8
    - `skfilmUnrated`
    """
    smaisRating: str | None = None
    """
    The video's rating in Iceland.

    Valid values:
    - `smais12` - 12
    - `smais14` - 14
    - `smais16` - 16
    - `smais18` - 18
    - `smais7` - 7
    - `smaisL` - L
    - `smaisUnrated`
    """
    smsaRating: str | None = None
    """
    The video's rating from Statens medieråd (Sweden's National Media Council).

    Valid values:
    - `smsa11` - 11
    - `smsa15` - 15
    - `smsa7` - 7
    - `smsaA` - All ages
    - `smsaUnrated`
    """
    tvpgRating: str | None = None
    """
    The video's TV Parental Guidelines (TVPG) rating.

    Valid values:
    - `tvpgG` - TV-G
    - `tvpgMa` - TV-MA
    - `tvpgPg` - TV-PG
    - `tvpgY` - TV-Y
    - `tvpgY7` - TV-Y7
    - `tvpgY7Fv` - TV-Y7-FV
    - `pg14` - TV-14
    - `tvpgUnrated`
    """
    ytRating: str | None = None
    """
    A rating that YouTube uses to identify age-restricted content.

    Valid values:
    - `ytAgeRestricted`
    """

class YoutubeVideoItemContentDetails(BaseModel):
    """
    Representing the content details of a YouTube video.
    """
    duration: str | None = None
    """The length of the video in ISO 8601 format."""
    dimension: str | None = None
    """
    Indicates whether the video is in 2D or 3D format.
    Valid values:
    - `2d`
    - `3d`
    """
    definition: str | None = None
    """
    Indicates whether the video is in high definition (HD) or standard definition (SD).
    Valid values:
    - `hd` - The video is in high definition.
    - `sd` - The video is in standard definition.
    """
    caption: bool | None = None
    """Indicates whether the video has captions."""
    licensedContent: bool | None = None
    """Indicates whether the video is licensed content."""
    regionRestriction: YoutubeVideoItemContentDetailsRegionRestriction | None = None
    """contains information about the countries where a video is (or is not) viewable."""
    contentRating: YoutubeVideoItemContentRating | None = None
    """Specifies the ratings that the video received under various rating schemes."""
    projection: str | None = None
    """
    Specifies the projection format of the video.

    Valid values:
    - `360`
    - `rectangular`
    """
    hasCustomThumbnail: bool | None = None
    """Indicates whether the video has a custom thumbnail."""

class YoutubeVideoItemStatistics(BaseModel):
    """
    Representing the statistics of a YouTube video.
    """
    viewCount: str | None = None
    likeCount: str | None = None
    dislikeCount: str | None = None
    favoriteCount: str | None = None
    commentCount: str | None = None

class YoutubeVideoItemStatus(BaseModel):
    """
    Representing the status of a YouTube video.
    """
    uploadStatus: str | None = None
    """
    Indicates the status of the video upload.

    Valid values:
    - `uploaded`
    - `processed`
    - `rejected`
    - `failed`
    - `deleted`
    """
    failureReason: str | None = None
    """
    Indicates the reason for a failed upload.

    Valid values:
    - `codec`
    - `conversion`
    - `emptyFile`
    - `invalidFile`
    - `tooSmall`
    - `uploadAborted`
    """
    rejectionReason: str | None = None
    """
    This value explains why YouTube rejected an uploaded video. This property is only present if the uploadStatus property indicates that the upload was rejected.

Valid values for this property are:
claim
copyright
duplicate
inappropriate
legal
length
termsOfUse
trademark
uploaderAccountClosed
uploaderAccountSuspended
"""
    privacyStatus: str | None = None
    """
    The video's privacy status.

Valid values for this property are:
private
public
unlisted
"""
    publishAt: datetime | None = None
    license: str | None = None
    embeddable: bool | None = None
    publicStatsViewable: bool | None = None
    madeForKids: bool | None = None
    selfDeclaredMadeForKids: bool | None = None
    containsSyntheticMedia: bool | None = None

class YoutubeVideoItempaidProductPlacementDetails(BaseModel):
    """
    Representing paid product placement details of a YouTube video.
    """
    hasPaidProductPlacement: bool | None = None

class YoutubeVideoItemPlayer(BaseModel):
    """
    Representing the player details of a YouTube video.
    """
    embedHtml: str | None = None
    embedWidth: int | None = None
    embedHeight: int | None = None

class YoutubeVideoItemTopicDetails(BaseModel):
    """
    Representing topic details of a YouTube video.
    """
    topicCategories: list[str] | None = None
    relevantTopicIds: list[str] | None = None
    topicIds: list[str] | None = None

class YoutubeVideoItemLiveStreamingDetails(BaseModel):
    """
    Representing live streaming details of a YouTube video.
    """
    actualStartTime: str | None = None
    actualEndTime: str | None = None
    scheduledStartTime: str | None = None
    scheduledEndTime: str | None = None
    concurrentViewers: int | None = None
    activeLiveChatId: str | None = None

class YoutubeVideoItem(YoutubeBaseItem):
    """
    Representing a single YouTube video item.
    """
    KIND = "youtube#video"

    snippet: YoutubeVideoItemSnippet | None = None
    """Contains basic details about the video, such as its title, description, and category."""
    contentDetails: YoutubeVideoItemContentDetails | None = None
    """Contains information about the video content, including the length of the video and an indication of whether captions are available for the video."""
    status: YoutubeVideoItemStatus | None = None
    """Contains information about the video's upload status, privacy status, and other related details."""
    statistics: YoutubeVideoItemStatistics | None = None
    paidProductPlacementDetails: YoutubeVideoItempaidProductPlacementDetails | None = None
    player: YoutubeVideoItemPlayer | None = None
    topicDetails: YoutubeVideoItemTopicDetails | None = None
    liveStreamingDetails: YoutubeVideoItemLiveStreamingDetails | None = None
    localizations: dict[str, YoutubeLocalized] | None = None

class YoutubeVideosResponse(YoutubeBaseResponseStructure):
    """
    Representing a YouTube videos response.
    """
    KIND = "youtube#videoListResponse"

    items: list[YoutubeVideoItem] | None = None
    """A list of videos that match the request criteria"""
