"""
Parquet export module (SPEC-1).

Writes partitioned Parquet files for DuckDB/Pandas analysis.
"""
import json
from pathlib import Path

import pandas as pd

from nrlscraper.config import settings


def to_parquet(rows: list[dict], table: str, season: int) -> str:
    """
    Export matches to partitioned Parquet.

    Args:
        rows: List of match dicts
        table: Table name (e.g., 'matches')
        season: Season year for partitioning

    Returns:
        Path to output file
    """
    df = pd.DataFrame(rows)

    # Ensure date is proper datetime
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])

    out_dir = Path(settings.exports_dir) / table / f'season={season}'
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / 'part-000.parquet'
    df.to_parquet(out_path, index=False, compression='snappy')

    # Write manifest
    manifest = {
        'version': '1',
        'table': table,
        'season': season,
        'rows': len(df),
    }
    (out_dir / '_manifest.json').write_text(json.dumps(manifest, indent=2))

    return str(out_path)


def to_parquet_multi(rows: list[dict], table: str) -> list[str]:
    """
    Export matches to Parquet, partitioned by season.

    Args:
        rows: List of match dicts
        table: Table name

    Returns:
        List of output paths
    """
    df = pd.DataFrame(rows)

    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])

    paths = []
    for season, group in df.groupby('season'):
        path = to_parquet(group.to_dict('records'), table, int(season))
        paths.append(path)

    return paths


def load_parquet(path: str) -> pd.DataFrame:
    """Load Parquet file or directory."""
    return pd.read_parquet(path)


def export_to_parquet(rows: list[dict], prefix: str = "nrl_matches") -> str:
    """
    Convenience wrapper for Railway main.py.

    Auto-detects season from data and exports to parquet.

    Args:
        rows: List of match dicts
        prefix: Output file prefix

    Returns:
        Path to output file
    """
    if not rows:
        return ""

    # Detect season from first row
    first = rows[0]
    season = first.get('season') or pd.to_datetime(first.get('date')).year

    return to_parquet(rows, prefix, season)
