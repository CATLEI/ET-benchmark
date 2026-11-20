#!/usr/bin/env python3
"""Offline protocol metrics on an existing hybrid run (does not touch chain.py).

Example::

    python scripts/reeval_protocol_metrics.py \\
      --run-dir results/aligned-model-sm70 \\
      --tilt-min -70 --tilt-max 70

Writes ``protocol_metrics.json`` under the run directory and merges new keys
into a sidecar ``protocol_evaluation/<algorithm>.json`` without modifying
existing ``evaluation.json`` files.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import hyperspy.api as hs
import numpy as np

from et_dflow.domain.evaluation.metrics.protocol_bypass import compute_protocol_metrics


def _discover_recons(run_dir: Path) -> List[Tuple[str, Path]]:
    pairs: List[Tuple[str, Path]] = []
    # Flat layout: results/<run>/<alg>/reconstruction.hspy
    for child in sorted(run_dir.iterdir()):
        if not child.is_dir():
            continue
        if child.name in {"data", "prepared_data", "protocol_evaluation"}:
            continue
        recon = child / "reconstruction.hspy"
        npy = child / "reconstruction.npy"
        if recon.is_file():
            pairs.append((child.name, recon))
        elif npy.is_file():
            pairs.append((child.name, npy))
    # Nested hybrid: results/<run>/data/<ds>/<alg>/
    data_root = run_dir / "data"
    if data_root.is_dir():
        for ds_dir in sorted(data_root.iterdir()):
            if not ds_dir.is_dir():
                continue
            for child in sorted(ds_dir.iterdir()):
                if not child.is_dir() or child.name == "prepared_data":
                    continue
                recon = child / "reconstruction.hspy"
                npy = child / "reconstruction.npy"
                label = f"{ds_dir.name}/{child.name}"
                if recon.is_file():
                    pairs.append((label, recon))
                elif npy.is_file():
                    pairs.append((label, npy))
    return pairs


def _load_volume(path: Path) -> np.ndarray:
    if path.suffix == ".npy":
        return np.asarray(np.load(str(path)), dtype=np.float64)
    sig = hs.load(str(path))
    return np.asarray(sig.data, dtype=np.float64)


def _find_gt(run_dir: Path, gt_path: Optional[Path]) -> Optional[np.ndarray]:
    if gt_path is not None and gt_path.is_file():
        return _load_volume(gt_path)
    candidates = [
        run_dir / "prepared_data" / "prepared_data_ground_truth.hspy",
        run_dir / "data" / "prepared_data" / "prepared_data_ground_truth.hspy",
    ]
    for ds_dir in (run_dir / "data").glob("*") if (run_dir / "data").is_dir() else []:
        candidates.append(
            ds_dir / "prepared_data" / "prepared_data_ground_truth.hspy"
        )
    for cand in candidates:
        if cand.is_file():
            return _load_volume(cand)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--gt", type=Path, default=None, help="Ground-truth .hspy/.npy")
    parser.add_argument("--tilt-min", type=float, default=-70.0)
    parser.add_argument("--tilt-max", type=float, default=70.0)
    parser.add_argument("--pixel-size-nm", type=float, default=None)
    parser.add_argument("--tilt-axis", choices=["x", "y"], default="y")
    args = parser.parse_args()

    run_dir = args.run_dir.resolve()
    if not run_dir.is_dir():
        print(f"Run dir not found: {run_dir}", file=sys.stderr)
        return 1

    gt = _find_gt(run_dir, args.gt.resolve() if args.gt else None)
    if gt is None:
        print("Ground truth not found; pass --gt", file=sys.stderr)
        return 1

    pairs = _discover_recons(run_dir)
    if not pairs:
        print(f"No reconstructions under {run_dir}", file=sys.stderr)
        return 1

    out_dir = run_dir / "protocol_evaluation"
    out_dir.mkdir(parents=True, exist_ok=True)
    summary: Dict[str, Any] = {
        "tilt_min": args.tilt_min,
        "tilt_max": args.tilt_max,
        "missing_wedge_deg": 180.0 - (args.tilt_max - args.tilt_min),
        "pixel_size_nm": args.pixel_size_nm,
        "algorithms": {},
    }

    for label, path in pairs:
        print(f"[protocol] {label} <- {path.name}", flush=True)
        try:
            recon = _load_volume(path)
            if recon.shape != gt.shape:
                print(
                    f"  skip shape mismatch recon={recon.shape} gt={gt.shape}",
                    flush=True,
                )
                continue
            metrics = compute_protocol_metrics(
                recon,
                gt,
                tilt_min_deg=args.tilt_min,
                tilt_max_deg=args.tilt_max,
                pixel_size_nm=args.pixel_size_nm,
                tilt_axis=args.tilt_axis,
            )
        except Exception as exc:  # noqa: BLE001 — keep batch going
            print(f"  failed: {exc}", flush=True)
            continue
        # Drop huge curve from per-alg print; keep in JSON.
        slim = {k: v for k, v in metrics.items() if k != "protocol_fsc_curve"}
        print(f"  {slim}", flush=True)
        alg_key = label.replace("/", "__")
        payload = {
            "algorithm": label,
            "source": str(path),
            "metrics": metrics,
        }
        (out_dir / f"{alg_key}.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )
        summary["algorithms"][label] = metrics

    summary_path = run_dir / "protocol_metrics.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[ok] wrote {summary_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
