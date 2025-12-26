# NRL Prediction Engine

A point-in-time (PIT) safe NRL match prediction framework with walk-forward evaluation.

## Repository Structure

```
nrl_engine/
├── README.md
├── requirements.txt
├── setup.py
├── nrl_engine/
│   ├── __init__.py
│   ├── config.py              # Paths, feature config, constants
│   ├── data/
│   │   ├── __init__.py
│   │   ├── loader.py          # Robust data loading (Drive/local/sample)
│   │   ├── scraper.py         # ASB scraper (placeholder)
│   │   └── sample_data.py     # Generate realistic sample data
│   ├── features/
│   │   ├── __init__.py
│   │   ├── engineer.py        # PIT-safe feature engineering
│   │   ├── pit_validator.py   # Point-in-time validation
│   │   └── registry.py        # Feature registry + versioning
│   ├── evaluation/
│   │   ├── __init__.py
│   │   ├── folds.py           # Walk-forward fold generation
│   │   ├── metrics.py         # Brier, AUC, CLV, calibration
│   │   ├── harness.py         # Full evaluation pipeline
│   │   └── odds_gate.py       # Odds orientation enforcement
│   ├── models/
│   │   ├── __init__.py
│   │   └── baseline.py        # Baseline model (HGBC)
│   └── run_eval.py            # CLI entry point
├── notebooks/
│   └── nrl_colab_runner.ipynb # Thin Colab runner
└── tests/
    ├── __init__.py
    ├── test_pit.py
    ├── test_odds_gate.py
    └── test_metrics.py
```

## Quick Start

### Option 1: Run from Colab (recommended)

1. Open in Colab: `https://colab.research.google.com/github/YOUR_USERNAME/nrl-engine/blob/main/notebooks/nrl_colab_runner.ipynb`

2. The notebook will:
   - Clone the repo
   - Install dependencies
   - Mount your Drive for data/artifacts
   - Run the evaluation pipeline

### Option 2: Local development

```bash
git clone https://github.com/YOUR_USERNAME/nrl-engine.git
cd nrl-engine
pip install -e .
python -m nrl_engine.run_eval --seasons 2023 2024 2025
```

## Key Features

### Point-in-Time (PIT) Safety
All features are computed using only data available before each match. The `PITValidator` blocks any future data leakage.

### Odds Orientation Gate
Automatic detection and correction of swapped home/away odds columns. Fails loudly if orientation is ambiguous (likely join corruption).

### Walk-Forward Evaluation
Anchored folds: train on all prior seasons, test on target season. No future leakage in train/test splits.

### Metrics
- **Model metrics**: Brier score, AUC, accuracy, calibration curve
- **Market metrics**: CLV (vs devigged closing odds), market baseline Brier

## Configuration

Edit `nrl_engine/config.py`:

```python
# Feature windows
ROLLING_WINDOWS = [3, 5, 10]
MIN_GAMES_FOR_ROLLING = 3

# Evaluation
MIN_TRAIN_SEASONS = 2
MIN_TEST_MATCHES = 20
```

## Data Sources

The loader searches in priority order:
1. `PROC_DIR`: Processed data from scraper
2. `RAW_DIR`: Manual CSV uploads
3. `EVAL_DIR`: Previous predictions (diagnostics only)
4. **Fallback**: Generate sample data

For production, run the scraper or upload real match data to `RAW_DIR`.

## Artifacts

All outputs saved to `EVAL_DIR`:
- `predictions_{timestamp}.csv` - Match-level predictions
- `summary_{timestamp}.json` - Metrics summary
- `calibration_plot_{timestamp}.png` - Calibration curve

## License

MIT
