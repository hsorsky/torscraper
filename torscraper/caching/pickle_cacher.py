import pickle

from torscraper.caching.file_cacher import FileCacher


class PickleCacher(FileCacher):

    EXTENSION = ".pkl"

    def cache_response(self, response, name: str, **kwargs) -> None:
        super().cache_response(response, name, **kwargs)
        file_path = self._get_file_path(name)
        with open(file_path, "wb") as f:
            pickle.dump(response, f)

    def get_response_from_cache(self, name, **kwargs) -> str:
        super().get_response_from_cache(name, **kwargs)
        file_path = self._get_file_path(name)
        with open(file_path, "rb") as f:
            return pickle.load(f)
