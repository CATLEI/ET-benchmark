#!/usr/bin/env python3
"""
Merge several comparison_summary.json files (from multiple workflow runs)
into one summary with combined leaderboard_by_track / leaderboard_rows.

Usage:
  python scripts/merge_comparison_summaries.py run1/comparison_summary.json \\
      run2/comparison_summary.json -o merged.json
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def _load(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    p = argparse.ArgumentParser(description="Merge comparison_summary.json files")
    p.add_argument("inputs", nargs="+", type=Path, help="comparison_summary.json paths")
    p.add_argument("-o", "--output", type=Path, required=True, help="Output JSON path")
    args = p.parse_args()

    merged_metrics: Dict[str, Any] = {}
    algorithms: List[str] = []
    row_labels: List[str] = []
    by_track: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    all_rows: List[Dict[str, Any]] = []

    for path in args.inputs:
        data = _load(path)
        algorithms.extend(data.get("algorithms") or [])
        row_labels.extend(data.get("row_labels") or [])
        m = data.get("metrics") or {}
        for k, v in m.items():
            merged_metrics[k] = v
        lb = data.get("leaderboard_by_track") or {}
        for track, rows in lb.items():
            if isinstance(rows, list):
                by_track[track].extend(rows)
        rows = data.get("leaderboard_rows")
        if isinstance(rows, list):
            all_rows.extend(rows)

    out = {
        "algorithms": algorithms,
        "row_labels": row_labels,
        "metrics": merged_metrics,
        "leaderboard_by_track": dict(by_track),
        "leaderboard_rows": all_rows,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sources": [str(x) for x in args.inputs],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)


if __name__ == "__main__":
    main()
