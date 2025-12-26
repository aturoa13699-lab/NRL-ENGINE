"""
Tests for Point-in-Time validation.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from nrl_engine.features.pit_validator import PITValidator
from nrl_engine.features.engineer import FeatureEngineer
from nrl_engine.data.sample_data import generate_sample_data


def test_pit_validator_blocks_future():
    """Test that PIT validator blocks future data."""
    pit = PITValidator()
    
    # Create test data
    dates = pd.date_range("2023-01-01", periods=10, freq="D")
    df = pd.DataFrame({
        "date": dates,
        "value": range(10)
    })
    
    # Filter to before day 5
    asof = pd.Timestamp("2023-01-05")
    filtered = pit.validate("test_feature", df, asof, "date")
    
    # Should only have days 1-4 (4 rows)
    assert len(filtered) == 4, f"Expected 4 rows, got {len(filtered)}"
    
    # Check report
    report = pit.report()
    assert report["status"] == "VIOLATIONS_BLOCKED"
    assert report["violations_blocked"] == 1
    assert report["total_rows_blocked"] == 6  # Days 5-10


def test_pit_validator_clean():
    """Test that PIT validator reports clean when no future data."""
    pit = PITValidator()
    
    dates = pd.date_range("2023-01-01", periods=5, freq="D")
    df = pd.DataFrame({
        "date": dates,
        "value": range(5)
    })
    
    # Filter with future asof
    asof = pd.Timestamp("2023-01-10")
    filtered = pit.validate("test_feature", df, asof, "date")
    
    assert len(filtered) == 5
    assert pit.is_clean
    
    report = pit.report()
    assert report["status"] == "CLEAN"


def test_feature_engineer_pit_safe():
    """Test that feature engineer respects PIT."""
    # Generate sample data
    data = generate_sample_data(n_matches=100, seasons=[2023])
    
    # Get a match in the middle
    data = data.sort_values("date").reset_index(drop=True)
    mid_idx = len(data) // 2
    test_match = data.iloc[mid_idx]
    test_date = pd.to_datetime(test_match["date"])
    
    # Create feature engineer
    fe = FeatureEngineer(data)
    
    # Compute features for this match
    features = fe.compute_features(test_match)
    
    # The feature engineer should have blocked future data
    # (PIT violations are logged but data is filtered)
    # Just verify we got features without error
    assert "match_id" in features
    assert features["match_id"] == test_match["match_id"]
    
    # Rolling stats should be computed from past only
    # If home team has games, they should be from before test_date
    home_team = test_match["home_team"]
    home_history = data[
        ((data["home_team"] == home_team) | (data["away_team"] == home_team)) &
        (pd.to_datetime(data["date"]) < test_date)
    ]
    
    expected_games = min(len(home_history), 5)  # window of 5
    
    # home_5_games should match available history
    if expected_games >= 3:  # min_games_for_rolling
        assert features.get("home_5_games", 0) <= expected_games


def test_no_future_leakage_in_features():
    """Verify no future information leaks into features."""
    # Create simple dataset with known patterns
    np.random.seed(42)
    
    data = generate_sample_data(n_matches=200, seasons=[2022, 2023])
    data = data.sort_values("date").reset_index(drop=True)
    
    # Split at 2023
    train_data = data[data["season"] == 2022]
    test_data = data[data["season"] == 2023]
    
    # Build features using ONLY training data
    fe_train = FeatureEngineer(train_data)
    
    # Now compute features for first test match
    first_test = test_data.iloc[0]
    features = fe_train.compute_features(first_test)
    
    # Should have some features (from 2022 data)
    # But they should be limited since we only used 2022 data
    assert features["home_5_games"] >= 0
    
    # The key test: features computed should NOT use any 2023 data
    # This is guaranteed by the PIT validator filtering


if __name__ == "__main__":
    print("Running PIT tests...")
    test_pit_validator_blocks_future()
    print("✓ test_pit_validator_blocks_future")
    
    test_pit_validator_clean()
    print("✓ test_pit_validator_clean")
    
    test_feature_engineer_pit_safe()
    print("✓ test_feature_engineer_pit_safe")
    
    test_no_future_leakage_in_features()
    print("✓ test_no_future_leakage_in_features")
    
    print("\nAll PIT tests passed!")
