#!/usr/bin/env python
"""
NRL Scraper - Railway Entry Point (One-Shot Worker)

Reads env vars and runs once, then exits cleanly.

Environment Variables:
    MODE            - 'season' (default) or 'historical'
    SEASON          - Year to scrape (e.g., 2024)
    INCLUDE_FINALS  - '1' to include finals (default: '1')
    WRITE_DB        - '1' to write to database (requires DATABASE_URL)
    EXPORT          - '1' to export to parquet
    START_YEAR      - Start year for historical mode
    END_YEAR        - End year for historical mode
    DATABASE_URL    - PostgreSQL connection string

Example Railway Variables:
    MODE=season
    SEASON=2024
    INCLUDE_FINALS=1
    WRITE_DB=1
    DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db
"""

import os
import sys
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Log version and deployment info at boot
try:
    from nrlscraper.__version__ import VERSION as _VER
except Exception:
    _VER = {"commit": "unknown", "touched": "unknown"}

deploy_id = os.getenv("RAILWAY_DEPLOYMENT_ID", "unknown")
logger.info(
    "boot: version_commit=%s version_built=%s railway_deployment_id=%s",
    _VER.get("commit"),
    _VER.get("touched"),
    deploy_id,
)


def get_env_bool(key: str, default: bool = False) -> bool:
    """Get boolean from env var (1/true/yes = True)."""
    val = os.getenv(key, '').lower()
    if val in ('1', 'true', 'yes'):
        return True
    if val in ('0', 'false', 'no'):
        return False
    return default


def run_season_scrape(season: int, include_finals: bool, write_db: bool, export: bool):
    """Scrape a single season."""
    from nrlscraper import NRLScraper
    from nrlscraper.export import export_to_parquet

    logger.info(f"Scraping season {season} (finals={include_finals})")

    scraper = NRLScraper()
    matches = scraper.scrape_season(season, include_finals=include_finals)

    logger.info(f"Scraped {len(matches)} matches")

    if not matches:
        logger.warning("No matches found!")
        return 0

    # Write to database
    if write_db:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            logger.error("WRITE_DB=1 but DATABASE_URL not set!")
            return 1

        from nrlscraper.db import get_engine, upsert_matches

        logger.info("Writing to database...")
        engine = get_engine(database_url)
        count = upsert_matches(engine, matches)
        logger.info(f"Wrote {count} matches to database")

    # Export to parquet
    if export:
        logger.info("Exporting to parquet...")
        path = export_to_parquet(matches, prefix=f"nrl_{season}")
        logger.info(f"Exported to {path}")

    return 0


def run_historical_scrape(start_year: int, end_year: int, write_db: bool, export: bool):
    """Scrape historical range."""
    from nrlscraper import NRLScraper
    from nrlscraper.export import export_to_parquet

    logger.info(f"Scraping historical: {start_year}-{end_year}")

    scraper = NRLScraper()
    all_matches = []

    for year in range(start_year, end_year + 1):
        logger.info(f"  Scraping {year}...")
        matches = scraper.scrape_season(year, include_finals=True)
        all_matches.extend(matches)
        logger.info(f"    Got {len(matches)} matches")

    logger.info(f"Total: {len(all_matches)} matches")

    if not all_matches:
        logger.warning("No matches found!")
        return 0

    # Write to database
    if write_db:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            logger.error("WRITE_DB=1 but DATABASE_URL not set!")
            return 1

        from nrlscraper.db import get_engine, upsert_matches

        logger.info("Writing to database...")
        engine = get_engine(database_url)
        count = upsert_matches(engine, all_matches)
        logger.info(f"Wrote {count} matches to database")

    # Export to parquet
    if export:
        logger.info("Exporting to parquet...")
        path = export_to_parquet(all_matches, prefix=f"nrl_{start_year}_{end_year}")
        logger.info(f"Exported to {path}")

    return 0


def main():
    """Main entry point."""
    start_time = datetime.now()

    print("=" * 60)
    print("NRL SCRAPER - Railway Worker")
    print("=" * 60)

    # Read configuration from environment
    mode = os.getenv('MODE', 'season').lower()
    season = int(os.getenv('SEASON', datetime.now().year))
    include_finals = get_env_bool('INCLUDE_FINALS', default=True)
    write_db = get_env_bool('WRITE_DB', default=False)
    export = get_env_bool('EXPORT', default=False)
    start_year = int(os.getenv('START_YEAR', 2020))
    end_year = int(os.getenv('END_YEAR', datetime.now().year))

    logger.info(f"Mode: {mode}")
    logger.info(f"Season: {season}")
    logger.info(f"Include Finals: {include_finals}")
    logger.info(f"Write DB: {write_db}")
    logger.info(f"Export: {export}")

    if write_db and not os.getenv('DATABASE_URL'):
        logger.error("WRITE_DB=1 but DATABASE_URL not set!")
        return 1

    print("=" * 60)

    try:
        if mode == 'historical':
            exit_code = run_historical_scrape(start_year, end_year, write_db, export)
        else:
            exit_code = run_season_scrape(season, include_finals, write_db, export)

        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Completed in {duration:.1f}s")

        return exit_code

    except Exception as e:
        logger.error(f"FAILED: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
