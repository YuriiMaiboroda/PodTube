# [PodTube](https://github.com/aquacash5/PodTube)

This is an extended functionality fork of a python application for converting Youtube, Rumble and Bitchute channels into podcast-friendly RSS feeds.

For basic or original usage that may be needed, see the original project page. To use this fork:

## Usage

### Youtube

#### Key

For the YouTube module, you must specify the Google API Key. See [documentation][google_api_key_doc]

#### Channels

```
http://yourserver.com/youtube/channel/youtube-channel-id
```

YouTube channel by @<username> (should automatically grab canonical URL):

```
http://yourserver.com/youtube/user/@username
```

##### Optional GET Arguments

`max` — limit the number of pages we pull from to 10 pages
`max_items=value` — clamp playlist length
```
http://yourserver.com/youtube/channel/youtube-channel-id?max=10
http://yourserver.com/youtube/channel/youtube-channel-id?max_items=50
```

#### Playlists

```
http://yourserver.com/youtube/playlist/<PlaylistID>
```

#### Audio

If you want an audio podcast add a /audio to the url

```
http://yourserver.com/youtube/playlist/<PlaylistID>/audio

http://yourserver.com/youtube/channel/youtube-channel-id/audio

http://yourserver.com/youtube/user/@username/audio

```

##### Optional GET Arguments

`as_channel` — set information (title, icon and description) of channel instead of playlist
`max_items=value` — clamp playlist length

```
http://yourserver.com/youtube/playlist/<PlaylistID>/audio?max_items=50&as_channel
```

### Bitchute

#### Channels

```
http://yourserver.com/bitchute/channel/bitchute-channel-name
```

### Rumble

#### Channels

```
http://yourserver.com/rumble/channel/rumble-channel-name
```

#### Users

```
http://yourserver.com/rumble/user/rumble-user-name
```

#### Categories

```
http://yourserver.com/rumble/category/category-name
```

### Daily Motion

```
http://yourserver.com/dailymotion/user/dailymotion-user-name
```

## Docker
Docker container info:
Be sure to open a port to containers default 15000


`-e YT_API_KEY`  -  required for Youtube functions

[https://hub.docker.com/r/ftawesome/podtube](https://hub.docker.com/r/ftawesome/podtube)

## Configuration

### Command line

```rs
podtube.py [--config-file CONFIG_FILE] [--log-file LOG_FILE] [--log-format LOG_FORMAT] [--log-level {CRITICAL,FATAL,ERROR,WARN,WARNING,INFO,DEBUG,NOTSET}] [--log-filemode {a,w}] [port]
```

| argument | config | env | value | default | description |
| --- | --- | --- | --- | --- | --- |
| --config-file |  | CONFIG_FILE | CONFIG_FILE | `None` | Path to config file |
| --log-file | log_file | GENERAL_LOG_FILE | LOG_FILE | `/dev/stdout` | Path to log file or `/dev/stdout` for standard output |
| --log-format | log_format | GENERAL_LOG_FORMAT | LOG_FORMAT | `%(asctime)-15s [%(levelname)s] %(message)s` | Logging format using syntax for python `logging` module |
| --log-level | log_level | GENERAL_LOG_LEVEL | `CRITICAL`<br>`FATAL`<br>`ERROR`<br>`WARN`<br>`WARNING`<br>`INFO`<br>`DEBUG`<br>`NOTSET` | `INFO` | Logging level using for python `logging` module |
| --log-filemode | log_filemode | GENERAL_LOG_FILEMODE | `a`<br>`w` | `a` | Logging file mode using for python `logging` module<br>`a` - appending to the end of file if it exists<br>`w` - truncating the file first |
| port | port | GENERAL_PORT |  PORT_NUMBER | `15000` | Port Number to listen on |


> Priority for applying the configuration in descending order:
> 1. command line arguments
> 2. environment variables
> 3. configuration file

### Configuration file example

```ini
[general]
port=8080
log_file=./podtube.log
log_format=%(asctime)-15s %(message)s
log_level=DEBUG
log_filemode=w

[youtube]
api_key=YOUTUBE_API_KEY
cleanup_period=600000
convert_video_period=1000
audio_expiration_time=259200000 # 3 days in seconds
autoload_newest_audio=1
```

### Youtube configuration

| config                   | environment variable     | default value | type   | description                                                                       |
| ---------------------    | ------------------------ | ------------- | ------ | --------------------------------------------------------------------------------- |
| yt_api_key               | YT_API_KEY               | `None`        | string | A Google API Key. See [documentation][google_api_key_doc]                         |
| yt_http_proxy            | YT_HTTP_PROXY            | `None`        | string | An address for proxy (`http`, `https`, `socks5`) for `http` requests              |
| yt_https_proxy           | YT_HTTPS_PROXY           | `None`        | string | An address for proxy (`http`, `https`, `socks5`) for `https` requests             |
| yt_cleanup_period        | YT_CLEANUP_PERIOD        | `600000`      | int    | Periodicity of the call to the cache clearing function. In milliseconds           |
| yt_convert_video_period  | YT_CONVERT_VIDEO_PERIOD  | `1000`        | int    | Periodicity of calling the function of converting video to audio. In milliseconds |
| yt_audio_expiration_time | YT_AUDIO_EXPIRATION_TIME | `259200000`   | int    | Expiration time of stored files                                                   |
| yt_autoload_newest_audio | YT_AUTOLOAD_NEWEST_AUDIO | `True`        | bool   | Whether to automatically download the newest audio when updating the rss feed     |

## License
[BSD-2-Clause](./LICENSE)

[google_api_key_doc]: https://developers.google.com/youtube/registering_an_application