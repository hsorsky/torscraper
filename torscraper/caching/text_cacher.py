from torscraper.caching.file_cacher import FileCacher


class TextCacher(FileCacher):

    EXTENSION = ".txt"

    def cache_response(self, response, name: str, **kwargs) -> None:
        super().cache_response(response, name, **kwargs)
        file_path = self._get_file_path(name)
        with open(file_path, "w") as f:
            f.write(response.text)

    def get_response_from_cache(self, name, **kwargs) -> str:
        super().get_response_from_cache(name, **kwargs)
        file_path = self._get_file_path(name)
        with open(file_path, "r") as f:
            return f.read()
