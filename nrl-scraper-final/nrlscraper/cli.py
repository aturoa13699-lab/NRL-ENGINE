"""
CLI entrypoints for NRL Scraper (SPEC-1).

Usage:
    python -m nrlscraper.cli season 2024
    python -m nrlscraper.cli historical 1998 2025
"""
import argparse
import logging
import sys

from nrlscraper.scraper import NRLScraper, log_event
from nrlscraper.export import to_parquet, to_parquet_multi
from nrlscraper.config import settings

logger = logging.getLogger('nrlscraper')


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    )


def run_season(
    year: int,
    include_finals: bool = True,
    write_db: bool = True,
    export: bool = True,
) -> int:
    """
    Scrape a single season.

    Returns:
        Number of matches scraped
    """
    scraper = NRLScraper()
    rows = scraper.scrape_season(year, include_finals=include_finals)

    if not rows:
        logger.error(f'No rows scraped for season {year}')
        return 0

    # Write to database
    if write_db and settings.db_url:
        from nrlscraper.db import upsert_matches
        count = upsert_matches(rows)
        logger.info(f'Upserted {count} matches to database')

    # Export to Parquet
    if export:
        path = to_parquet(rows, 'matches', year)
        logger.info(f'Exported to {path}')

    log_event(event='season_done', season=year, matches=len(rows))
    return len(rows)


def run_historical(
    start_year: int,
    end_year: int,
    include_finals: bool = True,
    write_db: bool = True,
    export: bool = True,
) -> int:
    """
    Scrape multiple seasons sequentially.

    Returns:
        Total matches scraped
    """
    scraper = NRLScraper()
    all_rows = scraper.scrape_historical(start_year, end_year, include_finals=include_finals)

    if not all_rows:
        logger.error('No rows scraped')
        return 0

    # Write to database
    if write_db and settings.db_url:
        from nrlscraper.db import upsert_matches
        count = upsert_matches(all_rows)
        logger.info(f'Upserted {count} matches to database')

    # Export to Parquet (partitioned by season)
    if export:
        paths = to_parquet_multi(all_rows, 'matches')
        logger.info(f'Exported {len(paths)} season files')

    log_event(event='historical_done', start=start_year, end=end_year, matches=len(all_rows))
    return len(all_rows)


def main(argv=None):
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        prog='nrlscraper',
        description='NRL match data scraper',
    )
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')

    subparsers = parser.add_subparsers(dest='command', required=True)

    # Season command
    season_parser = subparsers.add_parser('season', help='Scrape a single season')
    season_parser.add_argument('year', type=int, help='Season year')
    season_parser.add_argument('--no-finals', action='store_true', help='Exclude finals')
    season_parser.add_argument('--no-db', action='store_true', help='Skip database write')
    season_parser.add_argument('--no-export', action='store_true', help='Skip Parquet export')

    # Historical command
    hist_parser = subparsers.add_parser('historical', help='Scrape multiple seasons')
    hist_parser.add_argument('start_year', type=int, help='Start year')
    hist_parser.add_argument('end_year', type=int, help='End year (inclusive)')
    hist_parser.add_argument('--no-finals', action='store_true', help='Exclude finals')
    hist_parser.add_argument('--no-db', action='store_true', help='Skip database write')
    hist_parser.add_argument('--no-export', action='store_true', help='Skip Parquet export')

    args = parser.parse_args(argv)
    setup_logging(args.verbose)

    if args.command == 'season':
        count = run_season(
            args.year,
            include_finals=not args.no_finals,
            write_db=not args.no_db,
            export=not args.no_export,
        )
        print(f'Scraped season {args.year}: {count} matches')
        sys.exit(0 if count > 0 else 1)

    elif args.command == 'historical':
        count = run_historical(
            args.start_year,
            args.end_year,
            include_finals=not args.no_finals,
            write_db=not args.no_db,
            export=not args.no_export,
        )
        print(f'Scraped {args.start_year}-{args.end_year}: {count} matches')
        sys.exit(0 if count > 0 else 1)


if __name__ == '__main__':
    main()
