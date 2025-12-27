from __future__ import annotations

import json
import os
import random
import statistics as stats
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping

import pandas as pd
import requests

API_KEY = os.getenv("ODDS_API_KEY")
SPORT = "rugbyleague_nrl"
REGIONS = os.getenv("ODDS_REGIONS", "au")
MARKETS = "h2h"
TIMEOUT = float(os.getenv("ODDS_TIMEOUT", "30"))
RETRIES = int(os.getenv("ODDS_RETRIES", "5"))
BMIN = float(os.getenv("ODDS_BACKOFF_MIN", "0.8"))
BMAX = float(os.getenv("ODDS_BACKOFF_MAX", "6.0"))


def _sleep(backoff_step: int, retry_after: str | None = None) -> None:
    if retry_after:
        try:
            delay = float(retry_after)
        except Exception:
            delay = None
        else:
            time.sleep(min(max(delay, 1.0), 60.0))
            return

    upper = min(BMAX, BMIN * (2**backoff_step))
    time.sleep(random.uniform(BMIN, upper))


def _req(url: str, params: Mapping[str, str]) -> requests.Response:
    for attempt in range(RETRIES):
        try:
            response = requests.get(url, params=params, timeout=TIMEOUT)
        except Exception as exc:
            print("API error", exc, f"retry {attempt + 1}/{RETRIES}")
            _sleep(attempt)
            continue

        if response.status_code == 200:
            return response
        if response.status_code in (429, 500, 502, 503):
            _sleep(
                attempt,
                response.headers.get("Retry-After")
                or response.headers.get("retry-after"),
            )
            continue

        print("Hard API fail:", response.status_code, response.text[:200])
        return response

    raise SystemExit("Exhausted retries for TheOddsAPI")


def normalize(events: Iterable[Mapping[str, object]]) -> pd.DataFrame:
    rows = []
    for ev in events:
        home, away = ev.get("home_team"), ev.get("away_team")
        dt = (ev.get("commence_time") or "")[:10]
        home_prices: list[float] = []
        away_prices: list[float] = []
        books: set[str] = set()

        for bookmaker in ev.get("bookmakers", []) or []:
            for market in bookmaker.get("markets", []) or []:
                if market.get("key") != "h2h":
                    continue

                prices = {o.get("name"): o.get("price") for o in market.get("outcomes", []) or []}
                home_price, away_price = prices.get(home), prices.get(away)
                if home_price is None or away_price is None:
                    continue
                try:
                    home_prices.append(float(home_price))
                    away_prices.append(float(away_price))
                except Exception:
                    continue
                books.add(bookmaker.get("key", "book"))

        if home and away and home_prices and away_prices:
            rows.append(
                {
                    "date": dt,
                    "home_team": home,
                    "away_team": away,
                    "home_odds_close": round(stats.median(home_prices), 4),
                    "away_odds_close": round(stats.median(away_prices), 4),
                    "source": "theoddsapi",
                    "books": ",".join(sorted(books)),
                }
            )

    return pd.DataFrame(rows)


def main() -> int:
    if not API_KEY:
        print("No ODDS_API_KEY; skipping API fetch.")
        return 0

    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds"
    response = _req(
        url,
        {"apiKey": API_KEY, "regions": REGIONS, "markets": MARKETS, "oddsFormat": "decimal"},
    )
    if response.status_code != 200:
        print("API FAIL:", response.status_code, response.text[:200])
        return 0

    today = datetime.utcnow().strftime("%Y%m%d")
    snapshot = Path(f"manual_feeds/{today}")
    snapshot.mkdir(parents=True, exist_ok=True)
    (snapshot / "api_odds.json").write_text(json.dumps(response.json(), indent=2), encoding="utf-8")

    df = normalize(response.json())
    if df.empty:
        print("API returned no H2H rows.")
        return 0

    destination = Path("data/sources")
    destination.mkdir(parents=True, exist_ok=True)
    out = destination / "odds.csv"
    if out.exists():
        base = pd.read_csv(out)
        df = (
            pd.concat([base, df], ignore_index=True)
            .drop_duplicates(subset=["date", "home_team", "away_team"], keep="last")
        )
    df.sort_values(["date", "home_team", "away_team"], inplace=True)
    df.to_csv(out, index=False)
    print("Wrote", out, "rows", len(df))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
