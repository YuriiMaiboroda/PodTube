import utils

from configparser import ConfigParser

KEY = None
CLEANUP_PERIOD = None
CONVERT_VIDEO_PERIOD = None
AUDIO_EXPIRATION_TIME = None
PLAYLIST_EXPIRATION_TIME = None
HTTP_PROXY = None
HTTPS_PROXY = None
PROXIES = None
COOKIES_FILE_PATH = False
AUDIO_DIR = None
HL = None
MARK_WATCHED = None
FFMPEG_LIVE_LOGS = None

def get_env_or_config_option(conf: ConfigParser, env_name: str, config_name: str, value_type: type, default_value = None):
    """
    Get the value of a configuration option from the given ConfigParser object, either from the environment variables or from the configuration file.

    Args:
        conf (ConfigParser): The ConfigParser object containing the configuration options.
        env_name (str): The name of the environment variable to check for the configuration option.
        config_name (str): The name of the configuration option in the configuration file.
        default_value: The default value to return if the configuration option is not found.

    Returns:
        The value of the configuration option, or the default value if the option is not found.
    """
    return utils.get_env_or_config_option(conf, env_name, config_name, "youtube", value_type, default_value=default_value)


def init_config(conf):
    global KEY, HTTP_PROXY, HTTPS_PROXY, PROXIES, CLEANUP_PERIOD, CONVERT_VIDEO_PERIOD, AUDIO_EXPIRATION_TIME, PLAYLIST_EXPIRATION_TIME, COOKIES_FILE_PATH, AUDIO_DIR, HL, MARK_WATCHED, FFMPEG_LIVE_LOGS
    KEY                      = get_env_or_config_option(conf, "YT_API_KEY"                  , "yt_api_key"                  , str,  default_value=None)
    HTTP_PROXY               = get_env_or_config_option(conf, "YT_HTTP_PROXY"               , "yt_http_proxy"               , str,  default_value=None)
    HTTPS_PROXY              = get_env_or_config_option(conf, "YT_HTTPS_PROXY"              , "yt_https_proxy"              , str,  default_value=None)
    CLEANUP_PERIOD           = get_env_or_config_option(conf, "YT_CLEANUP_PERIOD"           , "yt_cleanup_period"           , int,  default_value=60*10)
    CONVERT_VIDEO_PERIOD     = get_env_or_config_option(conf, "YT_CONVERT_VIDEO_PERIOD"     , "yt_convert_video_period"     , int,  default_value=1)
    AUDIO_EXPIRATION_TIME    = get_env_or_config_option(conf, "YT_AUDIO_EXPIRATION_TIME"    , "yt_audio_expiration_time"    , int,  default_value=3*24*60*60)
    PLAYLIST_EXPIRATION_TIME = get_env_or_config_option(conf, "YT_PLAYLIST_EXPIRATION_TIME" , "yt_playlist_expiration_time" , int,  default_value=30*60)
    COOKIES_FILE_PATH        = get_env_or_config_option(conf, "YT_COOKIES_FILE_PATH"        , "yt_cookies_file_path"        , str,  default_value=None)
    AUDIO_DIR                = get_env_or_config_option(conf, "YT_AUDIO_DIR"                , "yt_audio_dir"                , str,  default_value="./youtube/audio")
    HL                       = get_env_or_config_option(conf, "YT_HL"                       , "yt_hl"                       , str,  default_value="en")
    MARK_WATCHED             = get_env_or_config_option(conf, "YT_MARK_WATCHED"             , "yt_mark_watched"             , bool, default_value=True)
    FFMPEG_LIVE_LOGS         = get_env_or_config_option(conf, "YT_FFMPEG_LIVE_LOGS"         , "yt_ffmpeg_live_logs"         , bool, default_value=False)

    if any(proxy is not None for proxy in (HTTP_PROXY, HTTPS_PROXY)):
        PROXIES = {}
    if HTTP_PROXY is not None:
        PROXIES["http"] = HTTP_PROXY
    if HTTPS_PROXY is not None:
        PROXIES["https"] = HTTPS_PROXY
