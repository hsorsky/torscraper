from stem import Signal
from stem.control import Controller
import requests
import re


class Scraper:

    # TODO: add logging

    def __init__(self, tor_password, max_n_uses=5, socks_port=9050, control_port=9051):
        self.tor_password = tor_password
        self.max_n_uses = max_n_uses
        self.socks_port = socks_port
        self.control_port = control_port
        self.tor_session = self._get_tor_session()
        self.ips_used = {}
        self._update_current_ip()

    def _get_tor_session(self):
        session = requests.session()
        # Tor uses the 9050 port as the default socks port
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
        print("New Tor connection processed with IP: {}".format(self.current_ip))

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

    def get(self, url, **kwargs):
        # -- if used too many times, refresh ip -- #
        if self.n_uses >= self.max_n_uses:
            print("Max uses reached on current IP: {}".format(self.current_ip))
            print("Signalling for new IP...")
            self._refresh_ip()

        # -- get the page -- #
        print("Fetching {}".format(url))
        result = self.tor_session.get(url, **kwargs)
        self._update_ip_dict(n_uses=1)
        return result
