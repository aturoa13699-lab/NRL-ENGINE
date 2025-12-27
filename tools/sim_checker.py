from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
from sklearn.model_selection import TimeSeriesSplit

from tools.feature_brewery import brew_candidates


def implied_probs(df: pd.DataFrame) -> pd.Series:
    if {"home_odds_close", "away_odds_close"} <= set(df.columns):
        inv = (
            1 / df[["home_odds_close", "away_odds_close"]].clip(lower=1.01).astype(float)
        )
        s = inv.sum(axis=1)
        return (inv["home_odds_close"] / s).rename("home_imp_prob")
    return pd.Series(np.nan, index=df.index, name="home_imp_prob")


def market_logit(p: pd.Series) -> pd.Series:
    p = p.clip(1e-5, 1 - 1e-5)
    return np.log(p / (1 - p))


def _splits(n: int = 5):
    return TimeSeriesSplit(n_splits=n)


def _logloss_cv(X, y, splits) -> float:
    losses = []
    for tr, te in splits.split(X):
        clf = LogisticRegression(max_iter=1000)
        clf.fit(X.iloc[tr], y.iloc[tr])
        p = clf.predict_proba(X.iloc[te])[:, 1]
        losses.append(log_loss(y.iloc[te], p, labels=[0, 1]))
    return float(np.mean(losses))


def forward_select(
    df: pd.DataFrame,
    y: pd.Series,
    base: List[str],
    cand: List[str],
    min_delta: float = 5e-4,
    max_add: int = 20,
) -> Tuple[List[str], Dict[str, float]]:
    splits = _splits()
    chosen = list(base)
    hist = {}
    best_score = _logloss_cv(df[chosen], y, splits)
    while len(chosen) - len(base) < max_add:
        best = (None, 0.0, best_score)
        for f in cand:
            if f in chosen:
                continue
            score = _logloss_cv(df[chosen + [f]], y, splits)
            delta = best_score - score
            if delta > best[1]:
                best = (f, delta, score)
        if best[0] and best[1] > min_delta:
            chosen.append(best[0])
            hist[best[0]] = best[1]
            best_score = best[2]
        else:
            break
    return chosen, hist


def backward_drop(
    df: pd.DataFrame,
    y: pd.Series,
    feats: List[str],
    min_delta: float = 1e-4,
) -> Tuple[List[str], Dict[str, float]]:
    splits = _splits()
    keep = list(feats)
    hist = {}
    base_score = _logloss_cv(df[keep], y, splits)
    while len(keep) > 1:
        best = (None, 0.0, base_score)
        for f in list(keep)[1:]:
            cols = [c for c in keep if c != f]
            score = _logloss_cv(df[cols], y, splits)
            delta = base_score - score
            if delta > best[1]:
                best = (f, delta, score)
        if best[0] and best[1] > min_delta:
            keep.remove(best[0])
            hist[best[0]] = best[1]
            base_score = best[2]
        else:
            break
    return keep, hist


def run_sim_checker(df: pd.DataFrame) -> Dict:
    out = {"errors": []}
    if "home_win" not in df:
        out["errors"].append("missing home_win")
        return out
    p_mkt = implied_probs(df)
    if p_mkt.isna().all():
        out["errors"].append("missing odds")
        return out
    df = df.copy()
    df["home_imp_prob"] = p_mkt
    df["market_logit"] = market_logit(p_mkt)
    base = ["market_logit"]
    cand = brew_candidates(df)
    X = df[base + cand].fillna(0)
    y = df["home_win"].astype(int)
    chosen, added = forward_select(X, y, base, cand)
    kept, dropped = backward_drop(X, y, chosen)
    return {"selected": kept, "added_gains": added, "dropped_gains": dropped}
