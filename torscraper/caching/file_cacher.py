import logging
import os
from abc import ABC

from torscraper.caching.base_cacher import BaseCacher
from torscraper.logger import set_formatter

set_formatter()
LOGGER = logging.getLogger(__name__)


class FileCacher(BaseCacher, ABC):

    EXTENSION = ""

    def __init__(
        self, cache_root=os.path.expanduser("~") + "/torscraper-cache/",
    ):
        self.cache_root = cache_root
        super().__init__()

    def setup_cache(self):
        super().setup_cache()
        if not os.path.exists(self.cache_root):
            LOGGER.debug(f"Cache directory '{self.cache_root} does not exist - creating cache.")
            try:
                os.makedirs(self.cache_root)
            except:
                LOGGER.debug(f"Error making cache.")
                raise
        else:
            LOGGER.debug(f"Cache directory '{self.cache_root} already exists - doing nothing.")

    def check_response_exists(self, name, **kwargs) -> bool:
        super().check_response_exists(name)
        file_path = self._get_file_path(name)
        return os.path.exists(file_path)

    def _get_file_path(self, name):
        return os.path.join(self.cache_root, name) + self.EXTENSION
