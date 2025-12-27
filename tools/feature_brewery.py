from __future__ import annotations

from typing import List

import pandas as pd


def _is_num(s, c):
    return c in s and s[c].dtype != object


def brew_candidates(df: pd.DataFrame) -> List[str]:
    """
    Generate candidate feature columns from existing data.
    Returns list of newly created numeric feature names.
    """
    cand = []

    def add(n, series):
        if n not in df.columns:
            df[n] = series

    pairs = [
        ("home_plyr_strength", "away_plyr_strength"),
        ("roll_win_5_home", "roll_win_5_away"),
        ("roll_margin_5_home", "roll_margin_5_away"),
        ("roll_pf_5_home", "roll_pa_5_away"),
        ("roll_pf_reg_5_home", "roll_pa_reg_5_away"),
        ("roll_pf_fin_5_home", "roll_pa_fin_5_away"),
    ]
    for a, b in pairs:
        if a in df and b in df and _is_num(df, a) and _is_num(df, b):
            n = f"{a}_minus_{b}"
            add(n, df[a].fillna(0) - df[b].fillna(0))
            cand.append(n)

    if "is_finals" in df:
        for s in [
            "home_plyr_strength_minus_away_plyr_strength",
            "roll_margin_5_home_minus_roll_margin_5_away",
        ]:
            if s in df and _is_num(df, s):
                n = f"{s}_x_is_finals"
                add(n, df[s].fillna(0) * df["is_finals"].fillna(0))
                cand.append(n)

    if "home_imp_prob" in df and _is_num(df, "home_imp_prob"):
        for s in [
            "home_plyr_strength_minus_away_plyr_strength",
            "roll_win_5_home_minus_roll_win_5_away",
        ]:
            if s in df and _is_num(df, s):
                n = f"{s}_minus_market"
                add(n, df[s].fillna(0) - (df["home_imp_prob"].fillna(0) - 0.5))
                cand.append(n)

    # Keep only numeric & unique
    cand = [c for c in dict.fromkeys(cand) if c in df and _is_num(df, c)]
    return cand
