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

    @classmethod
    def escape(cls, string: str) -> str:
        return string.replace("<", "&lt;").replace(">", "&gt;").replace("@", "&#64;").replace("=", "&#61;")

    @classmethod
    def add_block_start_border(cls, string: str) -> str:
        return re.sub(r"^[ \t]*(\d+-\d+-\d+ \d+:\d+:\d+)", rf"{cls.BLOCK_START}\g<0>", string, flags = re.MULTILINE)

    @classmethod
    def add_block_end_borders(cls, string):
        return re.sub(rf"^{cls.BLOCK_START}.*?(?=\n*(?:{cls.BLOCK_START}|\Z))", rf"\g<0>{cls.BLOCK_END}", string, flags = re.MULTILINE | re.DOTALL)

    @classmethod
    def add_block_borders(cls, string: str) -> str:
        string = cls.add_block_start_border(string)
        string = cls.add_block_end_borders(string)
        return string

    @classmethod
    def remove_block_borders(cls, string: str) -> str:
        return string.replace(cls.BLOCK_START, "").replace(cls.BLOCK_END, "")

    @classmethod
    def add_braces(cls, string: str) -> str:
        return string.replace("\n", "<br />\n")

    @classmethod
    def add_log_level_style(cls, string: str, use_block_borders: bool = True):
        def replacer(match_obj: re.Match[str]):
            if match_obj.group(1) is not None:
                return f"<span class='log-{match_obj.group(1).lower()}'>{match_obj.group()}</span>"
            return match_obj.group()

        if use_block_borders:
            return re.sub(rf"^{cls.BLOCK_START}.*?\[(CRITICAL|ERROR|WARNING|INFO|DEBUG)\].*?{LogFileHandler.BLOCK_END}", replacer, string, flags = re.MULTILINE | re.DOTALL)
        return re.sub(rf"^.*?\[(CRITICAL|ERROR|WARNING|INFO|DEBUG)\].*?(?=\n*\Z)", replacer, string, flags = re.MULTILINE | re.DOTALL)

    @classmethod
    def add_numbers_style(cls, string: str):
        def replacer(match_obj: re.Match[str]):
            if match_obj.group("html") is not None:
                return match_obj.group()
            style_class = None
            if match_obj.group("ip") is not None:
                style_class = "log-ip"
            elif match_obj.group("date") is not None:
                style_class = "log-date"
            elif match_obj.group("time") is not None:
                style_class = "log-time"
            elif match_obj.group("number") is not None:
                style_class = "log-number"
                if match_obj.group("hex") is not None:
                    style_class += " log-number-hex"
                if match_obj.group("bin") is not None:
                    style_class += " log-number-bin"
                if match_obj.group("simple_number") is not None:
                    style_class += " log-number-simple"

            if style_class is not None:
                return "<span class='" + style_class + "'>" + match_obj.group() + "</span>"
            return match_obj.group()

        return re.sub(
            r"(?:(?P<ip>(?:\d+\.){3}\d+)|(?# \
                )(?P<date>(?:(?:\d+-){2}|(?:\d+\/){1,2}|(?:\d+\.){2})\d+)|(?# \
                )(?P<time>(?:\d+:){1,2}\d+(?:[,.]\d+)?)|(?# \
                )(?P<html>&#\d+;)|(?# \
                )(?P<number>\b((?# \
                    )(?P<hex>0x[0-9a-fA-F]+)\b|(?# \
                    )(?P<bin>0b[01]+)\b|(?# \
                    )(?P<simple_number>\d+(?:[,.]\d+)?)(?=[\w-]{0,3}(?:[^\w-]|$))(?# \
                )))(?# \
            ))",
            replacer,
            string
        )

    @classmethod
    def add_string_style(cls, string: str):
        def replacer(match_obj: re.Match[str]):
            prefix = match_obj.group(1)
            return f"{'' if prefix is None else prefix}<span class='log-string'>{match_obj.group(2)}</span>"

        return re.sub(r"(?<!\\)(\\\\)*((?P<quote>(?P<is_double>\")|')(?:(?:\\\\)*(?(is_double)[^\"\\]*|[^\'\\]*)(?:\\\\)*(?:\\[^\\])?)*(?P=quote))", replacer, string)

    @classmethod
    def log_style(cls, string: str, add_br: bool = False) -> str:
        string = cls.escape(string)
        # string = cls.add_block_borders(string)
        # string = cls.add_string_style(string)
        # string = cls.add_numbers_style(string)
        # string = cls.add_log_level_style(string)
        # string = cls.remove_block_borders(string)
        string = cls.add_block_start_border(string)
        blocks = string.split(cls.BLOCK_START)
        for i in range(len(blocks)):
            block = blocks[i]
            block = cls.add_string_style(block)
            block = cls.add_numbers_style(block)
            block = cls.add_log_level_style(block, False)
            blocks[i] = block
        string = "".join(blocks)
        if add_br:
            string = cls.add_braces(string)
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
