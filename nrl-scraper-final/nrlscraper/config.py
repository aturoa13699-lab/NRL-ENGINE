"""
Configuration for NRL Scraper (SPEC-1).
"""
from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Immutable settings from environment."""

    db_url: str = os.getenv('DATABASE_URL', '')
    exports_dir: str = os.getenv('EXPORTS_DIR', 'data/exports')
    user_agent: str = os.getenv('USER_AGENT', 'nrlscraper/1.0 (+github)')
    req_timeout_s: float = float(os.getenv('REQ_TIMEOUT_S', '12'))
    rate_limit_rps: float = float(os.getenv('RATE_LIMIT_RPS', '1'))
    retries: int = int(os.getenv('RETRIES', '4'))
    season_start: int = int(os.getenv('SEASON_START', '1998'))
    season_end: int = int(os.getenv('SEASON_END', '2025'))


settings = Settings()
