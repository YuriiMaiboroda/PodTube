#!/usr/bin/python3

import logging, os, re
from typing import Optional
from tornado import web

class StaticFileNonCacheHandler(web.StaticFileHandler):
    def should_return_304(self) -> bool:
        return False

    def compute_etag(self) -> Optional[str]:
        return None


class LogFileHandler(StaticFileNonCacheHandler):
    BLOCK_START = "@@@___@@@___@@@"
    BLOCK_END = "===___===___==="

    def escape(string: str) -> str:
        return string.replace("<", "&lt;").replace(">", "&gt;").replace("@", "&#64;").replace("=", "&#61;")

    def add_block_borders(string: str) -> str:
        string = re.sub(r"^[ \t]*(\d+-\d+-\d+ \d+:\d+:\d+)", rf"{LogFileHandler.BLOCK_START}\g<0>", string, flags = re.MULTILINE)
        string = re.sub(rf"^{LogFileHandler.BLOCK_START}.*?(?=\n*(?:{LogFileHandler.BLOCK_START}|\Z))", rf"\g<0>{LogFileHandler.BLOCK_END}", string, flags = re.MULTILINE | re.DOTALL)
        return string

    def remove_block_borders(string: str) -> str:
        return string.replace(LogFileHandler.BLOCK_START, "").replace(LogFileHandler.BLOCK_END, "")

    def add_braces(string: str) -> str:
        return string.replace("\n", "<br />\n")

    def add_log_level_style(string: str):
        def replacer(match_obj: re.Match[str]):
            if match_obj.group(1) is not None:
                return f"<span class='log-{match_obj.group(1).lower()}'>{match_obj.group()}</span>"
            return match_obj.group()

        return re.sub(rf"^{LogFileHandler.BLOCK_START}.*?\[(CRITICAL|ERROR|WARNING|INFO|DEBUG)\].*?{LogFileHandler.BLOCK_END}", replacer, string, flags = re.MULTILINE | re.DOTALL)

    def add_numbers_style(string: str):
        def replacer(match_obj: re.Match[str]):
            if match_obj.group(5) is not None:
                return match_obj.group()
            style_class = None
            if match_obj.group(1) is not None:
                style_class = "log-ip"
            elif match_obj.group(2) is not None:
                style_class = "log-date"
            elif match_obj.group(3) is not None:
                style_class = "log-time"
            elif match_obj.group(4) is not None:
                style_class = "log-number"
            if style_class is not None:
                if match_obj.group(7) is not None:
                    return "<span class='" + style_class + "'>" + match_obj.group(6) + "</span>" + match_obj.group(7)
                return "<span class='" + style_class + "'>" + match_obj.group() + "</span>"
            return match_obj.group()
        return re.sub(
            r"(?:((?:\d+\.){3}\d+)|((?:(?:\d+-){2}|(?:\d+/){1,2}|(?:\d+\.){2})\d+)|((?:\d+:){1,2}\d+(?:[,.]\d+)?)|(\b0(?:x[0-9a-fA-F]+|b[01]+)\b|(&#)?\b(\d+(?:[,.]\d+)?))(?(5);|(\w{1,3})?\b))",
            replacer, string)

    def add_string_style(string: str):
        return re.sub(r"(?:\"[^\"\n]*\")|(?:\'[^\'\n]*\')", r"<span class='log-string'>\g<0></span>", string)

    def log_style(string: str, add_br: bool = False) -> str:
        string = LogFileHandler.escape(string)
        string = LogFileHandler.add_block_borders(string)
        string = LogFileHandler.add_string_style(string)
        string = LogFileHandler.add_numbers_style(string)
        string = LogFileHandler.add_log_level_style(string)
        string = LogFileHandler.remove_block_borders(string)
        if add_br:
            string = LogFileHandler.add_braces(string)
        return string

    def validate_absolute_path(self, root: str, absolute_path: str) -> Optional[str]:
        root = os.path.abspath(root)
        if not root.endswith(os.path.sep):
            root += os.path.sep
        project_root = os.path.abspath(".")
        if not project_root.endswith(os.path.sep):
            project_root += os.path.sep
        if not (root).startswith(project_root):
            raise web.HTTPError(403, "Log file is not in root directory")
        if project_root == root:
            if self.default_filename is not None:
                sub_path = absolute_path[len(root):]
                if len(sub_path) > 0:
                    self.redirect(f"http://{self.request.host}/log/", permanent=True)
                    return None
                return os.path.join(root, self.default_filename)
            else:
                raise web.HTTPError(403, "Log folder is root directory, but default_filename is not set")
        return super().validate_absolute_path(root, absolute_path)

    def get(self, path: str):
        self.path = self.parse_url_path(path)
        del path  # make sure we don't refer to path instead of self.path again
        absolute_path = self.get_absolute_path(self.root, self.path)
        self.absolute_path = self.validate_absolute_path(self.root, absolute_path)
        del absolute_path
        if self.absolute_path is None:
            return
        log_file = os.path.basename(self.absolute_path)
        # logging.debug('Get log (path: %s) from (%s)', log_file, self.request.remote_ip)
        self.write('<html><head><title>PodTube Log (')
        self.write(log_file)
        self.write(')</title>')
        self.write('<link rel="shortcut icon" href="/favicon.ico">')
        self.write('<link rel="stylesheet" type="text/css" href="/log.css">')
        self.write('<meta charset="UTF-8">')
        self.write('</head><body><pre class="logger">')
        with open(self.absolute_path) as text:
            self.write(
                LogFileHandler.log_style(text.read().replace("\xEF\xBB\xBF", "", 1))
            )
        self.write('</pre></body></html>')
