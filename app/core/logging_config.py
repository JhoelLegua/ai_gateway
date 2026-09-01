"""
Centralized logging configuration for the AI Gateway Perimetral.

Features:
    - Clean Console Output: Silences third-party library verbosity (httpx,
      huggingface_hub, sentence_transformers, chromadb) so only relevant
      gateway events and HTTP request/response summaries appear in the terminal.
    - Daily Rotating File Logs: Full detailed operational and security audit
      logs are automatically saved to `./logs/gateway_YYYY-MM-DD.log` rotated at midnight.
"""

import logging
import os
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


class DailySuffixTimedRotatingFileHandler(TimedRotatingFileHandler):
    """
    A TimedRotatingFileHandler that names current and rotated log files
    with explicit date suffixes (e.g., logs/gateway_2026-08-30.log).
    """

    def __init__(self, log_dir: str, prefix: str = "gateway", **kwargs):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.prefix = prefix
        
        today_str = datetime.now().strftime("%Y-%m-%d")
        initial_file = self.log_dir / f"{self.prefix}_{today_str}.log"
        
        super().__init__(
            filename=str(initial_file),
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
            **kwargs,
        )

    def doRollover(self):
        super().doRollover()
        # Ensure the active file follows the new date format
        today_str = datetime.now().strftime("%Y-%m-%d")
        new_file = self.log_dir / f"{self.prefix}_{today_str}.log"
        self.baseFilename = str(new_file)


def setup_logging(log_dir: str = "./logs") -> None:
    """
    Configures console and file loggers.

    Console (stdout):
        - Clean format: `%(asctime)s | %(levelname)-7s | %(message)s`
        - Third-party noise suppressed.

    File (`./logs/gateway_YYYY-MM-DD.log`):
        - Detailed audit format: `%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s`
        - Rotated daily at midnight with 30-day retention.
    """
    # Suppress HuggingFace Windows symlink warnings and token warnings
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Remove default handlers to prevent duplicate lines
    root_logger.handlers.clear()

    # -----------------------------------------------------------------------
    # 1. Console Handler (Clean, minimal output)
    # -----------------------------------------------------------------------
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # -----------------------------------------------------------------------
    # 2. Daily Rotating File Handler (Comprehensive audit logging)
    # -----------------------------------------------------------------------
    file_handler = DailySuffixTimedRotatingFileHandler(
        log_dir=log_dir,
        prefix="gateway",
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # -----------------------------------------------------------------------
    # 3. Silence Third-Party Noisy Loggers in Console
    # -----------------------------------------------------------------------
    noisy_loggers = [
        "httpx",
        "httpcore",
        "huggingface_hub",
        "transformers",
        "sentence_transformers",
        "chromadb",
        "urllib3",
        "filelock",
        "multipart",
        "watchfiles",
        "asyncio",
    ]
    for name in noisy_loggers:
        logging.getLogger(name).setLevel(logging.WARNING)

    # Uvicorn access logger: let our custom HTTP middleware handle clean access logs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
