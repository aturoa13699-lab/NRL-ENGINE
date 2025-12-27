"""
Baseline models for NRL prediction.
"""

from typing import Optional

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

from nrl_engine.config import Config, DEFAULT_CONFIG


def create_baseline_model(model_type: str = "hgbc", config: Config | None = None):
    """
    Create a baseline model.

    Args:
        model_type: "hgbc" (HistGradientBoosting) or "logistic"
        config: Configuration

    Returns:
        Unfitted sklearn model
    """
    config = config or DEFAULT_CONFIG

    if model_type == "logistic":
        return LogisticRegression(
            random_state=config.random_seed, max_iter=1000, solver="lbfgs"
        )

    # Default: HistGradientBoostingClassifier
    return HistGradientBoostingClassifier(
        random_state=config.random_seed,
        max_iter=config.hgbc_max_iter,
        max_depth=config.hgbc_max_depth,
        learning_rate=config.hgbc_learning_rate,
    )


def create_model_fn(model_type: str = "hgbc", config: Config | None = None):
    """
    Create a model factory function for use with EvaluationHarness.

    Args:
        model_type: "hgbc" or "logistic"
        config: Configuration

    Returns:
        Function that takes (X_train, y_train) and returns fitted model
    """
    config = config or DEFAULT_CONFIG

    def model_fn(X_train: np.ndarray, y_train: np.ndarray):
        model = create_baseline_model(model_type, config)
        model.fit(X_train, y_train)
        return model

    return model_fn
