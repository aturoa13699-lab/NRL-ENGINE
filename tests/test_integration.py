"""
Integration tests for full pipeline.
"""

import os
import tempfile
import pandas as pd

from nrl_engine.config import Config
from nrl_engine.data.sample_data import generate_sample_data
from nrl_engine.data.loader import DataLoader
from nrl_engine.evaluation.harness import EvaluationHarness


def test_full_pipeline_with_sample_data():
    """Test complete pipeline from data generation to evaluation."""
    # Generate data
    data = generate_sample_data(n_matches=300, seasons=[2022, 2023, 2024])

    # Verify required columns
    required = {
        "match_id",
        "date",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
        "home_win",
    }
    assert required.issubset(data.columns), f"Missing: {required - set(data.columns)}"

    # Run evaluation
    config = Config()
    harness = EvaluationHarness(data, config)
    results = harness.run_evaluation(test_seasons=[2024])

    # Verify results
    assert "predictions" in results
    assert len(results["predictions"]) > 0
    assert "metrics" in results
    assert results["metrics"]["model_metrics"]["accuracy"]["accuracy"] > 0


def test_save_and_reload_data():
    """Test that saved data can be reloaded correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup config with temp directory
        config = Config()
        config.base_dir = tmpdir
        config.ensure_dirs()

        # Generate and save (use model_data prefix to match loader patterns)
        data = generate_sample_data(n_matches=100, seasons=[2023])
        loader = DataLoader(config)
        save_path = loader.save_to_proc(data, prefix="model_data")

        assert os.path.exists(save_path)

        # Reload
        loaded_data, meta = loader.load(prefer="proc")

        assert meta["source"] == "file"
        assert len(loaded_data) == len(data)
        assert "home_team" in loaded_data.columns
        assert "home_score" in loaded_data.columns


def test_date_handling_from_csv():
    """Test that dates are correctly parsed when loading from CSV."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = Config()
        config.base_dir = tmpdir
        config.ensure_dirs()

        # Generate data
        data = generate_sample_data(n_matches=50, seasons=[2023])

        # Save to CSV (dates become strings)
        csv_path = os.path.join(config.proc_dir, "test_dates.csv")
        data.to_csv(csv_path, index=False)

        # Reload - this should handle string dates
        loader = DataLoader(config)
        loaded_data, meta = loader.load(prefer="proc")

        # Verify dates are datetime
        assert pd.api.types.is_datetime64_any_dtype(loaded_data["date"])


if __name__ == "__main__":
    print("Running integration tests...")

    test_full_pipeline_with_sample_data()
    print("✓ test_full_pipeline_with_sample_data")

    test_save_and_reload_data()
    print("✓ test_save_and_reload_data")

    test_date_handling_from_csv()
    print("✓ test_date_handling_from_csv")

    print("\nAll integration tests passed!")
