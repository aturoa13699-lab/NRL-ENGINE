#!/usr/bin/env python3
"""
Aggregate validation tool for NRL scraper (SPEC-1).

Validates season data against expected totals and coverage.

Usage:
    python -m tools.validate_aggregate --season 2024 --expected-total 213 --expected-regular 204
"""

import argparse
import sys
from datetime import date

import pandas as pd

from nrlscraper import NRLScraper

# 2024 season bounds
START_2024 = date(2024, 3, 2)
END_2024 = date(2024, 10, 6)


def main():
    parser = argparse.ArgumentParser(description='Validate scraped season data')
    parser.add_argument('--season', type=int, required=True)
    parser.add_argument('--expected-total', type=int, required=True)
    parser.add_argument('--expected-regular', type=int, required=True)
    parser.add_argument('--include-finals', action='store_true', default=True)
    args = parser.parse_args()

    print(f'🔍 Validating season {args.season}...')

    scraper = NRLScraper()
    rows = scraper.scrape_season(args.season, include_finals=args.include_finals)

    if not rows:
        print('ERROR: empty result from scraper')
        sys.exit(2)

    df = pd.DataFrame(rows)

    # Check required columns
    required = {
        'match_id',
        'date',
        'season',
        'round',
        'home_team',
        'away_team',
        'home_score',
        'away_score',
        'venue',
        'referee',
        'crowd',
    }
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f'ERROR: missing columns: {missing}')
        sys.exit(2)

    # Normalize date
    df['date'] = pd.to_datetime(df['date']).dt.date

    # Split regular vs finals
    is_finals = df['round'].str.contains('Final', case=False, na=False)
    reg = df.loc[~is_finals]
    fin = df.loc[is_finals]

    total = len(df)
    total_reg = len(reg)

    ok = True

    # Expected counts
    if total != args.expected_total:
        print(f'ERROR: expected total {args.expected_total}, got {total}')
        ok = False
    else:
        print(f'✓ Total matches: {total}')

    if total_reg != args.expected_regular:
        print(f'ERROR: expected regular {args.expected_regular}, got {total_reg}')
        ok = False
    else:
        print(f'✓ Regular season: {total_reg}')

    print(f'✓ Finals: {len(fin)}')

    # Team coverage: 17 unique teams (2023+)
    teams = pd.unique(pd.concat([reg['home_team'], reg['away_team']], ignore_index=True))
    expected_teams = 17 if args.season >= 2023 else 16
    if len(teams) != expected_teams:
        print(f'WARNING: expected {expected_teams} unique teams, got {len(teams)}')
        # Don't fail on this for historical seasons
    else:
        print(f'✓ Teams: {len(teams)}')

    # Each team plays 24 regular season games (modern era)
    if args.season >= 2007:
        for t in teams:
            played = ((reg['home_team'] == t) | (reg['away_team'] == t)).sum()
            if played != 24:
                print(f'ERROR: team {t} played {played} regular-season games (expected 24)')
                ok = False

        if ok:
            print('✓ All teams played 24 games')

    # Date window sanity (2024)
    if args.season == 2024:
        min_date = reg['date'].min()
        max_date = df['date'].max()
        if not (min_date >= START_2024 and max_date <= END_2024):
            print(
                f'ERROR: date range {min_date}..{max_date} outside expected {START_2024}..{END_2024}'
            )
            ok = False
        else:
            print(f'✓ Date range: {min_date} to {max_date}')

    # Check for nulls in critical fields
    crit = ['match_id', 'home_team', 'away_team']
    nulls = df[crit].isna().sum()
    bad = nulls[nulls > 0]
    if not bad.empty:
        print(f'ERROR: nulls in critical fields:\n{bad}')
        ok = False
    else:
        print('✓ No nulls in identity fields')

    # Summary
    print('\n📊 Summary:')
    print(f'   Total: {total} | Regular: {total_reg} | Finals: {len(fin)}')
    print(f'   Teams: {len(teams)} | Venues: {df["venue"].nunique()}')
    print(
        f'   Referees: {df["referee"].dropna().nunique()} (missing: {df["referee"].isna().sum()})'
    )

    if ok:
        print(f'\n✅ PASS: season {args.season} validated successfully')
        sys.exit(0)
    else:
        print(f'\n❌ FAIL: season {args.season} validation failed')
        sys.exit(1)


if __name__ == '__main__':
    main()
