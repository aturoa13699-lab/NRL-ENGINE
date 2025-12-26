"""
CLI entry point for NRL Engine evaluation.

Usage:
    python -m nrl_engine.run_eval --test-seasons 2023 2024 2025
    python -m nrl_engine.run_eval --use-sample
"""

import argparse
import sys
from typing import List, Optional

from nrl_engine.config import Config
from nrl_engine.data.loader import DataLoader
from nrl_engine.data.sample_data import generate_sample_data, validate_sample_data
from nrl_engine.evaluation.harness import EvaluationHarness


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="NRL Engine - Match prediction evaluation"
    )
    
    parser.add_argument(
        "--test-seasons",
        type=int,
        nargs="+",
        default=None,
        help="Seasons to test on (e.g., 2023 2024 2025). Auto-detects if not specified."
    )
    
    parser.add_argument(
        "--fold-type",
        choices=["anchored", "rolling"],
        default="anchored",
        help="Type of walk-forward folds (default: anchored)"
    )
    
    parser.add_argument(
        "--train-window",
        type=int,
        default=3,
        help="Training window for rolling folds (default: 3)"
    )
    
    parser.add_argument(
        "--prefer",
        choices=["proc", "raw", "eval"],
        default="proc",
        help="Data source preference (default: proc)"
    )
    
    parser.add_argument(
        "--use-sample",
        action="store_true",
        help="Use generated sample data instead of loading from files"
    )
    
    parser.add_argument(
        "--n-matches",
        type=int,
        default=500,
        help="Number of matches for sample data (default: 500)"
    )
    
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Don't save artifacts"
    )
    
    parser.add_argument(
        "--base-dir",
        type=str,
        default=None,
        help="Override base directory for data/artifacts"
    )
    
    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_args()
    
    print("=" * 60)
    print("NRL ENGINE - EVALUATION")
    print("=" * 60)
    
    # Setup config
    config = Config()
    if args.base_dir:
        config.base_dir = args.base_dir
    config.ensure_dirs()
    
    # Load or generate data
    if args.use_sample:
        print("\nGenerating sample data...")
        model_data = generate_sample_data(
            n_matches=args.n_matches,
            seasons=[2021, 2022, 2023, 2024, 2025]
        )
        
        # Validate sample data
        validation = validate_sample_data(model_data)
        print(f"Sample validation: {validation}")
        
        if not validation["overall_healthy"]:
            print("⚠️ Sample data validation failed - proceeding anyway")
    else:
        print("\nLoading data...")
        loader = DataLoader(config)
        model_data, load_meta = loader.load(prefer=args.prefer)
        
        print(f"Source: {load_meta['source']}")
        if load_meta['path']:
            print(f"Path: {load_meta['path']}")
        for note in load_meta['notes']:
            print(f"  {note}")
    
    # Run evaluation
    print(f"\nRunning evaluation...")
    print(f"  Fold type: {args.fold_type}")
    print(f"  Test seasons: {args.test_seasons or 'auto-detect'}")
    
    harness = EvaluationHarness(model_data, config)
    
    results = harness.run_evaluation(
        test_seasons=args.test_seasons,
        fold_type=args.fold_type,
        train_window=args.train_window
    )
    
    # Save artifacts
    if not args.no_save:
        paths = harness.save_artifacts(results)
        print("\nArtifacts saved:")
        for name, path in paths.items():
            print(f"  {name}: {path}")
    
    print("\n" + "=" * 60)
    print("EVALUATION COMPLETE")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
