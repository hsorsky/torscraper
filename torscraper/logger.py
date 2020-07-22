import logging

FMT = "%(asctime)s %(levelname)-4s %(filename)s:%(lineno)d - %(message)s"


def set_formatter(level=logging.INFO):
    """Set a custom formatter for logs with caller context.
    """
    logging.basicConfig(level=level, format=FMT)
