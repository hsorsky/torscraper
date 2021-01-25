import logging
import random
import re
import time
import warnings

import requests
from requests import Response, Session
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
    """Scraper class used to cache pages from the internet. Checks local cache for existence of page already. If page
    does not exist in local cache, fetches from internet using TOR and caches. Intended usage:

    >>> list_of_urls = [...]
    >>> scraper = Scraper()
    >>> for url in list_of_urls:
    >>>     scraper.scrape(url)

    By default, ``Scraper`` caches the response from the page by saving it to a pickle under ``~/torscraper-cache/``.
    If a bad response is received, the page will not be cached. For other functionality, one can subclass
    ``BaseCacher``, implementing ``setup_cache``, ``check_response_exists``, ``cache_response`` and
    ``get_response_from_cache``. For example, you may wish to cache responses to a DB so could create a
    ``DatabaseCacher`` class. Alternatively, you may just cache results in pickles, as default, and import them to DB
    afterwards.

    :param headers: Defaults to ``None``. Header to use for the session.
    :param randomize_user_agent: Defaults to ``False``. Whether or not to select a random user-agent header when we
        switch IP addresses. If ``True``, any user-agent header supplied in headers will be ignored upon getting a
        new IP address.
    :param max_n_uses: Defaults to ``5``. Max number of uses per IP address.
    :param minimum_wait_time: Defaults to ``5``. Minimum number of seconds to wait between requests.
    :param random_wait_time: Defaults to ``5``. Max amount of randomized time to wait between requests. Random extra
        wait time will be sample from a uniform distribution of ``U(0, random_wait_time)`` resulting in total wait time
        being distributed according to ``U(minimum_wait_time, minimum_wait_time + random_wait_time)``
    :param socks_port: Defaults to ``9050``. The TOR socks port setup on your machine.
    :param control_port: Defaults to ``9051``. The TOR control port setup on your machine.
    :param tor_password: Defaults to ``None``. The TOR password for your machine. If ``None`` will use an empty
        password, i.e. ``""``.
    :param cacher: Defaults to ``PickleCacher``. Cacher object used to cache request responses. Should implement
        ``check_response_exists`` and ``cache_response`` methods.
    :param ignore_cache: Defaults to ``False``. Whether or not to ignore what is already in the cache when
        scraping. Scraped pages will still be cached if this is ``False``.
    """

    def __init__(
        self,
        headers: dict = None,
        randomize_user_agent: bool = False,
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
        self.randomize_headers = randomize_user_agent
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
        self.set_last_scrape_time()

    def set_last_scrape_time(self):
        """Set the last time a page was scraped (i.e. request was made)."""
        self.last_scrape_time = time.time()
        return self.last_scrape_time

    def _validate_inputs(self):
        """ Validate the inputs.
        """
        if self.tor_password is None:
            warnings.warn("tor_password is None - setting to empty string")
            self.tor_password = ""

    def _get_tor_session(self) -> Session:
        """Get a new TOR session.
        :return: New session with appropriate headers.
        """
        session = requests.session()
        session.proxies = {
            "http": f"socks5://127.0.0.1:{self.socks_port}",
            "https": f"socks5://127.0.0.1:{self.socks_port}",
        }
        session.headers = self.headers or {}
        return session

    def _update_current_ip(self):
        """Update our current IP address and the counter for how many times each IP has been used.
        """
        self.current_ip = self._get_current_ip()
        self.ips_used[self.current_ip] = 0

    def _get_current_ip(self) -> str:
        """Get the current IP address

        :return: Current IP address
        """
        return re.search(
            "[0-9.]*", self.tor_session.get("https://icanhazip.com/").text
        )[0]

    def _refresh_ip(self):
        """Signal to TOR to get a new IP address. If we are randomizing headers, also get a new user-agent header.
        """
        with Controller.from_port(port=self.control_port) as controller:
            controller.authenticate(password=self.tor_password)
            controller.signal(Signal.NEWNYM)
        self._update_current_ip()
        if self.randomize_headers:
            self.tor_session.headers["User-Agent"] = random.choice(USER_AGENTS)
        self._log_ip_related(
            f"\t\t\tNew Tor connection processed with IP: {self.current_ip}"
        )

    def _update_ip_dict(self, n_uses: int):
        """Add to the tracker of the number of times we have used an IP address.

        :param n_uses: Number of times used.
        """
        self.ips_used[self.current_ip] += n_uses

    @property
    def n_uses(self):
        """
        :return: The number of times the current IP address has been used.
        """
        try:
            n_uses = self.ips_used[self.current_ip]
        except KeyError:
            n_uses = 0
            self.ips_used[self.current_ip] = n_uses
        return n_uses

    @staticmethod
    def get_file_name(url: str) -> str:
        """Get the equivalent file name of a URL

        :param url: URL to get the file name of.
        :return: File name of given URL
        """
        return url.replace("/", "__")

    def scrape(self, url: str, **kwargs):
        """Scrape the given URL, saving it using the instances cacher. Process is as follows:

        1. Convert the URL to a filename - currently we just replace "/" with "__".
        2. If ignoring the cache, skip to step 4. Else go to step 3.
        3. Check if the file already exists in the cache. If it exists, finish. If not, go to step 4.
        4. Get the response using the TOR session.
        5. If the response is successful (i.e. status code in the 200s) store in cache. If not, add to set of URLs
            that gave bad status codes.

        If an error occurs, the URLs giving bad responses will be printed.

        :param url: URL to cache.
        :param kwargs: kwargs
        """
        try:
            file_name = self.get_file_name(url)
            self._log_fetch_related(f"Page: {url}")
            if self.ignore_cache:
                self._log_fetch_related(f"\tIgnoring cache")
                fetch_from_internet = True
            else:
                self._log_fetch_related("\tChecking cache for page")
                exists_in_cache = self.cacher.check_response_exists(file_name)
                if exists_in_cache:
                    self._log_fetch_related("\tPage found in cache - skipping.")
                    fetch_from_internet = False
                else:
                    fetch_from_internet = True

            if fetch_from_internet:
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

    def _get_page_from_internet(self, url, **kwargs) -> Response:
        """Fetch the page from the internet, waiting an appropriate amount of time and rotating IP if necessary.

        :param url: URL of the page to get.
        :return: Page response.
        """
        self._log_fetch_related("\tPage not found in cache - fetching from internet")

        # if used the ip too many times, refresh
        if self.n_uses >= self.max_n_uses:
            self._log_ip_related(
                f"\t\tMax uses reached on current IP: {self.current_ip}\n"
                f"\t\t\tSignalling for new IP..."
            )
            self._refresh_ip()

        # get the page
        time_since_last_request = time.time() - self.last_scrape_time
        wait_time = max(
            self.minimum_wait_time
            + random.random() * self.random_wait_time
            - time_since_last_request,
            0,
        )

        self._log_fetch_related(
            f"\t\tSleeping for {wait_time:.2f}s to avoid getting blacklisted"
        )

        time.sleep(wait_time)
        self._log_fetch_related("\t\tFetching page from internet...")
        response = self.tor_session.get(url, **kwargs)
        self.set_last_scrape_time()
        self._update_ip_dict(n_uses=1)
        self._log_fetch_related("\t\tPage fetched from internet")

        return response

    @staticmethod
    def _log_ip_related(string):
        """Log info related to IP addresses.

        :param string: string to pass to the logger
        """
        LOGGER.info(colored(string, "blue"))

    @staticmethod
    def _log_fetch_related(string):
        """Log info related to fetching pages.

        :param string: string to pass to the logger
        """
        LOGGER.info(colored(string, "green"))
