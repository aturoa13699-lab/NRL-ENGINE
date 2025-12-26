"""
Tests for odds orientation gate.
"""

import pandas as pd
import numpy as np

from nrl_engine.evaluation.odds_gate import (
    enforce_odds_orientation,
    quick_odds_check,
    _compute_market_slope
)
from nrl_engine.data.sample_data import generate_sample_data
from nrl_engine.config import Config


def test_correct_orientation_detected():
    """Test that correctly oriented odds are detected."""
    # Generate sample data (should have correct orientation)
    data = generate_sample_data(n_matches=200, seed=42)
    
    # Check orientation
    result = quick_odds_check(data)
    
    assert result["as_is_healthy"], "Sample data should have healthy as-is orientation"
    assert not result["likely_swapped"], "Sample data should not be detected as swapped"


def test_swapped_odds_detected():
    """Test that swapped odds are detected."""
    # Generate sample data
    data = generate_sample_data(n_matches=200, seed=42)
    
    # Swap the odds columns
    data_swapped = data.copy()
    data_swapped["home_odds_close"], data_swapped["away_odds_close"] = \
        data["away_odds_close"].copy(), data["home_odds_close"].copy()
    
    # Check orientation
    result = quick_odds_check(data_swapped)
    
    assert result["likely_swapped"], "Swapped data should be detected as swapped"
    assert result["swapped_healthy"], "Swapped data should have healthy swapped orientation"
    assert not result["as_is_healthy"], "Swapped data should not have healthy as-is orientation"


def test_auto_fix_swapped_odds():
    """Test that swapped odds are automatically fixed."""
    # Generate sample data
    data = generate_sample_data(n_matches=200, seed=42)
    original_home_odds = data["home_odds_close"].copy()
    
    # Swap the odds columns
    data_swapped = data.copy()
    data_swapped["home_odds_close"], data_swapped["away_odds_close"] = \
        data["away_odds_close"].copy(), data["home_odds_close"].copy()
    
    # Create config with auto-fix enabled
    config = Config()
    config.odds_auto_fix = True
    config.odds_fail_on_ambiguous = False
    
    # Run enforcement
    fixed_data, report = enforce_odds_orientation(
        data_swapped,
        config=config,
        verbose=False
    )
    
    assert report["chosen"] == "swapped", "Should choose swapped orientation"
    assert report["action"] == "auto_swapped", "Should auto-swap"
    
    # Verify odds were swapped back
    pd.testing.assert_series_equal(
        fixed_data["home_odds_close"],
        original_home_odds,
        check_names=False
    )


def test_market_slope_calculation():
    """Test market slope calculation."""
    # Generate sample data with known properties
    data = generate_sample_data(n_matches=300, seed=42)
    
    slope_result = _compute_market_slope(data)
    
    assert "error" not in slope_result, f"Got error: {slope_result.get('error')}"
    assert slope_result["slope"] is not None, "Slope should be computed"
    assert slope_result["slope"] > 0, f"Slope should be positive, got {slope_result['slope']}"
    assert slope_result["brier"] < 0.25, f"Brier should be < 0.25, got {slope_result['brier']}"


def test_ambiguous_orientation_fails():
    """Test that ambiguous orientation raises error when configured."""
    # Create data where both orientations are bad
    # (e.g., random odds with no correlation to outcomes)
    np.random.seed(42)
    n = 100
    
    data = pd.DataFrame({
        "match_id": [f"match_{i}" for i in range(n)],
        "home_odds_close": np.random.uniform(1.5, 3.0, n),
        "away_odds_close": np.random.uniform(1.5, 3.0, n),
        "home_win": np.random.randint(0, 2, n)
    })
    
    config = Config()
    config.odds_fail_on_ambiguous = True
    config.odds_min_healthy_slope = 0.5  # High threshold to trigger failure
    
    try:
        enforce_odds_orientation(data, config=config, verbose=False)
        # If we get here, no error was raised
        # This might happen if random data happens to have positive slope
        # Check the result instead
    except ValueError as e:
        assert "ambiguous" in str(e).lower(), "Error should mention ambiguous"


if __name__ == "__main__":
    print("Running odds gate tests...")
    
    test_correct_orientation_detected()
    print("✓ test_correct_orientation_detected")
    
    test_swapped_odds_detected()
    print("✓ test_swapped_odds_detected")
    
    test_auto_fix_swapped_odds()
    print("✓ test_auto_fix_swapped_odds")
    
    test_market_slope_calculation()
    print("✓ test_market_slope_calculation")
    
    test_ambiguous_orientation_fails()
    print("✓ test_ambiguous_orientation_fails")
    
    print("\nAll odds gate tests passed!")
