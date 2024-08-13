import logging
import requests
import utils
import re
import os

from configparser import ConfigParser
from tornado import web

HTTP_PROXY = None
HTTPS_PROXY = None
PROXIES = None

AUDIO_DIR = "./audio"

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
    return utils.get_env_or_config_option(conf, env_name, config_name, "proxy", default_value=default_value)

def init(conf: ConfigParser):
    """
    Initializes the configuration settings for the system.

    Args:
        conf (ConfigParser): The configuration parser object.

    Returns:
        None
    """
    global HTTP_PROXY, HTTPS_PROXY, PROXIES
    HTTP_PROXY  = get_env_or_config_option(conf, "PROXY_HTTP_PROXY" , "proxy_http_proxy" , default_value=None)
    HTTPS_PROXY = get_env_or_config_option(conf, "PROXY_HTTPS_PROXY", "proxy_https_proxy", default_value=None)

    if any(proxy is not None for proxy in [HTTP_PROXY, HTTPS_PROXY]):
        PROXIES = {}
    if HTTP_PROXY is not None:
        PROXIES["http"] = HTTP_PROXY
    if HTTPS_PROXY is not None:
        PROXIES["https"] = HTTPS_PROXY

class ProxyRssHandler(web.RequestHandler):

    def initialize(self, proxy_handler_path: str):
        """
        Initializes the object with the given video and audio handler paths.

        :param proxy_handler_path: A string representing the path to the proxy handler.
        """
        self.proxy_handler_path = proxy_handler_path

    def get(self, address: str) -> None:

        logging.info(f"Get proxy-rss for {address}")
        if self.request.arguments:
            logging.debug(f"Get proxy-rss for {address}?{self.request.arguments}")
        
        response = requests.get(
            url=address,
            params=self.request.arguments,
            proxies=PROXIES
        )
        if (response.status_code != 200):
            logging.error('Error get RSS: %s (%d)', response.reason, response.status_code)
            self.send_error(reason='Error get RSS')
            return

        has_content = not (response.status_code in (204, 304) or (100 <= response.status_code < 200))

        for (header_key, header_value) in response.headers.items():
            if has_content or header_key != 'content-length':
                # logging.debug(f"{header_key=}")
                # logging.debug(f"{header_value=}")
                self.set_header(header_key, header_value)

        self.write(
            re.sub(
                r"(\"|\&\#34\;)(https?://)",
                repl=rf"\g<1>{self.request.protocol}://{self.request.host}{self.proxy_handler_path}\g<2>",
                string=response.text,
                flags=re.MULTILINE))

class ProxyHandler(web.RequestHandler):
    CONTENT_CHUNK_SIZE = 10 * 1024

    def initialize(self, proxy_handler_path: str):
        """
        Initializes the object with the given video and audio handler paths.

        :param proxy_handler_path: A string representing the path to the proxy handler.
        """
        self.proxy_handler_path = proxy_handler_path

    def make_request(self, address: str, method: str) -> None:
        global PROXIES, AUDIO_DIR

        logging.info(f"Make request ({method}): {address=}")
        if self.request.arguments:
            logging.debug(f"Make request ({method}): {address=}; {self.request.arguments=}")
        
        filename = address
        if filename.endswith(".mp3"):
            filename = filename[:-4]
        filename = re.sub(r'\W+', '_', address)
        filename = filename + ".mp3"

        file_path = f"{AUDIO_DIR}/{filename}"
        if os.path.exists(file_path):
            with open(file_path, "rb") as file:
                logging.debug(f"Return cached file for '{address}' ('{file.name}')")
                self.write(file.read())
                self.finish()
                return
        
        headers = None
        for (header_key, header_value) in self.request.headers.items():
            if not headers:
                headers = {}
            if str(header_key).lower() != "host":
                headers[header_key] = header_value

        cookies = None
        for (cookie_key, cookie_value) in self.request.cookies.items():
            if not cookies:
                cookies = {}
            cookies[cookie_key] = cookie_value.output()

        files = None
        for (files_key, files_value) in self.request.files.items():
            if not files:
                files = []
            for file_info in files_value:
                files.append((files_key, (file_info.filename, file_info.body, file_info.content_type)))

        response = requests.request(
            method=method,
            url=address,
            params=self.request.arguments,
            data=self.request.body,
            headers=headers,
            cookies=cookies,
            files=files,
            proxies=PROXIES,
        )

        self.set_status(response.status_code, response.reason)
        has_content = not (response.status_code in (204, 304) or (100 <= response.status_code < 200))

        for (header_key, header_value) in response.headers.items():
            if has_content or header_key != 'content-length':
                # logging.debug(f"{header_key=}")
                # logging.debug(f"{header_value=}")
                self.set_header(header_key, header_value)

        if has_content:
            content = response.content
            # content = re.sub(
            #     r"(\"|\&\#34\;)(https?://)",
            #     repl=rf"\g<1>{self.request.protocol}://{self.request.host}{self.proxy_handler_path}\g<2>",
            #     string=response.text,
            #     flags=re.MULTILINE)
            self.write(content)
            if response.headers.get("Content-Type") == "audio/mpeg":
                if filename.endswith(".mp3"):
                    filename = filename[:-4]
                filename = re.sub(r'\W+', '_', address)
                filename = filename + ".mp3"
                
                with open(file_path, "wb") as file:
                    logging.debug(f"Save file from '{address}' to '{file.name}'")
                    file.write(content)

        for cookie in response.cookies:
            self.set_cookie(
                name=cookie.name,
                value=cookie.value,
                domain=cookie.domain,
                expires=cookie.expires,
                path=cookie.path
            )

        self.finish()

    def get(self, address: str) -> None:
        self.make_request(address, "get")
    
    def post(self, address: str) -> None:
        self.make_request(address, "post")

    def head(self, address: str) -> None:
        self.make_request(address, "head")

    def delete(self, address: str) -> None:
        self.make_request(address, "delete")

    def patch(self, address: str) -> None:
        self.make_request(address, "patch")

    def put(self, address: str) -> None:
        self.make_request(address, "put")

    def options(self, address: str) -> None:
        self.make_request(address, "options")
