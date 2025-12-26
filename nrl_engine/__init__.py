"""
NRL Prediction Engine

A point-in-time safe NRL match prediction framework with walk-forward evaluation.
"""

__version__ = "1.0.0"

from nrl_engine.config import Config
from nrl_engine.data.loader import DataLoader
from nrl_engine.features.engineer import FeatureEngineer
from nrl_engine.evaluation.harness import EvaluationHarness
from nrl_engine.evaluation.odds_gate import enforce_odds_orientation

__all__ = [
    "Config",
    "DataLoader", 
    "FeatureEngineer",
    "EvaluationHarness",
    "enforce_odds_orientation",
]
