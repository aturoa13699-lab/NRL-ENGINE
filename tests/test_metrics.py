"""
Tests for evaluation metrics.
"""

import pandas as pd
import numpy as np

from nrl_engine.evaluation.metrics import (
    compute_brier,
    compute_auc,
    compute_clv,
    compute_calibration,
    compute_market_baseline,
    devig_odds
)


def test_devig_odds():
    """Test odds de-vigging."""
    # Fair odds (no vig)
    home_prob, away_prob = devig_odds(2.0, 2.0)
    assert abs(home_prob - 0.5) < 0.001
    assert abs(away_prob - 0.5) < 0.001
    
    # With vig (overround)
    home_prob, away_prob = devig_odds(1.9, 1.9)
    # Should sum to ~1.0 after de-vigging
    assert abs(home_prob + away_prob - 1.0) < 0.001
    
    # Invalid odds
    assert devig_odds(None, 2.0) == (None, None)
    assert devig_odds(1.0, 2.0) == (None, None)  # odds <= 1 invalid


def test_compute_brier():
    """Test Brier score computation."""
    # Perfect predictions
    df = pd.DataFrame({
        "pred_home_win_prob": [1.0, 0.0, 1.0, 0.0],
        "home_win": [1, 0, 1, 0]
    })
    result = compute_brier(df)
    assert result["brier"] == 0.0
    assert result["brier_skill"] == 1.0
    
    # Worst predictions
    df = pd.DataFrame({
        "pred_home_win_prob": [0.0, 1.0, 0.0, 1.0],
        "home_win": [1, 0, 1, 0]
    })
    result = compute_brier(df)
    assert result["brier"] == 1.0
    
    # Random predictions (0.5)
    df = pd.DataFrame({
        "pred_home_win_prob": [0.5, 0.5, 0.5, 0.5],
        "home_win": [1, 0, 1, 0]
    })
    result = compute_brier(df)
    assert result["brier"] == 0.25


def test_compute_auc():
    """Test AUC computation."""
    # Perfect separation
    df = pd.DataFrame({
        "pred_home_win_prob": [0.9, 0.8, 0.2, 0.1],
        "home_win": [1, 1, 0, 0]
    })
    result = compute_auc(df)
    assert result["auc"] == 1.0
    
    # Random
    df = pd.DataFrame({
        "pred_home_win_prob": [0.5, 0.5, 0.5, 0.5],
        "home_win": [1, 0, 1, 0]
    })
    result = compute_auc(df)
    assert 0.4 <= result["auc"] <= 0.6  # Should be ~0.5


def test_compute_clv():
    """Test CLV computation."""
    df = pd.DataFrame({
        "pred_home_win_prob": [0.6, 0.4, 0.7],
        "home_odds_close": [2.0, 2.5, 1.8],  # Fair probs: 0.5, 0.4, 0.556
        "away_odds_close": [2.0, 1.67, 2.25]
    })
    
    result = compute_clv(df)
    
    assert "mean_clv" in result
    assert result["n"] == 3
    # CLV should be positive on average if model probs > market probs
    # First: 0.6 - 0.5 = 0.1
    # Second: 0.4 - 0.4 = 0.0
    # Third: 0.7 - 0.556 ≈ 0.14
    assert result["mean_clv"] > 0


def test_compute_calibration():
    """Test calibration curve computation."""
    # Well-calibrated predictions
    np.random.seed(42)
    n = 1000
    
    # Generate predictions in bins
    probs = np.concatenate([
        np.full(100, 0.1),  # 10% bin
        np.full(100, 0.3),  # 30% bin
        np.full(100, 0.5),  # 50% bin
        np.full(100, 0.7),  # 70% bin
        np.full(100, 0.9),  # 90% bin
    ])
    
    # Generate outcomes matching probabilities
    outcomes = np.concatenate([
        np.random.binomial(1, 0.1, 100),
        np.random.binomial(1, 0.3, 100),
        np.random.binomial(1, 0.5, 100),
        np.random.binomial(1, 0.7, 100),
        np.random.binomial(1, 0.9, 100),
    ])
    
    df = pd.DataFrame({
        "pred_home_win_prob": probs,
        "home_win": outcomes
    })
    
    result = compute_calibration(df, n_bins=5)
    
    assert "predicted" in result
    assert "actual" in result
    assert len(result["predicted"]) == len(result["actual"])
    
    # Check approximate calibration
    for pred, act in zip(result["predicted"], result["actual"]):
        assert abs(pred - act) < 0.15, f"Calibration off: pred={pred}, actual={act}"


def test_compute_market_baseline():
    """Test market baseline computation."""
    # Create data where market is well-calibrated
    np.random.seed(42)
    n = 200
    
    # Generate realistic odds
    home_strength = np.random.uniform(0.3, 0.7, n)
    home_odds = 1.0 / home_strength
    away_odds = 1.0 / (1 - home_strength)
    
    # Outcomes follow probability
    outcomes = (np.random.random(n) < home_strength).astype(int)
    
    df = pd.DataFrame({
        "home_odds_close": home_odds,
        "away_odds_close": away_odds,
        "home_win": outcomes
    })
    
    result = compute_market_baseline(df)
    
    assert "error" not in result
    assert result["slope"] is not None
    assert result["slope"] > 0, "Healthy market should have positive slope"
    assert result["brier"] < 0.26, "Market should have reasonable Brier"


if __name__ == "__main__":
    print("Running metrics tests...")
    
    test_devig_odds()
    print("✓ test_devig_odds")
    
    test_compute_brier()
    print("✓ test_compute_brier")
    
    test_compute_auc()
    print("✓ test_compute_auc")
    
    test_compute_clv()
    print("✓ test_compute_clv")
    
    test_compute_calibration()
    print("✓ test_compute_calibration")
    
    test_compute_market_baseline()
    print("✓ test_compute_market_baseline")
    
    print("\nAll metrics tests passed!")
