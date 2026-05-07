import logging

LOG_FORMAT = "%(asctime)s - %(pathname)s:%(lineno)d - %(levelname)s - %(message)s"

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
)

logger = logging.getLogger(__name__)
