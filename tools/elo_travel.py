from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np
import pandas as pd


@dataclass
class EloConfig:
    base: float = 1500.0
    k: float = 20.0
    home_adv: float = 45.0  # Elo pts
    finals_mult: float = 1.1  # increase K in finals
    margin_scale: float = 0.003  # scale margin into Elo adjustment


def _expected(ra: float, rb: float) -> float:
    return 1.0 / (1.0 + 10 ** (-(ra - rb) / 400.0))


def compute_elo(df: pd.DataFrame, cfg: EloConfig) -> pd.DataFrame:
    """Returns DF with added columns: elo_home, elo_away, elo_diff (pre-game)."""
    t_rating: dict[str, float] = {}
    out = []
    df = df.sort_values("date")
    for _, r in df.iterrows():
        h, a = str(r["home_team"]), str(r["away_team"])
        finals = bool(r.get("is_finals", 0))
        ra = t_rating.get(h, cfg.base)
        rb = t_rating.get(a, cfg.base)
        # pre-game snapshot
        out.append(
            {
                "match_id": r.get("match_id"),
                "date": r["date"],
                "home_team": h,
                "away_team": a,
                "elo_home": ra + cfg.home_adv,
                "elo_away": rb,
                "elo_diff": (ra + cfg.home_adv) - rb,
            }
        )
        # update after result (if scores present)
        hs, as_ = r.get("home_score"), r.get("away_score")
        if pd.notna(hs) and pd.notna(as_):
            s_home = 1.0 if hs > as_ else (0.5 if hs == as_ else 0.0)
            exp_home = _expected(ra + cfg.home_adv, rb)
            k_eff = cfg.k * (cfg.finals_mult if finals else 1.0)
            margin_term = 1.0 + cfg.margin_scale * abs(float(hs) - float(as_))
            delta = k_eff * margin_term * (s_home - exp_home)
            t_rating[h] = ra + delta
            t_rating[a] = rb - delta
    return pd.DataFrame(out)


def add_travel(df: pd.DataFrame, venues_latlon: pd.DataFrame | None) -> pd.DataFrame:
    """
    Adds travel_km and tz_diff if venues_latlon has columns:
    venue, lat, lon, tz_offset.
    """
    out = df.copy()
    if venues_latlon is None:  # nothing to add
        out["travel_km"] = np.nan
        out["tz_diff"] = np.nan
        return out
    v = venues_latlon.copy()
    v["venue_key"] = v["venue"].astype(str).str.strip().str.lower()
    out["venue_key"] = out["venue"].astype(str).str.strip().str.lower()
    out = out.merge(
        v[["venue_key", "lat", "lon", "tz_offset"]], on="venue_key", how="left"
    )
    # team home base lat/lon unknown -> fallback: 0 travel unless lat/lon for venue
    # is present; extend as needed with a home-base map.
    out["travel_km"] = 0.0
    out["tz_diff"] = out["tz_offset"].fillna(0.0)
    return out.drop(columns=["venue_key", "tz_offset", "lat", "lon"], errors="ignore")
