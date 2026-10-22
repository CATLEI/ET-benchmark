#!/usr/bin/env python3
"""Re-run master-side output_to_gt + evaluation + comparison on an existing run.

Does NOT re-submit remote algorithm jobs. Requires each algorithm directory to
already contain ``reconstruction.hspy`` (native or previously transformed).

Example::

    python scripts/reeval_from_run_dir.py \\
      --run-dir results/20260421_103015 \\
      --config configs/wbp_sirt_hybrid_aligned_model_sm70.yaml

With ``algorithms.*.parameters.output_to_gt`` set, the script backups native
volumes once and replays the GT-frame transform before metrics. Prefer
``evaluation.align_reconstruction: false`` so eval does not transform twice.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from dflow.python import OPIO

from et_dflow.domain.evaluation.volume_alignment import (
    apply_output_to_gt_file,
    output_to_gt_enabled,
    resolve_algorithm_output_to_gt,
)
from et_dflow.infrastructure.workflows.ops.comparison_op import ComparisonOP
from et_dflow.infrastructure.workflows.ops.evaluation_op import EvaluationOP


def _sanitize(name: str) -> str:
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in name)


def _resolve(path: str, config_dir: Path) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    cwd_cand = Path.cwd() / p
    if cwd_cand.exists():
        return cwd_cand.resolve()
    return (config_dir / p).resolve()


def _discover_pairs(run_dir: Path) -> List[Tuple[str, str, Path]]:
    data_root = run_dir / "data"
    if not data_root.is_dir():
        raise FileNotFoundError(
            f"No data/ under {run_dir}. Expected hybrid layout "
            f"data/<dataset>/<algorithm>/reconstruction.hspy"
        )
    pairs: List[Tuple[str, str, Path]] = []
    for ds_dir in sorted(data_root.iterdir()):
        if not ds_dir.is_dir():
            continue
        ds_key = ds_dir.name
        for child in sorted(ds_dir.iterdir()):
            if not child.is_dir() or child.name == "prepared_data":
                continue
            recon = child / "reconstruction.hspy"
            native = child / "reconstruction_native.hspy"
            if recon.is_file() or native.is_file():
                pairs.append((ds_key, child.name, child))
    return pairs


def _find_gt(
    run_dir: Path,
    ds_key: str,
    ds_cfg: Dict[str, Any],
    config_dir: Path,
) -> Optional[Path]:
    prepared = (
        run_dir / "data" / _sanitize(ds_key) / "prepared_data" / "prepared_data_ground_truth.hspy"
    )
    if prepared.is_file():
        return prepared
    prepared2 = run_dir / "data" / ds_key / "prepared_data" / "prepared_data_ground_truth.hspy"
    if prepared2.is_file():
        return prepared2
    gt = ds_cfg.get("ground_truth_path")
    if gt:
        p = _resolve(str(gt), config_dir)
        if p.is_file():
            return p
    return None


def _fill_target_shape(
    geom: Dict[str, Any],
    eval_cfg: Dict[str, Any],
    ds_cfg: Dict[str, Any],
) -> Dict[str, Any]:
    out = dict(geom)
    if out.get("target_shape"):
        return out
    ts = eval_cfg.get("align_target_shape")
    if not ts:
        ts = (ds_cfg.get("metadata") or {}).get("gt_shape")
    if ts and len(ts) == 3:
        out["target_shape"] = list(ts)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-dir",
        required=True,
        type=Path,
        help="Existing results/<timestamp> directory from a hybrid benchmark",
    )
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="YAML with algorithms.*.output_to_gt and evaluation:",
    )
    args = parser.parse_args()

    run_dir = args.run_dir.resolve()
    config_path = args.config.resolve()
    if not run_dir.is_dir():
        print(f"ERROR: run-dir not found: {run_dir}", file=sys.stderr)
        return 1
    if not config_path.is_file():
        print(f"ERROR: config not found: {config_path}", file=sys.stderr)
        return 1

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    eval_cfg = dict(config.get("evaluation") or {})
    metrics_list = list(eval_cfg.get("metrics") or ["psnr", "ssim", "mse"])
    datasets_cfg: Dict[str, Any] = dict(config.get("datasets") or {})
    config_dir = config_path.parent

    pairs = _discover_pairs(run_dir)
    if not pairs:
        print(
            f"ERROR: no reconstruction.hspy under {run_dir / 'data'}",
            file=sys.stderr,
        )
        return 1

    print(f"[reeval] run_dir={run_dir}")
    print(f"[reeval] config={config_path}")
    print(f"[reeval] evaluation={eval_cfg}")
    print(f"[reeval] found {len(pairs)} reconstruction(s)")

    eval_op = EvaluationOP()
    algorithm_names: List[str] = []
    row_labels: List[str] = []
    metrics_files: List[str] = []
    execution_metadata_files: List[str] = []
    multi = len({ds for ds, _, _ in pairs}) > 1

    for ds_key, alg_name, alg_dir in pairs:
        recon_path = alg_dir / "reconstruction.hspy"
        native_path = alg_dir / "reconstruction_native.hspy"
        if not recon_path.is_file() and native_path.is_file():
            shutil.copy2(native_path, recon_path)

        ds_cfg = datasets_cfg.get(ds_key) or {}
        if not ds_cfg:
            for k, v in datasets_cfg.items():
                if _sanitize(k) == ds_key:
                    ds_cfg = v or {}
                    break
        suite_meta = dict((ds_cfg or {}).get("metadata") or {})

        geom = resolve_algorithm_output_to_gt(config, alg_name)
        if output_to_gt_enabled(geom):
            geom = _fill_target_shape(geom or {}, eval_cfg, ds_cfg or {})
            print(f"[reeval] output_to_gt {ds_key}/{alg_name} ...")
            meta = apply_output_to_gt_file(recon_path, geom, force_from_native=True)
            print(
                f"[reeval]   applied={meta.get('applied')} "
                f"{meta.get('reconstruction_shape_before')} -> "
                f"{meta.get('reconstruction_shape_after')}"
            )
        else:
            print(f"[reeval] output_to_gt skipped for {ds_key}/{alg_name}")

        metrics_file = alg_dir / "evaluation.json"
        exec_meta = alg_dir / "execution_metadata.json"
        gt_path = _find_gt(run_dir, ds_key, ds_cfg or {}, config_dir)

        op_in: Dict[str, Any] = {
            "reconstruction": str(recon_path),
            "metrics": metrics_list,
            "algorithm_name": alg_name,
            "metrics_file": str(metrics_file),
            "dataset_key": ds_key,
            "suite_metadata": suite_meta,
            "evaluation_config": eval_cfg,
        }
        if gt_path is not None:
            op_in["ground_truth"] = str(gt_path)
            print(f"[reeval] {ds_key}/{alg_name}: GT={gt_path}")
        else:
            print(
                f"[reeval] WARNING {ds_key}/{alg_name}: no GT — "
                "PSNR/SSIM/MSE may be empty"
            )

        print(f"[reeval] evaluating {ds_key}/{alg_name} ...")
        eval_op.execute(OPIO(op_in))
        print(f"[reeval] wrote {metrics_file}")

        algorithm_names.append(alg_name)
        row_labels.append(f"{ds_key}/{alg_name}" if multi else alg_name)
        metrics_files.append(str(metrics_file))
        if exec_meta.is_file():
            execution_metadata_files.append(str(exec_meta))

    if not metrics_files:
        print("ERROR: no evaluations produced", file=sys.stderr)
        return 1

    print("[reeval] running comparison ...")
    comp_op = ComparisonOP()
    op_comp: Dict[str, Any] = {
        "metrics_files": metrics_files,
        "algorithm_names": algorithm_names,
        "row_labels": row_labels,
    }
    if len(execution_metadata_files) == len(metrics_files):
        op_comp["execution_metadata_files"] = execution_metadata_files
    comp_out = comp_op.execute(OPIO(op_comp))

    for name, dest_name in (
        ("comparison_report", "comparison_report.html"),
        ("comparison_json", "comparison_summary.json"),
        ("leaderboard_json", "leaderboard/suite_leaderboard.json"),
    ):
        src = comp_out.get(name)
        if src and Path(src).exists():
            dest = run_dir / dest_name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            print(f"[reeval] copied {dest}")

    src_cmp = Path(comp_out.get("comparison_json", "")).parent
    if src_cmp.is_dir():
        lb_dir = src_cmp / "leaderboard"
        if lb_dir.is_dir():
            out_lb = run_dir / "leaderboard"
            out_lb.mkdir(parents=True, exist_ok=True)
            for child in lb_dir.iterdir():
                if child.is_file():
                    shutil.copy2(str(child), str(out_lb / child.name))
        csv_src = src_cmp / "leaderboard.csv"
        if csv_src.is_file():
            shutil.copy2(str(csv_src), str(run_dir / "leaderboard.csv"))

    print(f"[reeval] done. See {run_dir / 'comparison_report.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
