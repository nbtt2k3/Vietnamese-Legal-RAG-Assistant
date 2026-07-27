import logging
import sys
import os
from logging.handlers import RotatingFileHandler
from app.config import settings


import re

class StructuredRedactingFormatter(logging.Formatter):
    def format(self, record):
        msg = str(record.msg)
        # Redact emails and phone numbers (simple PII redaction)
        msg = re.sub(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', '[REDACTED_EMAIL]', msg)
        msg = re.sub(r'\b(0|\+84)\d{9}\b', '[REDACTED_PHONE]', msg)
        
        # Prevent logging full legal situations (truncate long queries)
        if "Received API query:" in msg and len(msg) > 60:
            msg = msg[:60] + "... [REDACTED_LONG_QUERY]"
            
        record.msg = msg
        return super().format(record)

def setup_logger(name: str = "legal_rag") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        formatter = StructuredRedactingFormatter(
            '{"time": "%(asctime)s", "level": "%(levelname)s", "src": "%(filename)s:%(lineno)d", "msg": "%(message)s"}'
        )
        
        # Console handler
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
        # File handler
        log_dir = settings.project_root / "logs"
        log_dir.mkdir(exist_ok=True)
        fh = RotatingFileHandler(
            filename=log_dir / "app.log",
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
            encoding="utf-8"
        )
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
    return logger

logger = setup_logger()
