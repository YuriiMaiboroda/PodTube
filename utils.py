import os
from asyncio import sleep
from datetime import datetime
from urllib.parse import urlencode

from pytube import YouTube

video_links = dict()
metric_chart = {
    'k': 3,  # kilo
    'M': 6,  # Mega
    'G': 9,  # Giga
    'T': 12  # Tera
}

def parametrize(url, params):
    return url + '?' + urlencode(params)

def get_resolution(yt_video):
    return int(''.join(filter(str.isdigit, yt_video.resolution[:-1])))

def get_youtube_url(video_id):
    if video_id in video_links and video_links[video_id]['expire'] > datetime.now():
        return video_links[video_id]['url']
    yt_video = YouTube(f'http://www.youtube.com/watch?v={video_id}')
    video_url = yt_video.streams.get_highest_resolution().url
    parts = {part.split('=')[0]: part.split('=')[1] for part in video_url.split('?')[-1].split('&')}
    link = {'url': video_url, 'expire': datetime.fromtimestamp(int(parts['expire']))}
    video_links[video_id] = link
    return link['url']

def metric_to_base(metric):
    return int(metric[:-1]) * (10 ** metric_chart[metric[-1]])

async def get_total_storage(directory='.'):
    total_storage = 0
    for root, directories, files in os.walk(directory):
        for file in files:
            total_storage += os.path.getsize(os.path.join(root, file))
            await sleep(0)
    return total_storage

def convert_to_bool(input) -> bool:
    if type(input) is str:
        return input.lower() in ['1', 'true', 't', 'yes', 'y', 'on']
    return bool(input)