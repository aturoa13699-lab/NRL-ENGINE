"""
Evaluation Harness.

Complete evaluation pipeline that:
1. Enforces odds orientation
2. Builds features (PIT-safe)
3. Creates walk-forward folds
4. Trains and evaluates model
5. Computes all metrics
6. Saves artifacts
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.ensemble import HistGradientBoostingClassifier

from nrl_engine.config import Config, DEFAULT_CONFIG
from nrl_engine.features.engineer import FeatureEngineer
from nrl_engine.evaluation.folds import create_anchored_folds, create_rolling_folds
from nrl_engine.evaluation.metrics import compute_all_metrics, compute_calibration
from nrl_engine.evaluation.odds_gate import enforce_odds_orientation


class EvaluationHarness:
    """
    Complete evaluation pipeline for NRL predictions.
    
    Example:
        harness = EvaluationHarness(model_data)
        results = harness.run_evaluation(test_seasons=[2023, 2024, 2025])
        harness.save_artifacts(results)
    """
    
    def __init__(
        self,
        data: pd.DataFrame,
        config: Optional[Config] = None,
        model_fn: Optional[Callable] = None
    ):
        """
        Initialize evaluation harness.
        
        Args:
            data: Match data with required columns
            config: Configuration (uses defaults if not provided)
            model_fn: Optional custom model factory function.
                      Should return a fitted model given (X_train, y_train).
                      If None, uses HistGradientBoostingClassifier.
        """
        self.config = config or DEFAULT_CONFIG
        self.config.ensure_dirs()
        self.raw_data = data.copy()
        self.model_fn = model_fn or self._default_model_fn
        
        # Will be set during run
        self.data = None
        self.feature_engineer = None
        self.dataset = None
        self.odds_report = None
    
    def _default_model_fn(self, X_train: np.ndarray, y_train: np.ndarray):
        """Default model: HistGradientBoostingClassifier."""
        model = HistGradientBoostingClassifier(
            random_state=self.config.random_seed,
            max_iter=self.config.hgbc_max_iter,
            max_depth=self.config.hgbc_max_depth,
            learning_rate=self.config.hgbc_learning_rate
        )
        model.fit(X_train, y_train)
        return model
    
    def _prepare_data(self) -> None:
        """Prepare data: validate, add columns, enforce odds orientation."""
        print("\n" + "=" * 60)
        print("DATA PREPARATION")
        print("=" * 60)
        
        self.data = self.raw_data.copy()
        
        # Robust date handling - check if already datetime
        if not pd.api.types.is_datetime64_any_dtype(self.data["date"]):
            self.data["date"] = pd.to_datetime(self.data["date"], errors="coerce")
        self.data = self.data.dropna(subset=["match_id", "date"]).sort_values("date").reset_index(drop=True)
        
        # Add derived columns
        if "home_win" not in self.data.columns:
            self.data["home_win"] = (self.data["home_score"] > self.data["away_score"]).astype(int)
        if "season" not in self.data.columns:
            self.data["season"] = self.data["date"].dt.year
        
        print(f"✓ Data shape: {self.data.shape}")
        print(f"✓ Seasons: {sorted(self.data['season'].unique())}")
        
        # Odds orientation gate
        has_odds = "home_odds_close" in self.data.columns and "away_odds_close" in self.data.columns
        
        if has_odds:
            self.data, self.odds_report = enforce_odds_orientation(
                self.data,
                config=self.config,
                verbose=True
            )
        else:
            print("\n⚠️ No odds columns found - skipping orientation check")
            self.odds_report = {"chosen": "no_odds", "action": "skipped"}
    
    def _build_features(self) -> None:
        """Build PIT-safe feature matrix."""
        print("\n" + "=" * 60)
        print("FEATURE ENGINEERING")
        print("=" * 60)
        
        self.feature_engineer = FeatureEngineer(self.data, self.config)
        
        required_cols = ["match_id", "date", "home_team", "away_team", "home_score", "away_score", "home_win"]
        features = self.feature_engineer.build_feature_matrix(self.data[required_cols])
        
        # Merge features with data
        self.dataset = self.data.merge(features, on="match_id", how="left")
        
        print(f"✓ Features: {features.shape[1]} columns")
        print(f"✓ Dataset: {self.dataset.shape}")
    
    def _get_feature_columns(self) -> List[str]:
        """Get list of feature columns to use for training."""
        return self.feature_engineer.get_feature_columns(self.dataset)
    
    def run_evaluation(
        self,
        test_seasons: Optional[List[int]] = None,
        fold_type: str = "anchored",
        train_window: int = 3
    ) -> Dict[str, Any]:
        """
        Run full evaluation pipeline.
        
        Args:
            test_seasons: Seasons to test on (None = auto-detect)
            fold_type: "anchored" or "rolling"
            train_window: Training window for rolling folds
        
        Returns:
            Dict with predictions, fold_results, aggregate metrics
        """
        # Prepare data
        self._prepare_data()
        
        # Build features
        self._build_features()
        
        # Create folds
        print("\n" + "=" * 60)
        print("WALK-FORWARD FOLDS")
        print("=" * 60)
        
        if fold_type == "rolling":
            folds = create_rolling_folds(
                self.dataset,
                test_seasons=test_seasons,
                train_window=train_window,
                config=self.config
            )
        else:
            folds = create_anchored_folds(
                self.dataset,
                test_seasons=test_seasons,
                config=self.config
            )
        
        if not folds:
            raise ValueError("No valid folds created!")
        
        # Train and predict
        print("\n" + "=" * 60)
        print("MODEL TRAINING")
        print("=" * 60)
        
        feature_cols = self._get_feature_columns()
        print(f"Using {len(feature_cols)} features")
        
        all_predictions = []
        fold_results = []
        
        for fold_id, test_season, train_df, test_df in folds:
            print(f"\n--- Fold {fold_id}: Test {test_season} ---")
            
            # Prepare data
            X_train = train_df[feature_cols].fillna(0.0).values
            y_train = train_df["home_win"].values.astype(int)
            X_test = test_df[feature_cols].fillna(0.0).values
            y_test = test_df["home_win"].values.astype(int)
            
            # Train model
            model = self.model_fn(X_train, y_train)
            
            # Get probability index for home_win=1
            if hasattr(model, "classes_"):
                idx = list(model.classes_).index(1)
            else:
                idx = 1
            
            # Predict
            probs = model.predict_proba(X_test)[:, idx]
            
            # Build output
            out_cols = ["match_id", "date", "home_team", "away_team", "home_win"]
            if "home_odds_close" in test_df.columns:
                out_cols += ["home_odds_close", "away_odds_close"]
            
            pred_df = test_df[out_cols].copy()
            pred_df["pred_home_win_prob"] = probs
            pred_df["fold_id"] = fold_id
            pred_df["test_season"] = test_season
            
            all_predictions.append(pred_df)
            
            # Fold metrics
            accuracy = float(((probs > 0.5).astype(int) == y_test).mean())
            print(f"  Accuracy: {accuracy:.1%}")
            
            fold_results.append({
                "fold_id": fold_id,
                "test_season": test_season,
                "n_train": len(train_df),
                "n_test": len(test_df),
                "accuracy": accuracy
            })
        
        # Combine predictions
        predictions = pd.concat(all_predictions, ignore_index=True)
        
        # Compute aggregate metrics
        print("\n" + "=" * 60)
        print("AGGREGATE METRICS")
        print("=" * 60)
        
        metrics = compute_all_metrics(predictions)
        
        # Print summary
        model_metrics = metrics["model_metrics"]
        print("\n[MODEL METRICS]")
        
        acc = model_metrics.get("accuracy", {})
        if "accuracy" in acc:
            print(f"  Accuracy: {acc['accuracy']:.1%}")
        
        brier = model_metrics.get("brier", {})
        if "brier" in brier:
            print(f"  Brier: {brier['brier']:.4f} (skill: {brier.get('brier_skill', 0):.3f})")
        
        auc = model_metrics.get("auc", {})
        if "auc" in auc:
            print(f"  AUC: {auc['auc']:.4f}")
        
        market_metrics = metrics.get("market_metrics", {})
        if market_metrics:
            print("\n[MARKET METRICS]")
            
            clv = market_metrics.get("clv", {})
            if "mean_clv" in clv:
                print(f"  CLV Mean: {clv['mean_clv']:.4f}")
                print(f"  CLV Positive Rate: {clv['positive_rate']:.1%}")
            
            mkt = market_metrics.get("market_baseline", {})
            if "brier" in mkt:
                print(f"  Market Brier: {mkt['brier']:.4f}")
            if "slope" in mkt and mkt["slope"] is not None:
                print(f"  Market Slope: {mkt['slope']:.4f}")
        
        return {
            "predictions": predictions,
            "fold_results": fold_results,
            "metrics": metrics,
            "odds_report": self.odds_report,
            "feature_columns": feature_cols,
            "timestamp": datetime.now().isoformat()
        }
    
    def save_artifacts(
        self,
        results: Dict[str, Any],
        save_dir: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Save evaluation artifacts.
        
        Args:
            results: Results from run_evaluation()
            save_dir: Directory to save to (defaults to config.eval_dir)
        
        Returns:
            Dict mapping artifact type to file path
        """
        save_dir = save_dir or self.config.eval_dir
        os.makedirs(save_dir, exist_ok=True)
        
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        paths = {}
        
        print("\n" + "=" * 60)
        print("SAVING ARTIFACTS")
        print("=" * 60)
        
        # Save predictions
        pred_path = os.path.join(save_dir, f"predictions_{ts}.csv")
        results["predictions"].to_csv(pred_path, index=False)
        paths["predictions"] = pred_path
        print(f"✓ Predictions: {pred_path}")
        
        # Save summary
        summary = {
            "timestamp": ts,
            "odds_report": results["odds_report"],
            "fold_results": results["fold_results"],
            "metrics": results["metrics"],
            "n_features": len(results["feature_columns"]),
            "feature_columns": results["feature_columns"][:20]  # First 20
        }
        
        sum_path = os.path.join(save_dir, f"summary_{ts}.json")
        with open(sum_path, "w") as f:
            json.dump(summary, f, indent=2, default=str)
        paths["summary"] = sum_path
        print(f"✓ Summary: {sum_path}")
        
        # Save calibration plot
        cal = results["metrics"]["model_metrics"].get("calibration", {})
        if "predicted" in cal and "actual" in cal:
            plt.figure(figsize=(8, 6))
            plt.plot(cal["predicted"], cal["actual"], marker="o", label="Model")
            plt.plot([0, 1], [0, 1], linestyle="--", color="gray", label="Perfect")
            plt.xlabel("Predicted Probability")
            plt.ylabel("Observed Frequency")
            plt.title("Calibration Curve")
            plt.legend()
            plt.grid(True, alpha=0.3)
            
            plot_path = os.path.join(save_dir, f"calibration_plot_{ts}.png")
            plt.savefig(plot_path, dpi=150, bbox_inches="tight")
            plt.close()
            paths["calibration_plot"] = plot_path
            print(f"✓ Calibration plot: {plot_path}")
        
        return paths


def run_quick_evaluation(
    data: pd.DataFrame,
    test_seasons: Optional[List[int]] = None,
    config: Optional[Config] = None
) -> Dict[str, Any]:
    """
    Convenience function for quick evaluation.
    
    Args:
        data: Match data
        test_seasons: Seasons to test on
        config: Configuration
    
    Returns:
        Evaluation results
    """
    harness = EvaluationHarness(data, config)
    results = harness.run_evaluation(test_seasons=test_seasons)
    harness.save_artifacts(results)
    return results
