"""
Walk-forward fold generation for time-series evaluation.

Supports:
- Anchored folds: Train on all prior seasons, test on target
- Rolling folds: Train on fixed window of prior seasons
"""

from typing import List, Tuple, Optional

import pandas as pd

from nrl_engine.config import Config, DEFAULT_CONFIG


def create_anchored_folds(
    df: pd.DataFrame,
    test_seasons: Optional[List[int]] = None,
    min_train_seasons: int = None,
    min_test_matches: int = None,
    config: Optional[Config] = None
) -> List[Tuple[int, int, pd.DataFrame, pd.DataFrame]]:
    """
    Create anchored walk-forward folds.
    
    Anchored = train on ALL prior seasons, test on target season.
    This maximizes training data for each fold.
    
    Args:
        df: DataFrame with 'season' column
        test_seasons: List of seasons to test on (None = auto-detect)
        min_train_seasons: Minimum training seasons required
        min_test_matches: Minimum test matches required
        config: Configuration object
    
    Returns:
        List of (fold_id, test_season, train_df, test_df) tuples
    """
    config = config or DEFAULT_CONFIG
    min_train_seasons = min_train_seasons or config.min_train_seasons
    min_test_matches = min_test_matches or config.min_test_matches
    
    if "season" not in df.columns:
        raise ValueError("DataFrame must have 'season' column")
    
    available_seasons = sorted(df["season"].dropna().unique())
    
    # Auto-detect test seasons if not provided
    if test_seasons is None:
        # Test on seasons that have at least min_train_seasons before them
        test_seasons = [
            s for s in available_seasons
            if sum(1 for prev in available_seasons if prev < s) >= min_train_seasons
        ]
    
    folds = []
    fold_id = 0
    
    for test_season in test_seasons:
        # Training = all seasons before test
        train_seasons = [s for s in available_seasons if s < test_season]
        
        if len(train_seasons) < min_train_seasons:
            print(f"  Skipping {test_season}: only {len(train_seasons)} train seasons (need {min_train_seasons})")
            continue
        
        train_df = df[df["season"].isin(train_seasons)].copy()
        test_df = df[df["season"] == test_season].copy()
        
        if len(test_df) < min_test_matches:
            print(f"  Skipping {test_season}: only {len(test_df)} test matches (need {min_test_matches})")
            continue
        
        fold_id += 1
        folds.append((fold_id, test_season, train_df, test_df))
        
        print(f"  Fold {fold_id}: Train {min(train_seasons)}-{max(train_seasons)} ({len(train_df)}), "
              f"Test {test_season} ({len(test_df)})")
    
    return folds


def create_rolling_folds(
    df: pd.DataFrame,
    test_seasons: Optional[List[int]] = None,
    train_window: int = 3,
    min_test_matches: int = None,
    config: Optional[Config] = None
) -> List[Tuple[int, int, pd.DataFrame, pd.DataFrame]]:
    """
    Create rolling window walk-forward folds.
    
    Rolling = train on fixed window of prior seasons.
    This can reduce stale data issues but uses less training data.
    
    Args:
        df: DataFrame with 'season' column
        test_seasons: List of seasons to test on (None = auto-detect)
        train_window: Number of prior seasons to train on
        min_test_matches: Minimum test matches required
        config: Configuration object
    
    Returns:
        List of (fold_id, test_season, train_df, test_df) tuples
    """
    config = config or DEFAULT_CONFIG
    min_test_matches = min_test_matches or config.min_test_matches
    
    if "season" not in df.columns:
        raise ValueError("DataFrame must have 'season' column")
    
    available_seasons = sorted(df["season"].dropna().unique())
    
    # Auto-detect test seasons if not provided
    if test_seasons is None:
        test_seasons = [
            s for s in available_seasons
            if sum(1 for prev in available_seasons if prev < s) >= train_window
        ]
    
    folds = []
    fold_id = 0
    
    for test_season in test_seasons:
        # Get prior seasons
        prior_seasons = sorted([s for s in available_seasons if s < test_season])
        
        if len(prior_seasons) < train_window:
            print(f"  Skipping {test_season}: only {len(prior_seasons)} prior seasons (need {train_window})")
            continue
        
        # Take only the most recent `train_window` seasons
        train_seasons = prior_seasons[-train_window:]
        
        train_df = df[df["season"].isin(train_seasons)].copy()
        test_df = df[df["season"] == test_season].copy()
        
        if len(test_df) < min_test_matches:
            print(f"  Skipping {test_season}: only {len(test_df)} test matches (need {min_test_matches})")
            continue
        
        fold_id += 1
        folds.append((fold_id, test_season, train_df, test_df))
        
        print(f"  Fold {fold_id}: Train {min(train_seasons)}-{max(train_seasons)} ({len(train_df)}), "
              f"Test {test_season} ({len(test_df)})")
    
    return folds


def auto_detect_test_seasons(
    df: pd.DataFrame,
    min_matches_per_season: int = 50,
    n_test_seasons: int = 3
) -> List[int]:
    """
    Automatically detect suitable test seasons.
    
    Args:
        df: DataFrame with 'season' column
        min_matches_per_season: Minimum matches for a season to be testable
        n_test_seasons: Number of most recent seasons to test
    
    Returns:
        List of test seasons
    """
    if "season" not in df.columns:
        raise ValueError("DataFrame must have 'season' column")
    
    # Count matches per season
    season_counts = df.groupby("season").size()
    
    # Filter to seasons with enough matches
    valid_seasons = season_counts[season_counts >= min_matches_per_season].index.tolist()
    valid_seasons = sorted(valid_seasons)
    
    # Return most recent n seasons
    return valid_seasons[-n_test_seasons:] if len(valid_seasons) >= n_test_seasons else valid_seasons
