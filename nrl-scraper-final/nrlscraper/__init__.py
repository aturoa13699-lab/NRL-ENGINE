"""
NRL Scraper - Production-grade NRL match data scraper.

SPEC-1 Implementation:
- Scrapes NRL Premiership 1998-2025 (regular season + finals)
- Primary source: Rugby League Project (RLP)
- Outputs: PostgreSQL 15 + Parquet exports
"""

__version__ = '1.0.0'

from nrlscraper.models import MatchRow
from nrlscraper.normalize import normalize_team, normalize_venue
from nrlscraper.scraper import NRLScraper

__all__ = [
    'NRLScraper',
    'MatchRow',
    'normalize_team',
    'normalize_venue',
]
