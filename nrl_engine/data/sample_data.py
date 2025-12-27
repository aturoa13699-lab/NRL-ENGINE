"""
Generate realistic sample NRL data for testing.

Creates data with:
- Proper odds-outcome correlation (favorites win more often)
- Home advantage
- Realistic score distributions
- Multiple seasons
"""

from datetime import datetime, timedelta
from typing import List

import numpy as np
import pandas as pd


def generate_sample_data(
    n_matches: int = 500, seasons: list[int] = None, seed: int = 42
) -> pd.DataFrame:
    """
    Generate realistic NRL sample data.

    Args:
        n_matches: Total number of matches to generate
        seasons: List of seasons (years) to generate
        seed: Random seed for reproducibility

    Returns:
        DataFrame with match data including odds
    """
    if seasons is None:
        seasons = [2021, 2022, 2023, 2024, 2025]

    rng = np.random.default_rng(seed)

    teams = [
        "Brisbane Broncos",
        "Canterbury Bulldogs",
        "North Queensland Cowboys",
        "Dolphins",
        "St George Illawarra Dragons",
        "Parramatta Eels",
        "Newcastle Knights",
        "Penrith Panthers",
        "South Sydney Rabbitohs",
        "Canberra Raiders",
        "Sydney Roosters",
        "Manly Sea Eagles",
        "Cronulla Sharks",
        "Melbourne Storm",
        "Gold Coast Titans",
        "New Zealand Warriors",
        "Wests Tigers",
    ]

    venues = [
        "Suncorp Stadium",
        "AAMI Park",
        "Accor Stadium",
        "BlueBet Stadium",
        "McDonald Jones Stadium",
        "PointsBet Stadium",
        "4 Pines Park",
        "Queensland Country Bank Stadium",
    ]

    # Generate latent team strengths (persist across season for realism)
    # Stronger teams: Storm, Panthers, Roosters
    # Weaker teams: Tigers, Titans, Warriors
    base_strength = {t: rng.normal(0, 0.8) for t in teams}
    base_strength["Melbourne Storm"] += 0.5
    base_strength["Penrith Panthers"] += 0.4
    base_strength["Sydney Roosters"] += 0.3
    base_strength["Wests Tigers"] -= 0.4
    base_strength["Gold Coast Titans"] -= 0.3

    home_advantage = 0.3  # Home advantage in logit units

    rows = []
    match_idx = 0

    for season in seasons:
        # Season-specific strength adjustments (teams improve/decline)
        season_strength = {t: base_strength[t] + rng.normal(0, 0.2) for t in teams}

        season_start = datetime(season, 3, 1)
        season_end = datetime(season, 9, 30)
        season_days = (season_end - season_start).days

        per_season = max(1, n_matches // len(seasons))

        for _ in range(per_season):
            match_idx += 1

            # Random matchup (no repeat in same match)
            home, away = rng.choice(teams, size=2, replace=False)

            # Random date within season
            day_offset = int(rng.integers(0, max(1, season_days)))
            match_date = season_start + timedelta(days=day_offset)

            # Calculate win probability from strengths + home advantage
            logit = (season_strength[home] - season_strength[away]) + home_advantage
            p_home = 1 / (1 + np.exp(-logit))

            # Determine winner
            home_win = rng.random() < p_home

            # Generate scores
            # NRL typical: 20-30 total points per team, margin ~6-12 for favorites
            base_total = rng.normal(44, 10)
            expected_margin = (p_home - 0.5) * 16  # Favorites win by more
            actual_margin = rng.normal(expected_margin, 10)

            home_score = max(
                0, int((base_total / 2) + (actual_margin / 2) + rng.normal(0, 4))
            )
            away_score = max(
                0, int((base_total / 2) - (actual_margin / 2) + rng.normal(0, 4))
            )

            # Ensure outcome matches the probabilistic winner
            if home_win and home_score <= away_score:
                home_score = away_score + int(rng.integers(1, 10))
            elif not home_win and away_score <= home_score:
                away_score = home_score + int(rng.integers(1, 10))

            # Generate odds (with ~6% bookmaker vig)
            vig = 0.06
            noise = rng.normal(0, 0.03)  # Small noise in odds

            p_home_implied = np.clip(p_home * (1 + vig / 2) + noise, 0.08, 0.92)
            p_away_implied = np.clip((1 - p_home) * (1 + vig / 2) - noise, 0.08, 0.92)

            # Normalize to overround
            total_implied = p_home_implied + p_away_implied
            p_home_implied /= total_implied
            p_away_implied /= total_implied

            home_odds = round(1 / p_home_implied, 2)
            away_odds = round(1 / p_away_implied, 2)

            # Ensure odds are in realistic range
            home_odds = np.clip(home_odds, 1.10, 8.00)
            away_odds = np.clip(away_odds, 1.10, 8.00)

            rows.append(
                {
                    "match_id": f"SAMPLE_{season}_{match_idx:05d}",
                    "date": match_date.strftime("%Y-%m-%d"),
                    "season": season,
                    "round": (match_idx % 27) + 1,
                    "home_team": home,
                    "away_team": away,
                    "home_score": home_score,
                    "away_score": away_score,
                    "home_odds_close": float(home_odds),
                    "away_odds_close": float(away_odds),
                    "venue": rng.choice(venues),
                }
            )

    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)

    # Add home_win column
    df["home_win"] = (df["home_score"] > df["away_score"]).astype(int)

    return df


def validate_sample_data(df: pd.DataFrame) -> dict:
    """
    Validate that sample data has correct properties.

    Returns dict with validation results.
    """
    results = {}

    # Check odds-outcome correlation (should be positive)
    p_home_raw = 1.0 / df["home_odds_close"]
    p_away_raw = 1.0 / df["away_odds_close"]
    p_market = p_home_raw / (p_home_raw + p_away_raw)

    corr = np.corrcoef(p_market, df["home_win"])[0, 1]
    results["market_outcome_correlation"] = float(corr)
    results["correlation_healthy"] = corr > 0.15

    # Check home win rate (should be ~52-55%)
    home_win_rate = df["home_win"].mean()
    results["home_win_rate"] = float(home_win_rate)
    results["home_rate_healthy"] = 0.48 < home_win_rate < 0.58

    # Check favorite win rate (favorites should win >55%)
    df_temp = df.copy()
    df_temp["home_favorite"] = df_temp["home_odds_close"] < df_temp["away_odds_close"]
    df_temp["favorite_won"] = np.where(
        df_temp["home_favorite"], df_temp["home_win"], 1 - df_temp["home_win"]
    )
    fav_win_rate = df_temp["favorite_won"].mean()
    results["favorite_win_rate"] = float(fav_win_rate)
    results["favorite_rate_healthy"] = fav_win_rate > 0.55

    results["overall_healthy"] = all(
        [
            results["correlation_healthy"],
            results["home_rate_healthy"],
            results["favorite_rate_healthy"],
        ]
    )

    return results
