import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from app.config.settings import settings

# Ensure logs directory exists
LOGS_DIR = "./logs"
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

LOG_FILE_PATH = os.path.join(LOGS_DIR, "app.log")

# Setup logging formats
CONSOLE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-12s | %(message)s"
FILE_FORMAT = (
    '{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", '
    '"file": "%(filename)s:%(lineno)d", "message": "%(message)s"}'
)

# Root logger level configuration
root_level = logging.DEBUG if settings.ENVIRONMENT == "development" else logging.INFO


def get_console_handler() -> logging.StreamHandler:
    """Creates a console handler emitting colored/simple logs."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(CONSOLE_FORMAT))
    handler.setLevel(root_level)
    return handler


def get_file_handler() -> RotatingFileHandler:
    """Creates a rotating file handler emitting structured JSON logs."""
    handler = RotatingFileHandler(
        LOG_FILE_PATH, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(FILE_FORMAT))
    handler.setLevel(logging.INFO)
    return handler


# Configure the base root logger
logging.basicConfig(
    level=root_level,
    handlers=[get_console_handler(), get_file_handler()],
)


# Define and expose child loggers for structured telemetry
def get_logger(name: str) -> logging.Logger:
    """Returns a pre-configured logger with the specified channel name."""
    logger = logging.getLogger(name)
    logger.setLevel(root_level)
    return logger


# Structured loggers
auth_logger = get_logger("auth")
api_logger = get_logger("api")
upload_logger = get_logger("upload")
parser_logger = get_logger("parser")
chunking_logger = get_logger("chunking")
embedding_logger = get_logger("embedding")
retriever_logger = get_logger("retriever")
llm_logger = get_logger("llm")
error_logger = get_logger("errors")
database_logger = get_logger("db")
system_logger = get_logger("system")
