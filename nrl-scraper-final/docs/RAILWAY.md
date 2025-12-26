# Railway Deployment Guide

## Quick Start

1. **Create Railway PostgreSQL**
   - Go to railway.app → New Project → Add PostgreSQL
   - Copy the `DATABASE_URL` from the PostgreSQL service

2. **Add Service from GitHub**
   - In Railway, add a new service from your GitHub repo
   - Set Start Command: `python main.py`

3. **Set Environment Variables**
   ```
   MODE=season
   SEASON=2024
   INCLUDE_FINALS=1
   WRITE_DB=1
   DATABASE_URL=<your postgresql url>
   ```

4. **Bootstrap Database**
   ```bash
   psql "$DATABASE_URL" -f scripts/bootstrap_db.sql
   ```

5. **Deploy**
   - Click Deploy in Railway
   - Service will scrape, write to DB, and exit

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MODE` | `season` | `season` or `historical` |
| `SEASON` | current year | Year to scrape (e.g., 2024) |
| `INCLUDE_FINALS` | `1` | Include finals matches |
| `WRITE_DB` | `0` | Write to PostgreSQL |
| `EXPORT` | `0` | Export to parquet file |
| `START_YEAR` | 2020 | Start year (historical mode) |
| `END_YEAR` | current year | End year (historical mode) |
| `DATABASE_URL` | - | PostgreSQL connection string |

## Example Configurations

### M1: 2024 Season Write
```
MODE=season
SEASON=2024
INCLUDE_FINALS=1
WRITE_DB=1
```

### Historical Backfill (2020-2024)
```
MODE=historical
START_YEAR=2020
END_YEAR=2024
WRITE_DB=1
```

### Export Only (No Database)
```
MODE=season
SEASON=2024
EXPORT=1
```

## Scheduled Runs

For weekly updates, use GitHub Actions (already configured in `.github/workflows/ci.yml`).

The workflow runs:
- Weekly on Tuesday @ 09:30 Australia/Sydney
- On-demand via "Run workflow" button

## Verification

After running, verify with:

```sql
SELECT COUNT(*) FROM matches WHERE season = 2024;
-- Expected: 213

SELECT COUNT(*) FROM matches WHERE season = 2024 AND round NOT LIKE '%Final%';
-- Expected: 204 (regular season)
```

## Troubleshooting

### "I don't know what to run"
Set Start Command to: `python main.py`

### Database connection failed
Check `DATABASE_URL` format:
```
postgresql+psycopg://user:password@host:port/database
```

### No matches found
- Check RLP site is accessible
- Verify season exists (2013+)
