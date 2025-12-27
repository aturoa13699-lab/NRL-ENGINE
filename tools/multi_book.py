from __future__ import annotations

import numpy as np
import pandas as pd


def aggregate_multi_book(odds: pd.DataFrame) -> pd.DataFrame:
    """
    Accepts a DF with columns like:
      date, home_team, away_team, [home_odds_close[_{bk}]], [away_odds_close[_{bk}]]
    Picks best price across books; normalizes to implied probabilities with
    proportional overround reduction.
    """
    df = odds.copy()
    key = [c for c in ["date", "home_team", "away_team"] if c in df.columns]
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    # find all home/away price columns
    hcols = [c for c in df.columns if c.startswith("home_odds_close")]
    acols = [c for c in df.columns if c.startswith("away_odds_close")]
    if not hcols or not acols:
        return df.rename(
            columns={
                hcols[0] if hcols else "home_odds_close": "home_odds_close",
                acols[0] if acols else "away_odds_close": "away_odds_close",
            }
        )
    df["home_odds_close"] = df[hcols].max(axis=1)
    df["away_odds_close"] = df[acols].max(axis=1)
    out = df[key + ["home_odds_close", "away_odds_close"]].copy()
    inv = 1 / out[["home_odds_close", "away_odds_close"]].clip(lower=1.01)
    s = inv.sum(axis=1)
    # proportional reduction
    out["home_imp_prob"] = (inv["home_odds_close"] / s).astype(float)
    out["away_imp_prob"] = (inv["away_odds_close"] / s).astype(float)
    return out
