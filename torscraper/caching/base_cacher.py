import logging
from abc import ABC, abstractmethod

from torscraper.logger import set_formatter

set_formatter()
LOGGER = logging.getLogger(__name__)


class BaseCacher(ABC):
    def __init__(self):
        self.setup_cache()

    @abstractmethod
    def setup_cache(self):
        LOGGER.debug("Setting up cache.")

    @abstractmethod
    def check_response_exists(self, name, **kwargs) -> bool:
        LOGGER.debug(f"Checking {name} exists")

    @abstractmethod
    def cache_response(self, response, name, **kwargs) -> None:
        LOGGER.debug(f"Caching response to {name}")

    @abstractmethod
    def get_response_from_cache(self, name, **kwargs):
        LOGGER.debug(f"Fetching response from cache, file name: {name}")
