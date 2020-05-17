import logging
import random
import re
import time
import warnings

import requests
from stem import Signal
from stem.control import Controller
from termcolor import colored

from torscraper import PickleCacher
from torscraper.caching.base_cacher import BaseCacher
from torscraper.logger import set_formatter
from torscraper.user_agents import USER_AGENTS

set_formatter()
LOGGER = logging.getLogger(__name__)


class Scraper:
    def __init__(
        self,
        headers: dict = None,
        randomize_headers: bool = False,
        max_n_uses: int = 5,
        minimum_wait_time: int = 5,
        random_wait_time: int = 5,
        socks_port: int = 9050,
        control_port: int = 9051,
        tor_password: str = None,
        cacher: BaseCacher = PickleCacher(),
        ignore_cache: bool = False,
    ):
        self.headers = headers
        self.randomize_headers = randomize_headers
        self.max_n_uses = max_n_uses
        self.minimum_wait_time = minimum_wait_time
        self.random_wait_time = random_wait_time
        self.socks_port = socks_port
        self.control_port = control_port
        self.tor_password = tor_password
        self.cacher = cacher
        self.ignore_cache = ignore_cache

        self._validate_inputs()

        self.tor_session = self._get_tor_session()
        self.ips_used = {}
        self._update_current_ip()
        self.bad_response_urls = set()

    def _validate_inputs(self):
        if self.tor_password is None:
            warnings.warn("tor_password is None - setting to empty string")
            self.tor_password = ""

    def _get_tor_session(self):
        session = requests.session()
        session.proxies = {
            "http": f"socks5://127.0.0.1:{self.socks_port}",
            "https": f"socks5://127.0.0.1:{self.socks_port}",
        }
        session.headers = self.headers
        return session

    def _update_current_ip(self):
        self.current_ip = self._get_current_ip()
        self.ips_used[self.current_ip] = 0

    def _get_current_ip(self):
        return re.search(
            "[0-9.]*", self.tor_session.get("https://icanhazip.com/").text
        )[0]

    def _refresh_ip(self):
        with Controller.from_port(port=self.control_port) as controller:
            controller.authenticate(password=self.tor_password)
            controller.signal(Signal.NEWNYM)
        self._update_current_ip()
        if self.randomize_headers:
            self.tor_session.headers = random.choice(USER_AGENTS)
        self._log_ip_related(
            f"\t\t\tNew Tor connection processed with IP: {self.current_ip}"
        )

    def _update_ip_dict(self, n_uses):
        self.ips_used[self.current_ip] += n_uses

    @property
    def n_uses(self):
        try:
            n_uses = self.ips_used[self.current_ip]
        except KeyError:
            n_uses = 0
            self.ips_used[self.current_ip] = n_uses
        return n_uses

    @staticmethod
    def get_file_name(url):
        return url.replace("/", "__")

    def scrape(self, url, **kwargs):
        try:
            file_name = self.get_file_name(url)
            self._log_fetch_related(f"Page: {url}")
            if self.ignore_cache:
                self._log_fetch_related(f"\tIgnoring cache")
            else:
                self._log_fetch_related("\tChecking cache for page")
                exists_in_cache = self.cacher.check_response_exists(file_name)
                if exists_in_cache:
                    self._log_fetch_related("\tPage found in cache - skipping.")
                else:
                    response = self._get_page_from_internet(url, **kwargs)

                    # check its a 200 code - this means success
                    success = response.status_code // 100 == 2
                    if success:
                        self.cacher.cache_response(response, file_name)
                    else:
                        self._log_fetch_related(
                            f"\tBad response status code {response.status_code}. Not caching."
                        )
                        self.bad_response_urls.add(url)
        except:
            print(f"\n{self.bad_response_urls}\n")
            raise

    def _get_page_from_internet(self, url, **kwargs):
        self._log_fetch_related("\tPage not found in cache - fetching from internet")

        # if used the ip too many times, refresh
        if self.n_uses >= self.max_n_uses:
            self._log_ip_related(
                f"\t\tMax uses reached on current IP: {self.current_ip}\n"
                f"\t\t\tSignalling for new IP..."
            )
            self._refresh_ip()

        # get the page
        wait_time = self.minimum_wait_time + random.random() * self.random_wait_time

        self._log_fetch_related(
            f"\t\tSleeping for {wait_time:.2f}s to avoid getting blacklisted"
        )

        time.sleep(wait_time)
        self._log_fetch_related("\t\tFetching page from internet...")
        response = self.tor_session.get(url, **kwargs)
        self._update_ip_dict(n_uses=1)
        self._log_fetch_related("\t\tPage fetched from internet")

        return response

    @staticmethod
    def _log_ip_related(string):
        LOGGER.info(colored(string, "blue"))

    @staticmethod
    def _log_fetch_related(string):
        LOGGER.info(colored(string, "green"))
