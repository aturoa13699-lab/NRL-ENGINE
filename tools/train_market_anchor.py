from __future__ import annotations

import json
import os
from typing import Dict

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix, hstack
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder

from tools.elo_travel import EloConfig, add_travel, compute_elo
from tools.multi_book import aggregate_multi_book
from tools.sim_checker import implied_probs, market_logit, run_sim_checker


def _metrics(y, p) -> dict[str, float]:
    return {
        "logloss": float(log_loss(y, p)),
        "brier": float(brier_score_loss(y, p)),
        "auc": float(roc_auc_score(y, p)),
    }


def main(
    path_data: str = "data/exports/train_super_enriched_v2.csv",
    path_odds: str = "data/sources/odds.csv",
    path_venues_latlon: str | None = None,
    calibrate: str = "isotonic",
    seed: int = 42,
):
    df = pd.read_csv(path_data)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["home_win"] = (df["home_score"] > df["away_score"]).astype(int)

    # merge odds (multi-book aware)
    if os.path.exists(path_odds):
        od = pd.read_csv(path_odds)
        if "date" in od:
            od["date"] = pd.to_datetime(od["date"], errors="coerce")
        od = aggregate_multi_book(od)
        key = [
            c
            for c in ["date", "home_team", "away_team"]
            if c in od.columns and c in df.columns
        ]
        df = df.merge(od, on=key, how="left")

    # implied probabilities + anchor
    p_mkt = implied_probs(df)
    if p_mkt.isna().all():
        raise SystemExit("No odds present; provide data/sources/odds.csv")
    df["home_imp_prob"] = p_mkt
    df["market_logit"] = market_logit(p_mkt)

    # Elo pre-game (uses actual results for historical updates)
    elo = compute_elo(df, EloConfig())
    df = df.merge(
        elo[["date", "home_team", "away_team", "elo_home", "elo_away", "elo_diff"]],
        on=["date", "home_team", "away_team"],
        how="left",
    )

    # travel features (optional)
    venues_latlon = None
    if path_venues_latlon and os.path.exists(path_venues_latlon):
        venues_latlon = pd.read_csv(path_venues_latlon)
    df = add_travel(df, venues_latlon)

    # build matrix
    cat = ["home_team", "away_team", "venue", "referee"]
    cat = [c for c in cat if c in df.columns]
    num = [
        c
        for c in df.columns
        if c.startswith(("roll_", "ref_", "elo_", "travel_", "home_", "away_"))
        and df[c].dtype != object
    ]
    y = df["home_win"]
    Xc = df[cat].astype(str) if cat else pd.DataFrame(index=df.index)
    Xn = df[num + ["market_logit", "home_imp_prob"]].fillna(0)

    if cat:
        ct = ColumnTransformer(
            [
                (
                    "cat",
                    OneHotEncoder(handle_unknown="ignore", sparse_output=True),
                    cat,
                )
            ]
        )
        X = hstack([ct.fit_transform(Xc), csr_matrix(Xn.values)])
    else:
        X = csr_matrix(Xn.values)

    # Train/test split
    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=seed
    )

    # Market-only baseline (market_logit is second-to-last column)
    mkt_col_idx = Xn.shape[1] - 2
    mkt_only = LogisticRegression(max_iter=1000).fit(
        Xtr[:, -Xn.shape[1] :][:, [mkt_col_idx]], ytr
    )
    p_mkt_te = mkt_only.predict_proba(Xte[:, -Xn.shape[1] :][:, [mkt_col_idx]])[:, 1]

    # Anchored model
    clf = LogisticRegression(max_iter=1000).fit(Xtr, ytr)
    p_raw = clf.predict_proba(Xte)[:, 1]

    # Calibration
    if calibrate in {"isotonic", "sigmoid"}:
        base = LogisticRegression(max_iter=1000).fit(Xtr, ytr)
        cal = CalibratedClassifierCV(
            base, method=("isotonic" if calibrate == "isotonic" else "sigmoid"), cv=5
        )
        cal.fit(Xtr, ytr)
        p_cal = cal.predict_proba(Xte)[:, 1]
    else:
        p_cal = p_raw

    # Metrics
    m_mkt = _metrics(yte, p_mkt_te)
    m_mod = _metrics(yte, p_cal)
    uplift = {
        k: m_mkt[k] - m_mod[k] if k == "logloss" else m_mod[k] - m_mkt[k] for k in m_mkt
    }
    print(json.dumps({"market": m_mkt, "model": m_mod, "uplift": uplift}, indent=2))

    # Simulation checker on a subset (CV log-loss)
    idx = np.argsort(df["date"].values)[-min(len(df), 5000) :]
    df_small = df.iloc[idx]
    res = run_sim_checker(df_small)
    print(
        "sim_checker:",
        json.dumps(
            {k: (len(v) if isinstance(v, dict) else v) for k, v in res.items()},
            indent=2,
        ),
    )


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/exports/train_super_enriched_v2.csv")
    ap.add_argument("--odds", default="data/sources/odds.csv")
    ap.add_argument("--venues", default="")
    ap.add_argument(
        "--calibrate", choices=["none", "sigmoid", "isotonic"], default="isotonic"
    )
    args = ap.parse_args()
    main(
        path_data=args.data,
        path_odds=args.odds,
        path_venues_latlon=(args.venues or None),
        calibrate=args.calibrate,
    )
