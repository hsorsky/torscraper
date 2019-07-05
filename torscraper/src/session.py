import random
import re
import time

import requests
from stem import Signal
from stem.control import Controller
from termcolor import colored


class Session(requests.Session):

	def __init__(self, tor_password, headers=None, max_n_uses=5, minimum_wait_time=5, random_wait_time=5, socks_port=9050, control_port=9051):
		super().__init__()
		self.headers = headers
		self.proxies = {
			'http': f'socks5://127.0.0.1:{socks_port}',
			'https': f'socks5://127.0.0.1:{socks_port}',
		}
		self.tor_password = tor_password
		self.max_n_uses = max_n_uses
		self.minimum_wait_time = minimum_wait_time
		self.random_wait_time = random_wait_time
		self.socks_port = socks_port
		self.control_port = control_port
		self.ips_used = {}
		self._update_current_ip()

	def _update_current_ip(self):
		self.current_ip = re.search(r"[0-9.]*", self.get('https://icanhazip.com/').text)[0]
		self.ips_used[self.current_ip] = 0

	def _refresh_ip(self):
		with Controller.from_port(port=self.control_port) as controller:
			controller.authenticate(password=self.tor_password)
			controller.signal(Signal.NEWNYM)
		self._update_current_ip()
		self._print_ip_related_stuff("\t\t\tNew Tor connection processed with IP: {}".format(self.current_ip))

	def _update_ip_dict(self, n_uses):
		self.ips_used[self.current_ip] += n_uses

	def tor_get(self, url, **kwargs):
		self._print_fetch_related_stuff("Page: {}".format(url))

		# -- if used too many times, refresh ip -- #
		if self.n_uses >= self.max_n_uses:
			self._print_ip_related_stuff("\t\tMax uses reached on current IP: {}".format(self.current_ip))
			self._print_ip_related_stuff("\t\t\tSignalling for new IP...")
			self._refresh_ip()
		else:
			wait_time = self.minimum_wait_time + random.random() * self.random_wait_time
			self._print_fetch_related_stuff("\tSleeping for {:.2f}s to avoid getting blacklisted".format(wait_time))
			time.sleep(wait_time)

		# -- get the page -- #
		self._print_fetch_related_stuff("\tFetching page from internet...")
		result = super().get(url, **kwargs)
		self._update_ip_dict(n_uses=1)
		self._print_fetch_related_stuff("\tPage fetched from internet")

		return result

	@property
	def n_uses(self):
		try:
			n_uses = self.ips_used[self.current_ip]
		except KeyError:
			n_uses = 0
			self.ips_used[self.current_ip] = n_uses
		return n_uses

	@staticmethod
	def _print_ip_related_stuff(string):
		print(colored(string, 'blue'))

	@staticmethod
	def _print_fetch_related_stuff(string):
		print(colored(string, 'green'))