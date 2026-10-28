"""Inspect/import groundwater CSVs without assuming a fixed local path.

The importer only maps columns it can identify and emits a validation report. It
does not silently treat a forecast column as an observed measurement.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, "backend")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", type=Path)
    args = parser.parse_args()
    try:
        import pandas as pd
    except ImportError:
        print("pandas is required")
        return 2
    frame = pd.read_csv(args.csv_path)
    print(f"file: {args.csv_path}")
    print(f"rows: {len(frame)}")
    print(f"columns: {', '.join(map(str, frame.columns))}")
    print("missing values:")
    print(frame.isna().sum().to_string())
    datetime_candidates = [column for column in frame.columns if any(token in str(column).lower() for token in ("date", "time", "timestamp"))]
    station_candidates = [column for column in frame.columns if any(token in str(column).lower() for token in ("station", "well", "site", "location"))]
    level_candidates = [column for column in frame.columns if any(token in str(column).lower() for token in ("water_level", "groundwater", "depth", "level"))]
    print(f"datetime candidates: {datetime_candidates}")
    print(f"station candidates: {station_candidates}")
    print(f"groundwater candidates: {level_candidates}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

