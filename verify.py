#!/usr/bin/env python
"""Verification script for NRL Engine."""

import sys

def main():
    print("=" * 60)
    print("NRL ENGINE VERIFICATION")
    print("=" * 60)

    errors = []

    # Test 1: Imports
    print("\n[1/5] Testing imports...")
    try:
        from nrl_engine import Config, DataLoader, FeatureEngineer, EvaluationHarness
        from nrl_engine.evaluation.odds_gate import enforce_odds_orientation
        from nrl_engine.data.sample_data import generate_sample_data, validate_sample_data
        print("  ✓ All imports successful")
    except ImportError as e:
        errors.append(f"Import failed: {e}")
        print(f"  ✗ {e}")

    # Test 2: Sample data generation
    print("\n[2/5] Testing sample data generation...")
    try:
        data = generate_sample_data(n_matches=100, seed=42)
        assert len(data) == 100, f"Expected 100 rows, got {len(data)}"
        assert "home_odds_close" in data.columns
        assert "home_win" in data.columns
        print(f"  ✓ Generated {len(data)} matches")
    except Exception as e:
        errors.append(f"Sample data failed: {e}")
        print(f"  ✗ {e}")

    # Test 3: Sample data validation
    print("\n[3/5] Testing sample data validation...")
    try:
        validation = validate_sample_data(data)
        assert validation["correlation_healthy"], "Correlation should be healthy"
        assert validation["overall_healthy"], "Overall should be healthy"
        print(f"  ✓ Validation passed: correlation={validation['market_outcome_correlation']:.3f}")
    except Exception as e:
        errors.append(f"Validation failed: {e}")
        print(f"  ✗ {e}")

    # Test 4: Odds orientation gate
    print("\n[4/5] Testing odds orientation gate...")
    try:
        config = Config()
        config.odds_auto_fix = True
        config.odds_fail_on_ambiguous = False

        fixed_data, report = enforce_odds_orientation(data, config=config, verbose=False)
        assert report["chosen"] in ["as_is", "swapped"], f"Unexpected choice: {report['chosen']}"
        print(f"  ✓ Orientation: {report['chosen']}, action: {report['action']}")
    except Exception as e:
        errors.append(f"Odds gate failed: {e}")
        print(f"  ✗ {e}")

    # Test 5: Full pipeline (mini)
    print("\n[5/5] Testing full pipeline...")
    try:
        # Generate more data for proper folds
        data = generate_sample_data(n_matches=300, seasons=[2022, 2023, 2024])

        harness = EvaluationHarness(data, Config())
        results = harness.run_evaluation(test_seasons=[2024], fold_type="anchored")

        assert "predictions" in results
        assert len(results["predictions"]) > 0
        assert "metrics" in results

        acc = results["metrics"]["model_metrics"]["accuracy"]["accuracy"]
        print(f"  ✓ Pipeline complete: {len(results['predictions'])} predictions, accuracy={acc:.1%}")
    except Exception as e:
        errors.append(f"Pipeline failed: {e}")
        print(f"  ✗ {e}")

    # Summary
    print("\n" + "=" * 60)
    if errors:
        print(f"FAILED: {len(errors)} error(s)")
        for err in errors:
            print(f"  - {err}")
        return 1
    else:
        print("ALL CHECKS PASSED ✓")
        return 0

if __name__ == "__main__":
    sys.exit(main())
