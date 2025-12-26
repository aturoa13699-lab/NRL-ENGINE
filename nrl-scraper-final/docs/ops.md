# NRL Scraper – Ops

## Schedules

- **Weekly health check**: Tue ~09:30 Australia/Sydney (CI cron: MON 22:30 UTC)
- **Manual trigger**: Actions → "Run workflow" with `season` input (defaults to 2024)

## Environment

- `.env` (local, not committed): `DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db`
- CI healthcheck does **not** write to DB; prod writes only on protected branches

## Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Validate 2024 locally (no DB write)
python -m tools.validate_aggregate --season 2024 --expected-total 213 --expected-regular 204

# Write 2024 to DB + export Parquet (requires DATABASE_URL)
python -m nrlscraper.season 2024

# Scrape without DB (Parquet only)
python -m nrlscraper.season 2024 --no-db

# Historical backfill
python -m nrlscraper.historical 1998 2025
```

## QA Queries (PostgreSQL)

### Totals & Finals Split

```sql
WITH f AS (
    SELECT *, (round ILIKE '%final%') AS is_finals 
    FROM matches 
    WHERE season = 2024
)
SELECT 
    COUNT(*) AS total,
    SUM(CASE WHEN is_finals THEN 1 ELSE 0 END) AS finals,
    SUM(CASE WHEN NOT is_finals THEN 1 ELSE 0 END) AS regular
FROM f;
```

### Identity Nulls

```sql
SELECT
    SUM(CASE WHEN match_id IS NULL THEN 1 ELSE 0 END) AS match_id_nulls,
    SUM(CASE WHEN home_team IS NULL THEN 1 ELSE 0 END) AS home_nulls,
    SUM(CASE WHEN away_team IS NULL THEN 1 ELSE 0 END) AS away_nulls,
    SUM(CASE WHEN venue IS NULL THEN 1 ELSE 0 END) AS venue_nulls,
    SUM(CASE WHEN referee IS NULL THEN 1 ELSE 0 END) AS referee_nulls
FROM matches 
WHERE season = 2024;
```

### Duplicates (should be 0)

```sql
SELECT season, date, home_team, away_team, COUNT(*) c
FROM matches 
GROUP BY 1, 2, 3, 4 
HAVING COUNT(*) > 1;
```

### Season Bounds

```sql
SELECT MIN(date) AS first_match, MAX(date) AS last_match
FROM matches 
WHERE season = 2024;
```

### Normalization Hit-Rate

```sql
SELECT
    100.0 * AVG(CASE WHEN home_team = home_team_raw THEN 0 ELSE 1 END)::numeric AS home_norm_pct,
    100.0 * AVG(CASE WHEN away_team = away_team_raw THEN 0 ELSE 1 END)::numeric AS away_norm_pct,
    100.0 * AVG(CASE WHEN COALESCE(venue,'') = COALESCE(venue_raw,'') THEN 0 ELSE 1 END)::numeric AS venue_norm_pct
FROM matches 
WHERE season = 2024;
```

### Season Summary Table

```sql
SELECT 
    season,
    COUNT(*) AS matches,
    SUM(CASE WHEN round ILIKE '%final%' THEN 1 ELSE 0 END) AS finals,
    MIN(date) AS first_date,
    MAX(date) AS last_date
FROM matches
GROUP BY season
ORDER BY season;
```

## Troubleshooting

### Empty Season

```bash
# Isolate with single-match probe
python -m tools.scraper_check --season 2024 --limit 1

# Inspect HTML if parsing fails
curl -s "https://www.rugbyleagueproject.org/seasons/nrl-2024/round-1/summary.html" | head -100
```

### HTTP 5xx Errors

- Tenacity backoff is enabled (4 retries with jitter)
- Increase retries: `RETRIES=6 python -m nrlscraper.season 2024`

### Normalization Miss

1. Find the raw value in logs or DB (`*_raw` columns)
2. Add alias to `nrlscraper/normalize.py`
3. Re-run season (upserts are idempotent)

### DB Write Failures

1. Verify `DATABASE_URL` is set correctly
2. Run bootstrap: `psql "$DATABASE_URL" -f scripts/bootstrap_db.sql`
3. Check connection: `psql "$DATABASE_URL" -c "SELECT 1;"`
4. Retry scrape

### Schema Drift (RLP Markup Change)

- CI will fail on missing columns
- Run locally with `--limit 1` to inspect
- Compare HTML structure vs parser selectors
- Update `_parse_match_block()` regex patterns

## KPIs / SLOs

| Metric | Target |
|--------|--------|
| 2024 match count | 213 |
| 2024 regular season | 204 |
| Identity null rate | 0% |
| Normalization hit-rate | ≥95% |
| Full season scrape time | ≤10 min |
| Weekly job success rate | ≥99% |
| RLP request rate | ≤1 rps |
