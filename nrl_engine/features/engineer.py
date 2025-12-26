"""
PIT-Safe Feature Engineering for NRL matches.

All features are computed using only data available before each match.
"""

from typing import Dict, Any, Optional, List

import numpy as np
import pandas as pd

from nrl_engine.config import Config, DEFAULT_CONFIG
from nrl_engine.features.pit_validator import PITValidator


class FeatureEngineer:
    """
    Point-in-time safe feature engineering.
    
    Computes rolling team statistics, Pythagorean expectations,
    head-to-head records, and other features using only historical data.
    """
    
    def __init__(
        self,
        historical_data: pd.DataFrame,
        config: Optional[Config] = None
    ):
        """
        Initialize feature engineer with historical data.
        
        Args:
            historical_data: DataFrame with all historical matches
            config: Configuration (uses defaults if not provided)
        """
        self.config = config or DEFAULT_CONFIG
        self.pit = PITValidator()
        
        # Prepare historical data
        self.data = historical_data.copy()
        self.data["date"] = pd.to_datetime(self.data["date"], errors="coerce")
        self.data = self.data.sort_values("date").reset_index(drop=True)
        
        # Build team game index for fast lookups
        self.team_games: Dict[str, pd.DataFrame] = {}
        self._build_team_index()
    
    def _build_team_index(self) -> None:
        """Build per-team game history for fast lookups."""
        teams = pd.unique(
            pd.concat([self.data["home_team"], self.data["away_team"]], ignore_index=True)
        )
        
        for team in teams:
            # Get all games for this team
            mask = (self.data["home_team"] == team) | (self.data["away_team"] == team)
            team_df = self.data[mask].copy()
            
            # Add team-centric columns
            team_df["is_home"] = team_df["home_team"] == team
            team_df["points_for"] = np.where(
                team_df["is_home"],
                team_df["home_score"],
                team_df["away_score"]
            )
            team_df["points_against"] = np.where(
                team_df["is_home"],
                team_df["away_score"],
                team_df["home_score"]
            )
            team_df["margin"] = team_df["points_for"] - team_df["points_against"]
            team_df["win"] = (team_df["margin"] > 0).astype(int)
            
            self.team_games[team] = team_df.sort_values("date")
    
    def _get_team_history(self, team: str, before: pd.Timestamp) -> pd.DataFrame:
        """
        Get team's game history before a given date (PIT-safe).
        
        Args:
            team: Team name
            before: Cutoff timestamp (exclusive)
        
        Returns:
            DataFrame with team's past games, most recent first
        """
        if team not in self.team_games:
            return pd.DataFrame()
        
        team_df = self.team_games[team]
        
        # PIT validation - filter to only past games
        safe_df = self.pit.validate(
            feature_name=f"history_{team[:10]}",
            source_df=team_df,
            asof_ts=before,
            date_col="date"
        )
        
        # Return most recent first
        return safe_df.sort_values("date", ascending=False)
    
    def _compute_rolling_stats(
        self,
        history: pd.DataFrame,
        n_games: int,
        prefix: str
    ) -> Dict[str, Any]:
        """
        Compute rolling statistics from team history.
        
        Args:
            history: Team history (most recent first)
            n_games: Number of games to include
            prefix: Prefix for feature names (e.g., "home_5")
        
        Returns:
            Dict of feature name -> value
        """
        features = {
            f"{prefix}_games": 0,
            f"{prefix}_pf": None,
            f"{prefix}_pa": None,
            f"{prefix}_margin": None,
            f"{prefix}_win_rate": None,
        }
        
        if history.empty:
            return features
        
        # Get last n games
        recent = history.head(n_games)
        features[f"{prefix}_games"] = len(recent)
        
        # Need minimum games for reliable stats
        if len(recent) < self.config.min_games_for_rolling:
            return features
        
        features[f"{prefix}_pf"] = float(recent["points_for"].mean())
        features[f"{prefix}_pa"] = float(recent["points_against"].mean())
        features[f"{prefix}_margin"] = float(recent["margin"].mean())
        features[f"{prefix}_win_rate"] = float(recent["win"].mean())
        
        return features
    
    def _compute_pythagorean(
        self,
        home_history: pd.DataFrame,
        away_history: pd.DataFrame,
        window: int = 10
    ) -> Dict[str, Any]:
        """
        Compute Pythagorean win expectation for both teams.
        
        Args:
            home_history: Home team's history
            away_history: Away team's history
            window: Number of games to use
        
        Returns:
            Dict with home_pythag, away_pythag, pythag_diff
        """
        exp = self.config.pythagorean_exponent
        
        def calc_pythag(history: pd.DataFrame) -> Optional[float]:
            if history.empty or len(history) < self.config.min_games_for_rolling:
                return None
            
            recent = history.head(window)
            pf = recent["points_for"].sum()
            pa = recent["points_against"].sum()
            
            if pf + pa <= 0:
                return None
            
            return float((pf ** exp) / ((pf ** exp) + (pa ** exp)))
        
        home_pythag = calc_pythag(home_history)
        away_pythag = calc_pythag(away_history)
        
        pythag_diff = None
        if home_pythag is not None and away_pythag is not None:
            pythag_diff = home_pythag - away_pythag
        
        return {
            "home_pythag": home_pythag,
            "away_pythag": away_pythag,
            "pythag_diff": pythag_diff
        }
    
    def _compute_h2h(
        self,
        home_team: str,
        away_team: str,
        before: pd.Timestamp,
        window: int = 10
    ) -> Dict[str, Any]:
        """
        Compute head-to-head record between teams.
        
        Args:
            home_team: Home team name
            away_team: Away team name
            before: Cutoff timestamp
            window: Max games to consider
        
        Returns:
            Dict with h2h stats
        """
        # Filter to matchups between these teams
        mask = (
            ((self.data["home_team"] == home_team) & (self.data["away_team"] == away_team)) |
            ((self.data["home_team"] == away_team) & (self.data["away_team"] == home_team))
        )
        h2h_df = self.data[mask].copy()
        
        # PIT filter
        h2h_df = self.pit.validate(
            feature_name="h2h",
            source_df=h2h_df,
            asof_ts=before,
            date_col="date"
        )
        
        if h2h_df.empty:
            return {
                "h2h_games": 0,
                "h2h_home_win_rate": None,
                "h2h_margin": None
            }
        
        # Get recent games
        recent = h2h_df.sort_values("date", ascending=False).head(window)
        
        # Calculate stats from home team's perspective
        home_wins = 0
        total_margin = 0
        
        for _, row in recent.iterrows():
            if row["home_team"] == home_team:
                home_wins += int(row["home_score"] > row["away_score"])
                total_margin += row["home_score"] - row["away_score"]
            else:
                home_wins += int(row["away_score"] > row["home_score"])
                total_margin += row["away_score"] - row["home_score"]
        
        return {
            "h2h_games": len(recent),
            "h2h_home_win_rate": float(home_wins / len(recent)) if len(recent) > 0 else None,
            "h2h_margin": float(total_margin / len(recent)) if len(recent) > 0 else None
        }
    
    def _compute_rest_days(
        self,
        home_history: pd.DataFrame,
        away_history: pd.DataFrame,
        match_date: pd.Timestamp
    ) -> Dict[str, Any]:
        """Compute days since last game for each team."""
        def days_since_last(history: pd.DataFrame, date: pd.Timestamp) -> Optional[int]:
            if history.empty:
                return None
            last_game = history["date"].iloc[0]  # Most recent first
            return max(0, (date - last_game).days)
        
        home_rest = days_since_last(home_history, match_date)
        away_rest = days_since_last(away_history, match_date)
        
        rest_diff = None
        if home_rest is not None and away_rest is not None:
            rest_diff = home_rest - away_rest
        
        return {
            "home_rest": home_rest,
            "away_rest": away_rest,
            "rest_diff": rest_diff
        }
    
    def compute_features(self, match: pd.Series) -> Dict[str, Any]:
        """
        Compute all features for a single match.
        
        Args:
            match: Series with match details
        
        Returns:
            Dict of feature name -> value
        """
        match_date = pd.to_datetime(match["date"])
        home_team = match["home_team"]
        away_team = match["away_team"]
        
        # Get team histories
        home_history = self._get_team_history(home_team, match_date)
        away_history = self._get_team_history(away_team, match_date)
        
        # Initialize features
        features = {
            "match_id": match["match_id"],
            "asof_ts": str(match_date),
            "feature_version": self.config.feature_version
        }
        
        # Rolling stats for each window
        for window in self.config.rolling_windows:
            home_stats = self._compute_rolling_stats(home_history, window, f"home_{window}")
            away_stats = self._compute_rolling_stats(away_history, window, f"away_{window}")
            
            features.update(home_stats)
            features.update(away_stats)
            
            # Compute differentials
            for stat in ["pf", "pa", "margin", "win_rate"]:
                home_key = f"home_{window}_{stat}"
                away_key = f"away_{window}_{stat}"
                
                if features[home_key] is not None and features[away_key] is not None:
                    features[f"diff_{window}_{stat}"] = features[home_key] - features[away_key]
        
        # Pythagorean expectation
        features.update(self._compute_pythagorean(home_history, away_history))
        
        # Head-to-head
        features.update(self._compute_h2h(home_team, away_team, match_date))
        
        # Rest days
        features.update(self._compute_rest_days(home_history, away_history, match_date))
        
        return features
    
    def build_feature_matrix(self, matches: pd.DataFrame) -> pd.DataFrame:
        """
        Build feature matrix for multiple matches.
        
        Args:
            matches: DataFrame with matches to compute features for
        
        Returns:
            DataFrame with one row per match, containing all features
        """
        required_cols = ["match_id", "date", "home_team", "away_team"]
        missing = set(required_cols) - set(matches.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        
        # Compute features for each match
        rows = []
        for _, match in matches.iterrows():
            features = self.compute_features(match)
            rows.append(features)
        
        feature_df = pd.DataFrame(rows)
        
        # Print PIT report
        pit_report = self.pit.report()
        print(f"PIT Status: {pit_report['status']}")
        if pit_report['violations_blocked'] > 0:
            print(f"  Blocked {pit_report['total_rows_blocked']} future rows")
        
        return feature_df
    
    def get_feature_columns(self, df: pd.DataFrame) -> List[str]:
        """Get list of feature columns (excluding metadata and targets)."""
        exclude = set(self.config.feature_exclude)
        
        feature_cols = [
            col for col in df.columns
            if col not in exclude
            and df[col].dtype in ['float64', 'int64', 'float32', 'int32']
        ]
        
        return feature_cols
