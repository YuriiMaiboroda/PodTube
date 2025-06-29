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
USE_OAUTH = False
COOKIES_FILE_PATH = False
AUDIO_DIR = None
HL = None

def get_env_or_config_option(conf: ConfigParser, env_name: str, config_name: str, default_value = None):
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
    return utils.get_env_or_config_option(conf, env_name, config_name, "youtube", default_value=default_value)


def init_config(conf):
    global KEY, CLEANUP_PERIOD, CONVERT_VIDEO_PERIOD, AUDIO_EXPIRATION_TIME, PLAYLIST_EXPIRATION_TIME, HTTP_PROXY, HTTPS_PROXY, PROXIES, USE_OAUTH, COOKIES_FILE_PATH, AUDIO_DIR, HL
    KEY                      = str(get_env_or_config_option(conf, "YT_API_KEY"                  , "yt_api_key"                  , default_value=None))
    HTTP_PROXY               =     get_env_or_config_option(conf, "YT_HTTP_PROXY"               , "yt_http_proxy"               , default_value=None)
    HTTPS_PROXY              =     get_env_or_config_option(conf, "YT_HTTPS_PROXY"              , "yt_https_proxy"              , default_value=None)
    CLEANUP_PERIOD           = int(get_env_or_config_option(conf, "YT_CLEANUP_PERIOD"           , "yt_cleanup_period"           , default_value=60*10)) # 10 minutes
    CONVERT_VIDEO_PERIOD     = int(get_env_or_config_option(conf, "YT_CONVERT_VIDEO_PERIOD"     , "yt_convert_video_period"     , default_value=1)) # 1 second
    AUDIO_EXPIRATION_TIME    = int(get_env_or_config_option(conf, "YT_AUDIO_EXPIRATION_TIME"    , "yt_audio_expiration_time"    , default_value=3*24*60*60)) # 3 days
    PLAYLIST_EXPIRATION_TIME = int(get_env_or_config_option(conf, "YT_PLAYLIST_EXPIRATION_TIME" , "yt_playlist_expiration_time" , default_value=30*60)) # 30 minutes
    USE_OAUTH                =     get_env_or_config_option(conf, "YT_USE_OAUTH"                , "yt_use_oauth"                , default_value=False)
    COOKIES_FILE_PATH        = str(get_env_or_config_option(conf, "YT_COOKIES_FILE_PATH"        , "yt_cookies_file_path"        , default_value="__cache__/www.youtube.com_cookies.txt"))
    AUDIO_DIR                = str(get_env_or_config_option(conf, "YT_AUDIO_DIR"                , "yt_audio_dir"                , default_value="./youtube/audio"))
    HL               = str(get_env_or_config_option(conf, "YT_HL"                       , "yt_hl"                       , default_value="en"))

    USE_OAUTH = utils.convert_to_bool(USE_OAUTH)

    if any(proxy is not None for proxy in (HTTP_PROXY, HTTPS_PROXY)):
        PROXIES = {}
    if HTTP_PROXY is not None:
        PROXIES["http"] = HTTP_PROXY
    if HTTPS_PROXY is not None:
        PROXIES["https"] = HTTPS_PROXY