from __future__ import annotations

import re

import pandas as pd


def to_decimal(raw_value):
    s = str(raw_value).strip()
    if not s:
        return None

    frac = re.match(r"^\s*(\d+)\s*/\s*(\d+)\s*$", s)
    if frac:
        num, den = int(frac.group(1)), int(frac.group(2))
        return round(1.0 + num / den, 6)

    if re.match(r"^[+-]?\d+$", s):
        n = int(s)
        return round(1 + n / 100.0 if n > 0 else 1 + 100 / abs(n), 6)

    match = re.search(r"(\d+(?:\.\d+)?)", s)
    return float(match.group(1)) if match else None


def finalize(df: pd.DataFrame, source: str) -> pd.DataFrame:
    cols = ["date", "home_team", "away_team", "home_odds_close", "away_odds_close"]
    for col in cols:
        if col not in df.columns:
            df[col] = None

    frame = df[cols].copy()
    frame["source"] = source
    frame.dropna(
        subset=["home_team", "away_team", "home_odds_close", "away_odds_close"],
        inplace=True,
    )
    frame = frame[frame["home_odds_close"].astype(float) > 1.01]
    frame = frame[frame["away_odds_close"].astype(float) > 1.01]
    frame.drop_duplicates(
        subset=["date", "home_team", "away_team"], keep="last", inplace=True
    )
    return frame
