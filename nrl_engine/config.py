"""
Configuration for NRL Engine.

Centralizes all paths, feature settings, and constants.
"""

import os
from dataclasses import dataclass, field


@dataclass
class Config:
    """Configuration container for NRL Engine."""

    # ==========================================================================
    # PATHS
    # ==========================================================================

    # Base directory (auto-detected for Colab vs local)
    base_dir: str = field(default_factory=lambda: Config._detect_base_dir())

    @staticmethod
    def _detect_base_dir() -> str:
        """Detect base directory based on environment."""
        # Colab with Drive mounted
        if os.path.exists("/content/drive/MyDrive"):
            return "/content/drive/MyDrive/NRL_Engine"
        # Local development
        return os.path.expanduser("~/NRL_Engine")

    @property
    def proc_dir(self) -> str:
        """Processed data directory (scraper output)."""
        return os.path.join(self.base_dir, "proc")

    @property
    def raw_dir(self) -> str:
        """Raw data directory (manual uploads, Excel files)."""
        return os.path.join(self.base_dir, "raw_data")

    @property
    def eval_dir(self) -> str:
        """Evaluation artifacts directory."""
        return os.path.join(self.base_dir, "eval")

    def ensure_dirs(self) -> None:
        """Create all directories if they don't exist."""
        for d in [self.base_dir, self.proc_dir, self.raw_dir, self.eval_dir]:
            os.makedirs(d, exist_ok=True)

    # ==========================================================================
    # FEATURE ENGINEERING
    # ==========================================================================

    # Rolling window sizes for team stats
    rolling_windows: list[int] = field(default_factory=lambda: [3, 5, 10])

    # Minimum games required before computing rolling stats
    min_games_for_rolling: int = 3

    # Pythagorean win expectation exponent (NRL-tuned)
    pythagorean_exponent: float = 2.5

    # Feature version string (increment when features change)
    feature_version: str = "v1.0.0"

    # ==========================================================================
    # EVALUATION
    # ==========================================================================

    # Minimum training seasons for a fold
    min_train_seasons: int = 2

    # Minimum test matches for a valid fold
    min_test_matches: int = 20

    # Default test seasons (None = auto-detect from data)
    test_seasons: list[int] | None = None

    # ==========================================================================
    # ODDS ORIENTATION GATE
    # ==========================================================================

    # Minimum positive slope to consider odds orientation "healthy"
    odds_min_healthy_slope: float = 0.3

    # Minimum rows required for odds orientation check
    odds_min_rows: int = 20

    # Auto-fix swapped odds (True) or just report (False)
    odds_auto_fix: bool = True

    # Raise error if orientation ambiguous
    odds_fail_on_ambiguous: bool = True

    # ==========================================================================
    # MODEL
    # ==========================================================================

    # Random seed for reproducibility
    random_seed: int = 42

    # HistGradientBoostingClassifier settings
    hgbc_max_iter: int = 100
    hgbc_max_depth: int = 5
    hgbc_learning_rate: float = 0.1

    # Columns to exclude from features
    feature_exclude: list[str] = field(
        default_factory=lambda: [
            "match_id",
            "date",
            "season",
            "home_team",
            "away_team",
            "home_score",
            "away_score",
            "home_win",
            "home_odds_close",
            "away_odds_close",
            "home_odds_open",
            "away_odds_open",
            "asof_ts",
            "feature_version",
            "venue",
            "referee",
        ]
    )


# Global default config instance
DEFAULT_CONFIG = Config()
