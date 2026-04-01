#!/usr/bin/env python3
"""
Expand benchmark_datasets/registry.yaml into an ET-dflow benchmark YAML fragment
(`datasets:` block). Paths are placeholders — replace DATA_ROOT and file names.

Usage:
  python scripts/expand_registry_to_config.py benchmark_datasets/registry.example.yaml \\
      --data-root /data/benchmarks --output datasets.fragment.yaml
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List


def _load_yaml(path: Path) -> Dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ImportError as e:
        raise SystemExit("PyYAML is required: pip install pyyaml") from e
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise SystemExit("Registry root must be a mapping")
    return data


def _emit_datasets(registry: Dict[str, Any], data_root: str) -> str:
    tracks = registry.get("tracks") or {}
    if not isinstance(tracks, dict):
        raise SystemExit("registry.tracks must be a mapping")
    lines: List[str] = ["datasets:"]
    for track_name, track_cfg in tracks.items():
        if not isinstance(track_cfg, dict):
            continue
        ds_list = track_cfg.get("datasets") or []
        if not isinstance(ds_list, list):
            continue
        for ds_id in ds_list:
            key = f"{track_name.replace('-', '_').replace(' ', '_')}__{ds_id}"
            base = f"{data_root.rstrip('/')}/{track_name}/{ds_id}"
            lines.append(f"  {key}:")
            lines.append(f'    path: "{base}/raw/tilt_series.hspy"')
            lines.append('    format: "hyperspy"')
            if "NoGT" in track_name or "T2" in track_name:
                lines.append("    # ground_truth_path: omitted for T2-style tracks")
            else:
                lines.append(f'    ground_truth_path: "{base}/raw/ground_truth.hspy"')
            lines.append("    metadata:")
            lines.append(f'      track: "{track_name}"')
            lines.append(f'      dataset_id: "{ds_id}"')
            if "Robustness" in track_name or "T3" in track_name:
                lines.append('      variant: "EDIT_ME"')
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description="Generate datasets: YAML from registry.yaml")
    p.add_argument("registry", type=Path, help="Path to registry.yaml")
    p.add_argument("--data-root", default="/data/benchmarks", help="Root prefix for placeholder paths")
    p.add_argument("-o", "--output", type=Path, help="Write fragment to file (stdout if omitted)")
    args = p.parse_args()
    reg = _load_yaml(args.registry)
    text = _emit_datasets(reg, args.data_root)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
