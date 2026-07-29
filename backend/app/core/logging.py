import logging
import re
import sys
from logging.handlers import RotatingFileHandler

from app.core.config import settings


class StructuredRedactingFormatter(logging.Formatter):
    def format(self, record):
        msg = str(record.msg)
        msg = re.sub(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", "[REDACTED_EMAIL]", msg)
        msg = re.sub(r"\b(0|\+84)\d{9}\b", "[REDACTED_PHONE]", msg)

        if "Received API query:" in msg and len(msg) > 60:
            msg = msg[:60] + "... [REDACTED_LONG_QUERY]"

        record.msg = msg
        return super().format(record)


def setup_logger(name: str = "legal_rag") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = StructuredRedactingFormatter(
        '{"time": "%(asctime)s", "level": "%(levelname)s", "src": "%(filename)s:%(lineno)d", "msg": "%(message)s"}'
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    log_dir = settings.project_root / "logs"
    log_dir.mkdir(exist_ok=True)
    file_handler = RotatingFileHandler(
        filename=log_dir / "app.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


logger = setup_logger()
