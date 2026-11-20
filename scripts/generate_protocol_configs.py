#!/usr/bin/env python3
"""Clone the frozen sm70 hybrid YAML into protocol batch configs.

Writes multi-dataset YAMLs under ``configs/protocol/`` (Axis W / S / WS).
Does not edit ``configs/wbp_sirt_hybrid_aligned_model_sm70.yaml``.
Algorithm blocks are copied verbatim; tilt angles at runtime come from each
dataset's HyperSpy ``TEM.tilt_series`` metadata.

Example::

    PYTHONPATH=. python scripts/generate_protocol_configs.py \\
      --base configs/wbp_sirt_hybrid_aligned_model_sm70.yaml
"""

from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

# Axis W: tilt range scan at 1°
AXIS_W: List[Tuple[str, float, str]] = [
    ("sm80", 80.0, "aligned_model_sm80_v1"),
    ("sm70", 70.0, "aligned_model_sm70_v1"),
    ("sm60", 60.0, "aligned_model_sm60_v1"),
    ("sm50", 50.0, "aligned_model_sm50_v1"),
    ("sm40", 40.0, "aligned_model_sm40_v1"),
]

# Axis S: sparse at ±70° — include 1° baseline + native 2°/4°
# (key, step_deg, folder, enabled)
AXIS_S: List[Tuple[str, float, str, bool]] = [
    ("aligned_model_sm70", 1.0, "aligned_model_sm70_v1", True),
    ("aligned_model_sm70_step2", 2.0, "aligned_model_sm70_step2_v1", True),
    ("aligned_model_sm70_step4", 4.0, "aligned_model_sm70_step4_v1", True),
]

# Interaction: ±40° × 2° (~41 frames)
INTERACTION = ("aligned_model_sm40_step2", 2.0, "aligned_model_sm40_v1_step2deg")

# Obsolete single-condition axis YAMLs (removed on regenerate)
SINGLE_AXIS_GLOBS = (
    "axis_w_sm*.yaml",
    "axis_s_sm70_step*.yaml",
    "axis_ws_sm40_step*.yaml",
)


