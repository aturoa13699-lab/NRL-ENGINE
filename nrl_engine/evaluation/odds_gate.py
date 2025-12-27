"""
Odds Orientation Gate.

Detects and corrects swapped home/away odds columns.
Fails loudly if orientation is ambiguous (likely join corruption).
"""

from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from nrl_engine.config import Config, DEFAULT_CONFIG


def _clip_probs(p: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    """Clip probabilities to avoid log(0)."""
    return np.clip(np.asarray(p, dtype=float), eps, 1 - eps)


def _compute_market_slope(
    df: pd.DataFrame,
    home_odds_col: str = "home_odds_close",
    away_odds_col: str = "away_odds_close",
    outcome_col: str = "home_win",
) -> dict[str, Any]:
    """
    Compute market baseline slope.

    A healthy market should have positive slope (higher implied prob = more wins).
    Negative slope strongly indicates swapped odds columns.
    """
    required = {home_odds_col, away_odds_col, outcome_col}
    if not required.issubset(df.columns):
        return {"error": f"missing columns: {required - set(df.columns)}"}

    # Filter valid rows
    mask = df[[home_odds_col, away_odds_col]].notna().all(axis=1)
    mask &= (df[home_odds_col] > 1.0) & (df[away_odds_col] > 1.0)
    d = df[mask].copy()

    if len(d) < 20:
        return {"error": f"too few valid rows: {len(d)}"}

    # De-vig
    p_home_raw = 1.0 / d[home_odds_col].values
    p_away_raw = 1.0 / d[away_odds_col].values
    p_market = _clip_probs(p_home_raw / (p_home_raw + p_away_raw))
    y = d[outcome_col].values.astype(int)

    # Brier
    brier = float(np.mean((p_market - y) ** 2))

    # Correlation
    corr = float(np.corrcoef(p_market, y)[0, 1]) if len(np.unique(y)) > 1 else 0.0

    # Slope
    slope = None
    intercept = None
    try:
        log_odds = np.log(p_market / (1 - p_market))
        lr = LogisticRegression(solver="lbfgs", max_iter=1000)
        lr.fit(log_odds.reshape(-1, 1), y)
        slope = float(lr.coef_[0][0])
        intercept = float(lr.intercept_[0])
    except Exception as e:
        return {"n": len(d), "brier": brier, "slope": None, "error": str(e)}

    return {
        "n": int(len(d)),
        "brier": brier,
        "slope": slope,
        "intercept": intercept,
        "correlation": corr,
    }


def enforce_odds_orientation(
    df: pd.DataFrame,
    home_odds_col: str = "home_odds_close",
    away_odds_col: str = "away_odds_close",
    outcome_col: str = "home_win",
    config: Config | None = None,
    verbose: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Enforce correct odds orientation.

    Detects swapped odds columns by checking market slope.
    A healthy market should have positive slope (favorites win more).

    Args:
        df: DataFrame with odds columns
        home_odds_col: Name of home odds column
        away_odds_col: Name of away odds column
        outcome_col: Name of outcome column (1 = home win)
        config: Configuration (uses defaults if not provided)
        verbose: Print diagnostic output

    Returns:
        (fixed_df, report_dict)

    Raises:
        ValueError: If orientation is ambiguous and config.odds_fail_on_ambiguous is True
    """
    config = config or DEFAULT_CONFIG

    if verbose:
        print("=" * 60)
        print("ODDS ORIENTATION ENFORCEMENT")
        print("=" * 60)

    # Check required columns
    required = {home_odds_col, away_odds_col, outcome_col}
    if not required.issubset(df.columns):
        report = {
            "error": f"missing columns: {required - set(df.columns)}",
            "chosen": "error",
            "action": "none",
        }
        if verbose:
            print(f"  ERROR: {report['error']}")
        return df, report

    # Compute slope as-is
    m_as_is = _compute_market_slope(df, home_odds_col, away_odds_col, outcome_col)

    # Compute slope with swapped columns
    df_swapped = df.copy()
    df_swapped[[home_odds_col, away_odds_col]] = df_swapped[
        [away_odds_col, home_odds_col]
    ].values
    m_swapped = _compute_market_slope(
        df_swapped, home_odds_col, away_odds_col, outcome_col
    )

    if verbose:
        print(f"\n{'Config':<10} {'Brier':<10} {'Slope':<12} {'Corr':<10}")
        print("-" * 50)

        for name, m in [("AS_IS", m_as_is), ("SWAPPED", m_swapped)]:
            if "error" in m:
                print(f"{name:<10} ERROR: {m['error']}")
            else:
                slope_str = f"{m['slope']:.4f}" if m.get("slope") is not None else "N/A"
                print(
                    f"{name:<10} {m['brier']:.4f}     {slope_str:<12} {m['correlation']:.4f}"
                )

    # Determine health
    def is_healthy(m: dict) -> bool:
        return (
            "error" not in m
            and m.get("slope") is not None
            and m["slope"] > config.odds_min_healthy_slope
        )

    as_is_healthy = is_healthy(m_as_is)
    swapped_healthy = is_healthy(m_swapped)

    report = {
        "as_is": m_as_is,
        "swapped": m_swapped,
        "as_is_healthy": as_is_healthy,
        "swapped_healthy": swapped_healthy,
    }

    if verbose:
        print("\n[DIAGNOSIS]")

    # Decision logic
    if as_is_healthy and not swapped_healthy:
        if verbose:
            print(f"  ✓ Odds correctly oriented (slope={m_as_is['slope']:.4f})")
        report["chosen"] = "as_is"
        report["action"] = "none"
        return df, report

    if swapped_healthy and not as_is_healthy:
        if verbose:
            print(
                f"  🚨 Odds SWAPPED upstream (as_is slope={m_as_is.get('slope')}, swapped slope={m_swapped['slope']:.4f})"
            )
        report["chosen"] = "swapped"

        if config.odds_auto_fix:
            if verbose:
                print(f"  🔧 AUTO-FIX: Swapping {home_odds_col} <-> {away_odds_col}")
            report["action"] = "auto_swapped"
            return df_swapped, report
        else:
            if verbose:
                print("  ⚠️ Auto-fix disabled. Manual fix required.")
            report["action"] = "manual_fix_needed"
            return df, report

    if as_is_healthy and swapped_healthy:
        # Both healthy - pick the one with higher slope
        s1 = m_as_is.get("slope", -999)
        s2 = m_swapped.get("slope", -999)

        if s2 > s1:
            if verbose:
                print("  ⚠️ Both slopes positive; SWAPPED is better -> using SWAPPED")
            report["chosen"] = "swapped"
            report["action"] = (
                "auto_swapped" if config.odds_auto_fix else "manual_fix_needed"
            )
            return (df_swapped if config.odds_auto_fix else df), report
        else:
            if verbose:
                print("  ⚠️ Both slopes positive; AS_IS is better -> using AS_IS")
            report["chosen"] = "as_is"
            report["action"] = "none"
            return df, report

    # Neither healthy - ambiguous
    if verbose:
        print("  🚨 Neither orientation yields positive market slope!")
        print(
            "  → Likely causes: join corruption, label mismatch, or odds attached to wrong matches"
        )

    report["chosen"] = "unknown"
    report["action"] = "investigation_needed"

    if config.odds_fail_on_ambiguous:
        raise ValueError(
            f"Odds orientation ambiguous: neither AS_IS nor SWAPPED produces healthy market baseline.\n"
            f"AS_IS: {m_as_is}\n"
            f"SWAPPED: {m_swapped}\n"
            f"Check join integrity and label correctness."
        )

    return df, report


def quick_odds_check(
    df: pd.DataFrame,
    home_odds_col: str = "home_odds_close",
    away_odds_col: str = "away_odds_close",
    outcome_col: str = "home_win",
) -> dict[str, Any]:
    """
    Quick odds sanity check without fixing.

    Returns dict with orientation diagnosis.
    """
    m_as_is = _compute_market_slope(df, home_odds_col, away_odds_col, outcome_col)

    df_swapped = df.copy()
    df_swapped[[home_odds_col, away_odds_col]] = df_swapped[
        [away_odds_col, home_odds_col]
    ].values
    m_swapped = _compute_market_slope(
        df_swapped, home_odds_col, away_odds_col, outcome_col
    )

    def is_healthy(m):
        return "error" not in m and m.get("slope", -999) > 0.3

    return {
        "as_is": m_as_is,
        "swapped": m_swapped,
        "as_is_healthy": is_healthy(m_as_is),
        "swapped_healthy": is_healthy(m_swapped),
        "likely_swapped": is_healthy(m_swapped) and not is_healthy(m_as_is),
    }
