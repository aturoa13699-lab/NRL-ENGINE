# Odds ingestion

This repo ships a small, idempotent odds pipeline that can be run locally, from GitHub Actions, or in Colab. It pulls closing prices from TheOddsAPI (when a key is present), scrapes Oddspedia/Oddschecker as a dynamic fallback, and merges everything into `data/sources/odds.csv`.

## Components

- `tools/fetch_api_odds.py`: Calls TheOddsAPI with retry/backoff. Honors `ODDS_API_KEY`, `ODDS_REGIONS` (default `au`), `ODDS_TIMEOUT`, `ODDS_RETRIES`, `ODDS_BACKOFF_MIN`, and `ODDS_BACKOFF_MAX`. Saves the raw payload under `manual_feeds/YYYYMMDD/api_odds.json` and merges normalized prices into `data/sources/odds.csv`.
- `tools/scrape_odds.py`: Headless Playwright scraper for Oddspedia (NRL) plus Oddschecker outrights. Writes HTML snapshots to `manual_feeds/YYYYMMDD/*_auto.html`.
- `tools/ingestors/oddspedia.py` + `tools/ingest_manual.py`: Parse saved Oddspedia HTML into normalized odds and append to `data/sources/odds.csv` (deduped on date/home/away).
- `tools/build_proxy_odds.py`: Fallback builder that derives odds from historical exports (e.g., `data/exports/train_super_enriched_v2.csv`) when no fresh odds file exists.
- `notebooks/30_odds_ingest_colab.ipynb`: Colab-friendly runner that clones the repo, attempts an API pull, parses any scraped HTML, and previews `data/sources/odds.csv`.
- `.github/workflows/odds-ingest.yml`: Nightly (Sun–Fri) workflow that runs the API fetch, Playwright scrape, manual ingest, and proxy builder before publishing `data/sources/odds.csv` to the `data` branch and as an artifact.

## Local usage

Run individual steps from the repo root:

```bash
# Pull from TheOddsAPI (requires ODDS_API_KEY)
python tools/fetch_api_odds.py

# Scrape dynamic sites and save HTML
python tools/scrape_odds.py

# Parse saved HTML and merge into data/sources/odds.csv
python tools/ingest_manual.py

# Optional: build proxy odds from a historical export
python tools/build_proxy_odds.py --from data/exports/train_super_enriched_v2.csv --write data/sources/odds.csv
```

Outputs land in `data/sources/odds.csv`, with raw snapshots under `manual_feeds/YYYYMMDD/`. The pipeline is safe to re-run; rows are deduplicated on `(date, home_team, away_team)` and sorted for stability.
