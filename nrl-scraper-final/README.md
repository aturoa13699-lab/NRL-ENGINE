# NRL Scraper 🏉

Production-grade NRL (National Rugby League) match data scraper.

[![CI](https://github.com/YOUR_USERNAME/nrl-scraper/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/nrl-scraper/actions/workflows/ci.yml)

## Scope

- **Competitions**: NRL Premiership only (1998-2025)
- **Matches**: Regular season (Rounds 1-27) + Finals series
- **Excludes**: Trials, State of Origin, All Stars, NRLW

## Quick Start

```bash
# Install
pip install -r requirements.txt

# Scrape 2024 season (no DB)
python -m nrlscraper.season 2024 --no-db

# Validate 2024 data
python -m tools.validate_aggregate --season 2024 --expected-total 213 --expected-regular 204

# Run tests
pip install -r requirements-dev.txt
pytest -m "not integration"  # Unit tests only
pytest                        # All tests (hits live RLP)
```

## Data Sources

| Source | Data | Status |
|--------|------|--------|
| [Rugby League Project](https://www.rugbyleagueproject.org) | Results, venues, referees, crowds | ✅ Primary |
| NRL.com | Detailed match stats | 📋 Template (post-MVP) |

## Output

- **PostgreSQL 15**: Production database (Railway)
- **Parquet**: Partitioned snapshots in `data/exports/`

## CLI Usage

```bash
# Single season
python -m nrlscraper.season 2024
python -m nrlscraper.season 2024 --no-finals --no-db

# Historical backfill
python -m nrlscraper.historical 1998 2025
python -m nrlscraper.historical 2020 2024 --no-db
```

## API

```python
from nrlscraper import NRLScraper

scraper = NRLScraper()

# Single season
rows = scraper.scrape_season(2024, include_finals=True)

# Multiple seasons
rows = scraper.scrape_historical(2020, 2024)

# Returns list of dicts with:
# match_id, date, season, round, home_team, away_team,
# home_score, away_score, venue, referee, crowd, ...
```

## Data Schema

| Column | Type | Description |
|--------|------|-------------|
| `match_id` | TEXT | Stable SHA-1 hash |
| `source` | TEXT | 'RLP' or 'MOCK' |
| `date` | DATE | Match date |
| `season` | INT | Season year |
| `round` | TEXT | Round label |
| `home_team` | TEXT | Canonical team name |
| `away_team` | TEXT | Canonical team name |
| `home_score` | INT | Home team score |
| `away_score` | INT | Away team score |
| `venue` | TEXT | Normalized venue |
| `referee` | TEXT | Match referee |
| `crowd` | INT | Attendance |
| `*_raw` | TEXT | Original values (traceability) |

## Validation Targets (2024)

- 204 regular season matches
- 9 finals matches
- 213 total
- 17 unique teams
- Each team plays 24 regular season games

## CI/CD

GitHub Actions runs:
- **Lint**: ruff check + format
- **Unit Tests**: pytest (no network)
- **Integration Tests**: RLP 2024 validation (main branch only)
- **Weekly Healthcheck**: Tuesday ~09:30 AEST

## Database Setup

```bash
# Bootstrap PostgreSQL schema
psql "$DATABASE_URL" -f scripts/bootstrap_db.sql

# Write 2024 to DB
python -m nrlscraper.season 2024
```

## Development

```bash
# Setup
python -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt

# Lint
ruff check .
ruff format .

# Test
pytest -v -m "not integration"  # Unit tests
pytest -v                        # All tests
```

## Operations

See [docs/ops.md](docs/ops.md) for:
- QA queries
- Troubleshooting guide
- KPIs / SLOs

## License

MIT
