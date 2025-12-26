"""
Evaluation metrics for NRL predictions.

Includes:
- Model metrics: Brier score, AUC, accuracy, calibration
- Market metrics: CLV (Closing Line Value), market baseline
"""

from typing import Dict, Any, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.calibration import calibration_curve


def _clip_probs(p: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    """Clip probabilities to avoid log(0)."""
    return np.clip(np.asarray(p, dtype=float), eps, 1 - eps)


def devig_odds(home_odds: float, away_odds: float) -> Tuple[Optional[float], Optional[float]]:
    """
    Convert decimal odds to fair probabilities (remove vig).
    
    Args:
        home_odds: Decimal odds for home team
        away_odds: Decimal odds for away team
    
    Returns:
        (home_prob, away_prob) or (None, None) if invalid
    """
    if home_odds is None or away_odds is None:
        return None, None
    if pd.isna(home_odds) or pd.isna(away_odds):
        return None, None
    if home_odds <= 1.0 or away_odds <= 1.0:
        return None, None
    
    p_home = 1.0 / home_odds
    p_away = 1.0 / away_odds
    total = p_home + p_away
    
    if total <= 0:
        return None, None
    
    return p_home / total, p_away / total


def compute_brier(
    df: pd.DataFrame,
    prob_col: str = "pred_home_win_prob",
    outcome_col: str = "home_win"
) -> Dict[str, Any]:
    """
    Compute Brier score and skill score.
    
    Args:
        df: DataFrame with predictions and outcomes
        prob_col: Column with predicted probabilities
        outcome_col: Column with actual outcomes (0/1)
    
    Returns:
        Dict with brier, brier_skill, base_rate, n
    """
    d = df.dropna(subset=[prob_col, outcome_col]).copy()
    
    if d.empty:
        return {"error": "no data"}
    
    p = d[prob_col].values
    y = d[outcome_col].values.astype(float)
    
    # Brier score
    brier = float(np.mean((p - y) ** 2))
    
    # Brier skill score (vs climatology/base rate)
    base_rate = y.mean()
    brier_clim = base_rate * (1 - base_rate)
    skill = 1 - (brier / brier_clim) if brier_clim > 0 else 0.0
    
    return {
        "n": int(len(d)),
        "brier": brier,
        "brier_skill": float(skill),
        "base_rate": float(base_rate)
    }


def compute_auc(
    df: pd.DataFrame,
    prob_col: str = "pred_home_win_prob",
    outcome_col: str = "home_win"
) -> Dict[str, Any]:
    """
    Compute AUC-ROC.
    
    Args:
        df: DataFrame with predictions and outcomes
        prob_col: Column with predicted probabilities
        outcome_col: Column with actual outcomes (0/1)
    
    Returns:
        Dict with auc, n
    """
    d = df.dropna(subset=[prob_col, outcome_col]).copy()
    
    if d.empty:
        return {"error": "no data"}
    
    if d[outcome_col].nunique() < 2:
        return {"error": "single class in outcomes"}
    
    auc = roc_auc_score(d[outcome_col].values, d[prob_col].values)
    
    return {
        "n": int(len(d)),
        "auc": float(auc)
    }


def compute_accuracy(
    df: pd.DataFrame,
    prob_col: str = "pred_home_win_prob",
    outcome_col: str = "home_win",
    threshold: float = 0.5
) -> Dict[str, Any]:
    """
    Compute classification accuracy.
    
    Args:
        df: DataFrame with predictions and outcomes
        prob_col: Column with predicted probabilities
        outcome_col: Column with actual outcomes (0/1)
        threshold: Classification threshold
    
    Returns:
        Dict with accuracy, n
    """
    d = df.dropna(subset=[prob_col, outcome_col]).copy()
    
    if d.empty:
        return {"error": "no data"}
    
    pred = (d[prob_col] > threshold).astype(int)
    actual = d[outcome_col].astype(int)
    accuracy = float((pred == actual).mean())
    
    return {
        "n": int(len(d)),
        "accuracy": accuracy
    }


def compute_clv(
    df: pd.DataFrame,
    prob_col: str = "pred_home_win_prob",
    home_odds_col: str = "home_odds_close",
    away_odds_col: str = "away_odds_close"
) -> Dict[str, Any]:
    """
    Compute Closing Line Value.
    
    CLV = model probability - fair market probability
    Positive CLV = model sees value that market doesn't
    
    Args:
        df: DataFrame with predictions and odds
        prob_col: Column with model predictions
        home_odds_col: Column with home team odds
        away_odds_col: Column with away team odds
    
    Returns:
        Dict with mean_clv, median_clv, std_clv, positive_rate, n
    """
    if home_odds_col not in df.columns or away_odds_col not in df.columns:
        return {"error": "odds columns not found"}
    
    clv_values = []
    
    for _, row in df.dropna(subset=[prob_col, home_odds_col, away_odds_col]).iterrows():
        fair_home, _ = devig_odds(row[home_odds_col], row[away_odds_col])
        
        if fair_home is None:
            continue
        
        clv = float(row[prob_col]) - float(fair_home)
        clv_values.append(clv)
    
    if not clv_values:
        return {"error": "no valid odds rows"}
    
    clv_arr = np.array(clv_values)
    
    return {
        "n": len(clv_arr),
        "mean_clv": float(clv_arr.mean()),
        "median_clv": float(np.median(clv_arr)),
        "std_clv": float(clv_arr.std()),
        "positive_rate": float((clv_arr > 0).mean())
    }


def compute_calibration(
    df: pd.DataFrame,
    prob_col: str = "pred_home_win_prob",
    outcome_col: str = "home_win",
    n_bins: int = 10
) -> Dict[str, Any]:
    """
    Compute calibration curve.
    
    Args:
        df: DataFrame with predictions and outcomes
        prob_col: Column with predicted probabilities
        outcome_col: Column with actual outcomes
        n_bins: Number of calibration bins
    
    Returns:
        Dict with predicted (bin centers), actual (observed frequency)
    """
    d = df.dropna(subset=[prob_col, outcome_col]).copy()
    
    if d.empty:
        return {"error": "no data"}
    
    try:
        actual, predicted = calibration_curve(
            d[outcome_col].values,
            d[prob_col].values,
            n_bins=n_bins
        )
        
        return {
            "predicted": predicted.tolist(),
            "actual": actual.tolist(),
            "n_bins": len(predicted)
        }
    except Exception as e:
        return {"error": str(e)}


def compute_market_baseline(
    df: pd.DataFrame,
    home_odds_col: str = "home_odds_close",
    away_odds_col: str = "away_odds_close",
    outcome_col: str = "home_win"
) -> Dict[str, Any]:
    """
    Compute market baseline metrics.
    
    Uses devigged closing odds as predictions and evaluates
    against actual outcomes.
    
    Args:
        df: DataFrame with odds and outcomes
        home_odds_col: Column with home team odds
        away_odds_col: Column with away team odds
        outcome_col: Column with actual outcomes
    
    Returns:
        Dict with n, brier, slope, correlation
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
    
    # De-vig to get market probabilities
    p_home_raw = 1.0 / d[home_odds_col].values
    p_away_raw = 1.0 / d[away_odds_col].values
    p_market = _clip_probs(p_home_raw / (p_home_raw + p_away_raw))
    y = d[outcome_col].values.astype(int)
    
    # Brier
    brier = float(np.mean((p_market - y) ** 2))
    
    # Correlation
    corr = float(np.corrcoef(p_market, y)[0, 1]) if len(np.unique(y)) > 1 else 0.0
    
    # Calibration slope (logistic regression of log-odds)
    slope = None
    intercept = None
    try:
        from sklearn.linear_model import LogisticRegression
        log_odds = np.log(p_market / (1 - p_market))
        lr = LogisticRegression(solver="lbfgs", max_iter=1000)
        lr.fit(log_odds.reshape(-1, 1), y)
        slope = float(lr.coef_[0][0])
        intercept = float(lr.intercept_[0])
    except Exception:
        pass
    
    return {
        "n": int(len(d)),
        "brier": brier,
        "slope": slope,
        "intercept": intercept,
        "correlation": corr,
        "home_win_rate": float(y.mean())
    }


def compute_all_metrics(
    df: pd.DataFrame,
    prob_col: str = "pred_home_win_prob",
    outcome_col: str = "home_win",
    home_odds_col: str = "home_odds_close",
    away_odds_col: str = "away_odds_close"
) -> Dict[str, Any]:
    """
    Compute all metrics in one call.
    
    Args:
        df: DataFrame with predictions, outcomes, and optionally odds
        prob_col: Column with predicted probabilities
        outcome_col: Column with actual outcomes
        home_odds_col: Column with home team odds
        away_odds_col: Column with away team odds
    
    Returns:
        Dict with model_metrics and market_metrics
    """
    has_odds = home_odds_col in df.columns and away_odds_col in df.columns
    
    metrics = {
        "model_metrics": {
            "brier": compute_brier(df, prob_col, outcome_col),
            "auc": compute_auc(df, prob_col, outcome_col),
            "accuracy": compute_accuracy(df, prob_col, outcome_col),
            "calibration": compute_calibration(df, prob_col, outcome_col),
        },
        "market_metrics": {}
    }
    
    if has_odds:
        metrics["market_metrics"] = {
            "clv": compute_clv(df, prob_col, home_odds_col, away_odds_col),
            "market_baseline": compute_market_baseline(df, home_odds_col, away_odds_col, outcome_col)
        }
    
    return metrics
