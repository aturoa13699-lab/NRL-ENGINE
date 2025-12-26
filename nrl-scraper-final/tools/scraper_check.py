#!/usr/bin/env python3
"""
Quick health check for NRL scraper (SPEC-1).

Validates that scraper can fetch and parse at least one match.

Usage:
    python -m tools.scraper_check --season 2024 --limit 1
"""
import argparse
import sys

from nrlscraper import NRLScraper


def main():
    parser = argparse.ArgumentParser(description='Quick scraper health check')
    parser.add_argument('--season', type=int, default=2024)
    parser.add_argument('--limit', type=int, default=1)
    args = parser.parse_args()

    print(f'🏥 Health check: season {args.season}, limit {args.limit}')

    scraper = NRLScraper()
    rows = scraper.scrape_season(args.season, include_finals=True)

    if not rows:
        print('ERROR: No data returned from scraper')
        sys.exit(1)

    # Sample matches
    import random
    random.seed(42)
    sample = random.sample(rows, min(args.limit, len(rows)))

    for row in sample:
        # Check required non-empty fields
        required_nonempty = ['match_id', 'date', 'home_team', 'away_team', 'venue']
        for key in required_nonempty:
            value = row.get(key)
            if not value or (isinstance(value, float) and str(value) == 'nan'):
                print(f'ERROR: {key} is missing/empty in match {row.get("match_id")}')
                sys.exit(1)

        # Check scores are valid
        home_score = row.get('home_score')
        away_score = row.get('away_score')
        if not isinstance(home_score, int) or not isinstance(away_score, int):
            print(f'ERROR: Invalid score types in match {row.get("match_id")}')
            sys.exit(1)

        print(f'✓ Match: {row["match_id"]}')
        print(f'  Date: {row["date"]}')
        print(f'  {row["home_team"]} {home_score} vs {row["away_team"]} {away_score}')
        print(f'  Venue: {row["venue"]}')
        print(f'  Referee: {row.get("referee", "N/A")}')

    print(f'\n✅ Health check passed ({len(rows)} total matches available)')
    sys.exit(0)


if __name__ == '__main__':
    main()
