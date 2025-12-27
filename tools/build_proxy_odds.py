from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import pandas as pd


def _pick_column(columns: Iterable[str], candidates: list[str]) -> str | None:
    lower_map = {c.lower(): c for c in columns}
    for candidate in candidates:
        if candidate in lower_map:
            return lower_map[candidate]
    return None


def _load_proxy_frame(source_path: Path) -> pd.DataFrame:
    if not source_path.exists():
        print(f"[proxy] source not found: {source_path}")
        return pd.DataFrame()

    df = pd.read_csv(source_path)

    date_col = _pick_column(df.columns, ["date", "match_date", "game_date"])
    home_col = _pick_column(
        df.columns,
        ["home_odds_close", "home_odds", "home_price", "price_home"],
    )
    away_col = _pick_column(
        df.columns,
        ["away_odds_close", "away_odds", "away_price", "price_away"],
    )

    home_prob_col = _pick_column(df.columns, ["home_imp_prob", "home_prob"])
    away_prob_col = _pick_column(df.columns, ["away_imp_prob", "away_prob"])

    if not date_col:
        print("[proxy] no date column; cannot build odds")
        return pd.DataFrame()

    out = pd.DataFrame()
    out["date"] = pd.to_datetime(df[date_col], errors="coerce").dt.strftime("%Y-%m-%d")

    if home_col and away_col:
        out["home_odds_close"] = pd.to_numeric(df[home_col], errors="coerce")
        out["away_odds_close"] = pd.to_numeric(df[away_col], errors="coerce")
    elif home_prob_col and away_prob_col:
        out["home_odds_close"] = 1 / pd.to_numeric(df[home_prob_col], errors="coerce")
        out["away_odds_close"] = 1 / pd.to_numeric(df[away_prob_col], errors="coerce")
    else:
        print("[proxy] no odds/prob columns found")
        return pd.DataFrame()

    if "home_team" not in df.columns or "away_team" not in df.columns:
        print("[proxy] required team columns missing")
        return pd.DataFrame()

    out["home_team"] = df["home_team"]
    out["away_team"] = df["away_team"]

    out["source"] = "proxy"
    out = out.dropna(subset=["date", "home_team", "away_team", "home_odds_close", "away_odds_close"])
    out = out[out["home_odds_close"] > 1.01]
    out = out[out["away_odds_close"] > 1.01]
    out = out.drop_duplicates(subset=["date", "home_team", "away_team"], keep="last")
    return out[["date", "home_team", "away_team", "home_odds_close", "away_odds_close", "source"]]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build proxy odds from historical exports")
    parser.add_argument("--from", dest="source", required=True, help="CSV source for proxy odds")
    parser.add_argument(
        "--write",
        dest="target",
        default="data/sources/odds.csv",
        help="Path to write merged odds CSV",
    )
    args = parser.parse_args()

    source_path = Path(args.source)
    target_path = Path(args.target)
    proxy_df = _load_proxy_frame(source_path)
    if proxy_df.empty:
        print("[proxy] no rows generated; skipping write")
        return 0

    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        base = pd.read_csv(target_path)
        proxy_df = (
            pd.concat([base, proxy_df], ignore_index=True)
            .drop_duplicates(subset=["date", "home_team", "away_team"], keep="last")
        )

    proxy_df.sort_values(["date", "home_team", "away_team"], inplace=True)
    proxy_df.to_csv(target_path, index=False)
    print(f"[proxy] wrote {len(proxy_df)} rows to {target_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
