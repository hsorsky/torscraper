from stem import Signal
from stem.control import Controller
import requests
import re
from termcolor import colored
from pathlib import Path
import os
import errno


class Scraper:

    # TODO: add logging
    # TODO: add page caching
    # TODO: add headers (e.g. firefox browser header)
    # TODO: encoding and decoding?

    def __init__(self, tor_password, max_n_uses=5, socks_port=9050, control_port=9051, cache_root='/cache/'):
        self.tor_password = tor_password
        self.max_n_uses = max_n_uses
        self.socks_port = socks_port
        self.control_port = control_port
        self.cache_root = Path(cache_root) / 'scraped_pages'
        self._make_cache_root()
        self.tor_session = self._get_tor_session()
        self.ips_used = {}
        self._update_current_ip()

    def _make_cache_root(self):
        try:
            os.makedirs(self.cache_root)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

    def _get_tor_session(self):
        session = requests.session()
        session.proxies = {
            'http':  'socks5://127.0.0.1:{}'.format(self.socks_port),
            'https': 'socks5://127.0.0.1:{}'.format(self.socks_port),
        }
        return session

    def _update_current_ip(self):
        self.current_ip = re.search("[0-9.]*", self.tor_session.get('https://icanhazip.com/').text)[0]
        self.ips_used[self.current_ip] = 0

    def _refresh_ip(self):
        with Controller.from_port(port=self.control_port) as controller:
            controller.authenticate(password=self.tor_password)
            controller.signal(Signal.NEWNYM)
        self._update_current_ip()
        self._print_ip_related_stuff("New Tor connection processed with IP: {}".format(self.current_ip))

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

    def get_page_text(self, url, **kwargs):
        file_version_of_url = url.replace('/', '_')
        self._print_fetch_related_stuff("Page: {}".format(url))
        try:
            # get page from cache
            self._print_fetch_related_stuff("\tChecking cache for page")
            result = self._retrieve_from_cache(file_version_of_url)
            self._print_fetch_related_stuff("\tPage fetched from cache")
        except FileNotFoundError:
            self._print_fetch_related_stuff("\tPage not found in cache")
            # -- if used too many times, refresh ip -- #
            if self.n_uses >= self.max_n_uses:
                self._print_ip_related_stuff("\t\tMax uses reached on current IP: {}".format(self.current_ip))
                self._print_ip_related_stuff("\t\t\tSignalling for new IP...")
                self._refresh_ip()

            # -- get the page -- #
            self._print_fetch_related_stuff("\tFetching page from internet...")
            result = self.tor_session.get(url, **kwargs).text
            self._update_ip_dict(n_uses=1)
            self._print_fetch_related_stuff("\tPage fetched from internet")

            # -- cache the page -- #
            self._cache_page(file_version_of_url, result)

        return result

    @staticmethod
    def _print_ip_related_stuff(string):
        print(colored(string, 'blue'))

    @staticmethod
    def _print_fetch_related_stuff(string):
        print(colored(string, 'green'))

    def _cache_page(self, url, text):
        with open(self.cache_root / url, 'w') as f:
            f.write(text)

    def _retrieve_from_cache(self, url):
        with open(self.cache_root / url, 'r') as f:
            text = f.read()
        return text


# if __name__ == '__main__':
#     scraper = Scraper(tor_password='torpassword', cache_root='/Users/hsorsky/dev/torscraper/cache/')
#     for i in range(10):
#         scraper.get_page_text('http://www.google.com')
