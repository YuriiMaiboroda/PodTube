#!/usr/bin/python3

import glob, logging, os
from argparse import ArgumentParser

import misaka
import youtube, bitchute, rumble, dailymotion
from tornado import gen, httputil, ioloop, iostream, process, web
import log_output

__version__ = 'v2023.04.07.04'

class FileHandler(web.RequestHandler):
    def get(self):
        logging.info('ReadMe (%s)', self.request.remote_ip)
        self.write('<html><head><title>PodTube (v')
        self.write(__version__)
        self.write(')</title><link rel="shortcut icon" href="favicon.ico">')
        self.write('<link rel="stylesheet" type="text/css" href="markdown.css">')
        self.write('</head><body>')
        with open('README.md') as text:
            self.write(
                misaka.html(
                    text.read(),
                    extensions=('tables', 'fenced-code')
                )
            )
        self.write('</body></html>')

def make_app(key="test"):
    job_logger = logging.getLogger()
    handler = job_logger.handlers[0]
    log_filename = os.path.basename(handler.baseFilename)
    log_folder = "." + os.path.sep + os.path.dirname(os.path.relpath(handler.baseFilename)) + os.path.sep
    # logging.info(f'log baseFilename: {handler.baseFilename}')
    # logging.info(f'log file name: {log_filename}')
    # logging.info(f'log folder: {log_folder}')
    webapp = web.Application([
        (r'/youtube/channel/(.*)', youtube.ChannelHandler),
        (r'/youtube/playlist/(.*)', youtube.PlaylistHandler),
        (r'/youtube/video/(.*)', youtube.VideoHandler),
        (r'/youtube/audio/(.*)', youtube.AudioHandler),
        (r'/youtube/user/@(.*)', youtube.UserHandler, {'channel_handler_path': '/youtube/channel/'}),
        (r'/rumble/user/(.*)', rumble.UserHandler),
        (r'/rumble/channel/(.*)', rumble.ChannelHandler),
        (r'/rumble/video/(.*)', rumble.VideoHandler),
        (r'/rumble/category/(.*)', rumble.CategoryHandler),
        (r'/bitchute/channel/(.*)', bitchute.ChannelHandler),
        (r'/bitchute/video/(.*)', bitchute.VideoHandler),
        (r'/dailymotion/channel/(.*)', dailymotion.ChannelHandler),
        (r'/dailymotion/video/(.*)', dailymotion.VideoHandler),
        (r'/log/(.*)', log_output.LogFileHandler, {'path': log_folder, 'default_filename': log_filename}),
        (r'/config.ini', web.RedirectHandler, {'url': '/'}),
        (r'/README.md', web.RedirectHandler, {'url': '/'}),
        (r'/Dockerfile', web.RedirectHandler, {'url': '/'}),
        (r'/', FileHandler),
        (r'/(.*)', web.StaticFileHandler, {'path': '.'})
    ], compress_response=True)
    return webapp

if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    if not os.path.exists('./audio'):
        os.mkdir('audio')
    parser = ArgumentParser(prog='PodTube')
    parser.add_argument(
        'port',
        type=int,
        default=15000,
        nargs='?',
        help='Port Number to listen on'
    )
    parser.add_argument(
        '--log-file',
        type=str,
        default='/dev/stdout',
        metavar='FILE',
        help='Location and name of log file'
    )
    parser.add_argument(
        '--log-format',
        type=str,
        default='%(asctime)-15s [%(levelname)s] %(message)s',
        metavar='FORMAT',
        help='Logging format using syntax for python logging module'
    )
    parser.add_argument(
        '-v', '--version',
        action='version',
        version="%(prog)s " + __version__
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG,
        format=args.log_format,
        filename=args.log_file,
        filemode='a'
    )
    for file in glob.glob('audio/*.temp'):
        os.remove(file)
    app = make_app( )
    app.listen(args.port)
    logging.info(f'Started listening on {args.port}')
    ioloop.PeriodicCallback(
        callback=youtube.cleanup,
        callback_time=1000
    ).start()
    ioloop.PeriodicCallback(
        callback=youtube.convert_videos,
        callback_time=1000
    ).start()
    ioloop.IOLoop.instance().start()
