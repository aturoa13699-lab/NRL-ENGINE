"""
Robust data loader for NRL Engine.

Searches multiple locations in priority order, validates schema,
and falls back to sample data if nothing found.
"""

import os
import glob
from datetime import datetime
from typing import Tuple, Dict, Any, Optional, List

import pandas as pd

from nrl_engine.config import Config, DEFAULT_CONFIG
from nrl_engine.data.sample_data import generate_sample_data


class DataLoader:
    """
    Robust data loader that searches multiple locations.
    
    Priority order:
    1. PROC_DIR: Processed data from scraper
    2. RAW_DIR: Manual CSV/parquet uploads
    3. EVAL_DIR: Previous predictions (diagnostics only, not for training)
    4. Fallback: Generate sample data
    """
    
    # Required columns for training
    REQUIRED_COLS = {
        "match_id", "date", "home_team", "away_team",
        "home_score", "away_score"
    }
    
    # Optional but recommended columns
    ODDS_COLS = {"home_odds_close", "away_odds_close"}
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or DEFAULT_CONFIG
        self.config.ensure_dirs()
    
    def load(self, prefer: str = "proc") -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Load model data from available sources.
        
        Args:
            prefer: Priority preference - "proc", "raw", or "eval"
        
        Returns:
            (dataframe, metadata_dict)
        """
        meta = {
            "source": None,
            "path": None,
            "notes": [],
            "has_odds": False,
            "timestamp": datetime.now().isoformat()
        }
        
        # Build candidate file lists
        proc_patterns = [
            os.path.join(self.config.proc_dir, "nrl_backfill_*.csv"),
            os.path.join(self.config.proc_dir, "nrl_matches_*.csv"),
            os.path.join(self.config.proc_dir, "model_data_*.csv"),
            os.path.join(self.config.proc_dir, "*.parquet"),
        ]
        
        raw_patterns = [
            os.path.join(self.config.raw_dir, "*.csv"),
            os.path.join(self.config.raw_dir, "*.parquet"),
        ]
        
        eval_patterns = [
            os.path.join(self.config.eval_dir, "predictions_*.csv"),
        ]
        
        # Priority based on preference
        priority_map = {
            "proc": [proc_patterns, raw_patterns, eval_patterns],
            "raw": [raw_patterns, proc_patterns, eval_patterns],
            "eval": [eval_patterns, proc_patterns, raw_patterns],
        }
        priority = priority_map.get(prefer, priority_map["proc"])
        
        # Find first available file
        chosen = None
        for pattern_list in priority:
            chosen = self._find_latest(pattern_list)
            if chosen:
                break
        
        if chosen:
            df = self._load_file(chosen)
            meta["source"] = "file"
            meta["path"] = chosen
            meta["notes"].append(f"Loaded: {os.path.basename(chosen)}")
            
            # Check if this is an eval file (may be missing columns)
            if self.config.eval_dir in chosen:
                meta["notes"].append("WARNING: Loaded from eval dir - may be missing training columns")
        else:
            # Fallback to sample data
            df = generate_sample_data(
                n_matches=500,
                seasons=[2021, 2022, 2023, 2024, 2025]
            )
            meta["source"] = "sample"
            meta["path"] = None
            meta["notes"].append("No data files found - generated sample data")
        
        # Validate and prepare
        df, validation_notes = self._validate_and_prepare(df)
        meta["notes"].extend(validation_notes)
        meta["has_odds"] = self.ODDS_COLS.issubset(df.columns)
        meta["shape"] = df.shape
        meta["seasons"] = sorted(df["season"].unique().tolist()) if "season" in df.columns else []
        
        return df, meta
    
    def _find_latest(self, patterns: List[str]) -> Optional[str]:
        """Find the most recent file matching any pattern."""
        candidates = []
        for pattern in patterns:
            candidates.extend(glob.glob(pattern))
        if not candidates:
            return None
        return sorted(candidates)[-1]
    
    def _load_file(self, path: str) -> pd.DataFrame:
        """Load a single file."""
        if path.endswith(".parquet"):
            return pd.read_parquet(path)
        return pd.read_csv(path)
    
    def _validate_and_prepare(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """Validate required columns and add derived columns."""
        notes = []
        
        # Check required columns
        missing = self.REQUIRED_COLS - set(df.columns)
        if missing:
            raise ValueError(
                f"Data missing required columns: {missing}\n"
                f"Available columns: {list(df.columns)[:30]}"
            )
        
        notes.append(f"✓ Required columns present")
        
        # Check odds columns
        if self.ODDS_COLS.issubset(df.columns):
            notes.append(f"✓ Odds columns present")
        else:
            notes.append(f"⚠ Odds columns missing - CLV metrics will be skipped")
        
        # Prepare data
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["match_id", "date"]).sort_values("date").reset_index(drop=True)
        
        # Add derived columns
        df["home_win"] = (df["home_score"] > df["away_score"]).astype(int)
        df["season"] = df["date"].dt.year
        
        notes.append(f"✓ Shape: {df.shape}")
        notes.append(f"✓ Date range: {df['date'].min().date()} to {df['date'].max().date()}")
        notes.append(f"✓ Home win rate: {df['home_win'].mean():.3f}")
        
        return df, notes
    
    def save_to_proc(self, df: pd.DataFrame, prefix: str = "nrl_data") -> str:
        """Save dataframe to PROC_DIR with timestamp."""
        self.config.ensure_dirs()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(self.config.proc_dir, f"{prefix}_{ts}.csv")
        df.to_csv(path, index=False)
        return path