def _load(path: Path) -> Dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _dump(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# AUTO-GENERATED protocol batch config. Do not edit the sm70 base.\n"
        "# See docs/ET_TOMO_BENCHMARK_PROTOCOL.md and configs/protocol/README.md\n"
        "# Angles: prefer HyperSpy TEM.tilt_series on each dataset; "
        "algorithm tilt_range is fallback only.\n"
    )
    path.write_text(
        header + yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _dataset_entry(
    key: str,
    dataset_dir: str,
    tmin: float,
    tmax: float,
    extra_meta: Dict[str, Any],
    *,
    enabled: bool = True,
) -> Dict[str, Any]:
    wedge = 180.0 - (tmax - tmin)
    return {
        "enabled": enabled,
        "path": f"./data/datasets/simulated/{dataset_dir}/raw/tilt_series.hspy",
        "format": "hyperspy",
        "ground_truth_path": (
            f"./data/datasets/simulated/{dataset_dir}/ground_truth/volume.hspy"
        ),
        "metadata": {
            "variant": key,
            "tilt_range": [tmin, tmax],
            "missing_wedge_angle": abs(tmin),
            "missing_wedge_deg": wedge,
            "gt_shape": [512, 512, 512],
            **extra_meta,
        },
    }


def _rewrite_tilts_fallback(cfg: Dict[str, Any], tmin: float, tmax: float) -> None:
    """Widen algorithm tilt_range fallback to cover the batch (metadata preferred)."""
    for _name, alg in (cfg.get("algorithms") or {}).items():
        params = alg.get("parameters") or {}
        if "tilt_range" in params:
            params["tilt_range"] = [tmin, tmax]
        alg["parameters"] = params


def make_axis_w_batch(base: Dict[str, Any], out_dir: Path) -> Path:
    cfg = copy.deepcopy(base)
    datasets: Dict[str, Any] = {}
    for variant, alpha, folder in AXIS_W:
        key = f"aligned_model_{variant}"
        datasets[key] = _dataset_entry(
            key,
            folder,
            -alpha,
            alpha,
            {"protocol_axis": "W", "angular_step_deg": 1.0},
        )
    cfg["datasets"] = datasets
    _rewrite_tilts_fallback(cfg, -80.0, 80.0)
    cfg.setdefault("workflow", {})["name"] = "protocol-axis-w-batch"
    path = out_dir / "axis_w_batch.yaml"
    _dump(path, cfg)
    return path


def make_axis_s_batch(base: Dict[str, Any], out_dir: Path) -> Path:
    cfg = copy.deepcopy(base)
    datasets: Dict[str, Any] = {}
    for key, step, folder, enabled in AXIS_S:
        datasets[key] = _dataset_entry(
            key,
            folder,
            -70.0,
            70.0,
            {"protocol_axis": "S", "angular_step_deg": float(step)},
            enabled=enabled,
        )
    cfg["datasets"] = datasets
    _rewrite_tilts_fallback(cfg, -70.0, 70.0)
    cfg.setdefault("workflow", {})["name"] = "protocol-axis-s-batch"
    path = out_dir / "axis_s_batch.yaml"
    _dump(path, cfg)
    return path


def make_axis_ws_batch(base: Dict[str, Any], out_dir: Path) -> Path:
    cfg = copy.deepcopy(base)
    key, step, folder = INTERACTION
    cfg["datasets"] = {
        key: _dataset_entry(
            key,
            folder,
            -40.0,
            40.0,
            {"protocol_axis": "W×S", "angular_step_deg": float(step)},
        )
    }
    _rewrite_tilts_fallback(cfg, -40.0, 40.0)
    cfg.setdefault("workflow", {})["name"] = "protocol-axis-ws-batch"
    path = out_dir / "axis_ws_batch.yaml"
    _dump(path, cfg)
    return path


def make_task_b_isonet(base: Dict[str, Any], out_dir: Path) -> Path:
    cfg = copy.deepcopy(base)
    cfg["datasets"] = {
        "aligned_model_sm70": _dataset_entry(
            "aligned_model_sm70",
            "aligned_model_sm70_v1",
            -70.0,
            70.0,
            {"protocol_axis": "B", "angular_step_deg": 1.0},
        )
    }
    _rewrite_tilts_fallback(cfg, -70.0, 70.0)
    algs = cfg.get("algorithms") or {}
    for name, alg in algs.items():
        alg["enabled"] = name == "isonet"
    if "isonet" in algs:
        algs["isonet"]["enabled"] = True
        params = algs["isonet"].setdefault("parameters", {})
        params["isonet_pipeline"] = True
        params.setdefault("isonet_pixel_size", 10.0)
    cfg.setdefault("workflow", {})["name"] = "protocol-task-b-isonet-sm70"
    path = out_dir / "task_b_isonet_sm70.yaml"
    _dump(path, cfg)
    return path


def make_task_c_wucon(base: Dict[str, Any], out_dir: Path) -> Path:
    cfg = copy.deepcopy(base)
    cfg["datasets"] = {
        "aligned_model_sm70": _dataset_entry(
            "aligned_model_sm70",
            "aligned_model_sm70_v1",
            -70.0,
            70.0,
            {"protocol_axis": "C", "angular_step_deg": 1.0},
        )
    }
    _rewrite_tilts_fallback(cfg, -70.0, 70.0)
    algs = cfg.get("algorithms") or {}
    for name, alg in algs.items():
        alg["enabled"] = name == "wucon"
    if "wucon" in algs:
        algs["wucon"]["enabled"] = True
        params = algs["wucon"].setdefault("parameters", {})
        params["wucon_pipeline"] = True
        params["wucon_recon_subset"] = False
    cfg.setdefault("workflow", {})["name"] = "protocol-task-c-wucon-sm70"
    path = out_dir / "task_c_wucon_sm70.yaml"
    _dump(path, cfg)
    return path


def make_task_c_deepdewedge(base: Dict[str, Any], out_dir: Path) -> Path:
    cfg = copy.deepcopy(base)
    cfg["datasets"] = {
        "aligned_model_sm70": _dataset_entry(
            "aligned_model_sm70",
            "aligned_model_sm70_v1",
            -70.0,
            70.0,
            {"protocol_axis": "C", "angular_step_deg": 1.0},
        )
    }
    _rewrite_tilts_fallback(cfg, -70.0, 70.0)
    algs = cfg.get("algorithms") or {}
    for name, alg in algs.items():
        alg["enabled"] = name == "deepdewedge"
    cfg.setdefault("workflow", {})["name"] = "protocol-task-c-deepdewedge-sm70"
    path = out_dir / "task_c_deepdewedge_sm70.yaml"
    _dump(path, cfg)
    return path


def _remove_single_axis_yamls(out_dir: Path) -> List[Path]:
    removed: List[Path] = []
    if not out_dir.is_dir():
        return removed
    for pattern in SINGLE_AXIS_GLOBS:
        for path in sorted(out_dir.glob(pattern)):
            if path.name.endswith("_batch.yaml"):
                continue
            path.unlink()
            removed.append(path)
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        type=Path,
        default=Path("configs/wbp_sirt_hybrid_aligned_model_sm70.yaml"),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("configs/protocol"),
    )
    args = parser.parse_args()
    base_path = args.base.resolve()
    if not base_path.is_file():
        print(f"Base config not found: {base_path}", file=sys.stderr)
        return 1
    base = _load(base_path)
    out_dir = args.out_dir.resolve()

    removed = _remove_single_axis_yamls(out_dir)
    for p in removed:
        print(f"[rm] {p}", flush=True)

    written = [
        make_axis_w_batch(base, out_dir),
        make_axis_s_batch(base, out_dir),
        make_axis_ws_batch(base, out_dir),
        make_task_b_isonet(base, out_dir),
        make_task_c_wucon(base, out_dir),
        make_task_c_deepdewedge(base, out_dir),
    ]
    for p in written:
        print(f"[ok] {p}", flush=True)
    print(
        f"[done] {len(written)} protocol configs; removed {len(removed)} singles",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
