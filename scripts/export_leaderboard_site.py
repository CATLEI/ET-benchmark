#!/usr/bin/env python3
"""Export audited / legacy run dirs into docs/benchmark-site/data/cohorts.json.

Reuses track assignment and collection helpers from ``report_protocol_tracks``
without changing that sidecar HTML report.

Example::

    PYTHONPATH=. python scripts/export_leaderboard_site.py \\
      --run-dir results/aligned-model-sm70 \\
      --run-dir results/aligned-model-sm70-20261111 \\
      --datasets-root data/datasets/simulated \\
      --output docs/benchmark-site/data/cohorts.json
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Allow ``python scripts/export_leaderboard_site.py`` from repo root.
_REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import report_protocol_tracks as _rpt  # noqa: E402

_assign_track = _rpt._assign_track
_best_for_metric = _rpt._best_for_metric
_collect_algorithms = _rpt._collect_algorithms

# Leaderboard tasks (condition axes), not method families.
TASKS = ["general", "missing wedge", "sparse view"]

# Optional badge on each algorithm row (does not split the leaderboard).
TRACK_TO_METHOD_GROUP = {
    "A_projection_to_volume": "classical",
    "B_post_recon_wedge_fill": "self-supervised",
    "C_self_supervised": "self-supervised",
    "oracle_prior": "grey prior",
    "unassigned": "classical",
}

# Per-algorithm overrides (display category, independent of track tabs).
ALGO_METHOD_GROUP = {
    "tvm": "TV regularized iterative",
    "dart": "grey prior",
    "tvr_dart": "grey prior",
}

# Shared primary columns; wedge keys matter most for missing-wedge views.
PRIMARY_BY_TASK = {
    "general": [
        "protocol_affine_ssim",
        "protocol_affine_cc",
        "ssim",
        "psnr",
        "dice",
    ],
    "missing wedge": [
        "protocol_affine_ssim",
        "protocol_affine_cc",
        "protocol_wedge_out_cc",
        "protocol_wedge_in_cc",
        "ssim",
        "psnr",
    ],
    "sparse view": [
        "protocol_affine_ssim",
        "protocol_affine_cc",
        "ssim",
        "psnr",
        "dice",
    ],
}

PROTOCOL_KEYS = {
    "protocol_affine_ssim",
    "protocol_affine_cc",
    "protocol_wedge_out_cc",
    "protocol_wedge_in_cc",
    "protocol_fsc_res_0p5_px",
    "protocol_fsc_res_0p143_px",
}


def method_group_from_track(track: str) -> str:
    return TRACK_TO_METHOD_GROUP.get(track, "classical")


def method_group_for_algorithm(name: str, track: str) -> str:
    key = name.replace("-", "_").lower()
    if key in ALGO_METHOD_GROUP:
        return ALGO_METHOD_GROUP[key]
    return method_group_from_track(track)


def dataset_id_from_tilt(tilt_abs: int) -> str:
    """Public dataset id, e.g. SM_70."""
    return f"SM_{int(tilt_abs)}"

# Display names: prefer hyphenated ids used by Docker result folders.
_ALGO_CANON = {
    "astra_fbp": "astra-fbp",
    "astra_sirt": "astra-sirt",
    "tigre_sirt": "tigre-sirt",
    "tvr_dart": "tvr-dart",
}


def _json_safe(obj: Any) -> Any:
    """Replace NaN/Inf so browser ``JSON.parse`` accepts the file."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    return obj


def _canonical_algo_name(name: str) -> str:
    raw = name.strip()
    key = raw.replace("-", "_").lower()
    if key in _ALGO_CANON:
        return _ALGO_CANON[key]
    # Keep known hyphen forms as-is; otherwise lower-case hyphens.
    if "-" in raw:
        return raw.lower()
    return raw.lower().replace("_", "-") if "_" in raw else raw


def _row_better(cand: Dict[str, Any], prev: Dict[str, Any]) -> bool:
    if cand.get("has_protocol") and not prev.get("has_protocol"):
        return True
    if prev.get("has_protocol") and not cand.get("has_protocol"):
        return False
    return int(cand.get("_n_metrics") or 0) >= int(prev.get("_n_metrics") or 0)

CONDITION_RE = re.compile(
    r"sm(?P<tilt>\d+)(?:_step(?P<step>\d+))?(?:_v\d+)?$",
    re.IGNORECASE,
)


def _load_yaml_simple(path: Path) -> Dict[str, Any]:
    """Minimal YAML subset reader (no PyYAML required for flat metadata)."""
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        # Fallback: only handle simple key: value / short lists used in metadata.
        out: Dict[str, Any] = {}
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if line.startswith(" ") or line.startswith("-"):
                continue
            if ":" not in line:
                continue
            key, raw = line.split(":", 1)
            val = raw.strip().strip("'\"")
            if val in {"true", "True"}:
                out[key.strip()] = True
            elif val in {"false", "False"}:
                out[key.strip()] = False
            else:
                try:
                    if "." in val:
                        out[key.strip()] = float(val)
                    else:
                        out[key.strip()] = int(val)
                except ValueError:
                    out[key.strip()] = val
        return out


def condition_id_from_parts(tilt: int, step: float) -> str:
    step_i = int(step) if float(step).is_integer() else step
    return f"sm{tilt}_step{step_i}"


def infer_condition_from_name(name: str) -> Optional[Tuple[int, float]]:
    base = name.replace("-", "_")
    # aligned_model_sm70_step2_v1 / aligned_model_sm70 / sm70
    m = re.search(
        r"(?:aligned_model_)?sm(?P<tilt>\d+)(?:_step(?P<step>\d+))?",
        base,
        re.IGNORECASE,
    )
    if not m:
        return None
    tilt = int(m.group("tilt"))
    step = float(m.group("step") or 1)
    return tilt, step


def infer_condition_for_run(
    run_dir: Path,
    algo_blob: Dict[str, Any],
) -> Dict[str, Any]:
    """Build condition metadata for one algorithm row."""
    meta: Dict[str, Any] = {}
    legacy = algo_blob.get("legacy") or {}
    # evaluation.json often nests dataset metadata under metrics sibling;
    # _collect_algorithms only keeps metrics — pull from execution if present.
    execution = algo_blob.get("execution") or {}
    ds_meta = execution.get("dataset_metadata") or {}
    meta.update(ds_meta)

    tilt_range = meta.get("tilt_range")
    tilt_abs = None
    if isinstance(tilt_range, (list, tuple)) and len(tilt_range) >= 2:
        tilt_abs = int(round(max(abs(float(tilt_range[0])), abs(float(tilt_range[1])))))
    variant = meta.get("variant")
    if tilt_abs is None and isinstance(variant, str) and variant.startswith("sm"):
        try:
            tilt_abs = int(variant[2:])
        except ValueError:
            pass

    step = meta.get("angular_step_deg")
    if step is None:
        inferred = infer_condition_from_name(run_dir.name)
        if inferred:
            if tilt_abs is None:
                tilt_abs = inferred[0]
            step = inferred[1]
    if tilt_abs is None:
        inferred = infer_condition_from_name(run_dir.name)
        if inferred:
            tilt_abs = inferred[0]
            step = step if step is not None else inferred[1]
    if tilt_abs is None:
        tilt_abs = 70
    if step is None:
        step = 1.0

    wedge = meta.get("missing_wedge_deg")
    if wedge is None:
        wedge = 180.0 - 2.0 * float(tilt_abs)

    cid = condition_id_from_parts(int(tilt_abs), float(step))
    return {
        "id": cid,
        "label": f"sm{int(tilt_abs)} · ±{int(tilt_abs)}° · {step:g}° step",
        "tilt_abs": int(tilt_abs),
        "tilt_min": -float(tilt_abs),
        "tilt_max": float(tilt_abs),
        "angular_step_deg": float(step),
        "missing_wedge_deg": float(wedge),
        "legacy_hint": legacy,
    }


def _has_protocol(metrics: Dict[str, Any]) -> bool:
    return any(k in PROTOCOL_KEYS for k in metrics)


def collect_nested_or_flat(run_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Support flat ``run/algo/`` and batch ``run/data/dataset/algo/`` layouts."""
    data_root = run_dir / "data"
    if data_root.is_dir():
        rows: Dict[str, Dict[str, Any]] = {}
        for ds_dir in sorted(data_root.iterdir()):
            if not ds_dir.is_dir():
                continue
            nested = _collect_algorithms(ds_dir)
            for name, blob in nested.items():
                key = f"{ds_dir.name}/{name}"
                rows[key] = blob
                rows[key]["_dataset_key"] = ds_dir.name
        if rows:
            return rows
    return _collect_algorithms(run_dir)


def build_cohorts(
    run_dirs: List[Path],
    datasets_root: Optional[Path] = None,
    protocol_version: str = "frozen-v1",
) -> Dict[str, Any]:
    conditions: Dict[str, Dict[str, Any]] = {}
    rows_out: List[Dict[str, Any]] = []
    runs_meta: List[Dict[str, Any]] = []

    for run_dir in run_dirs:
        run_dir = run_dir.resolve()
        if not run_dir.is_dir():
            raise FileNotFoundError(f"Not a directory: {run_dir}")
        collected = collect_nested_or_flat(run_dir)
        runs_meta.append(
            {
                "path": str(run_dir),
                "name": run_dir.name,
                "n_algorithms": len(collected),
            }
        )
        for name, blob in collected.items():
            track = _assign_track(name.split("/")[-1])
            protocol = dict(blob.get("protocol") or {})
            legacy = dict(blob.get("legacy") or {})
            # Prefer protocol keys; keep legacy for diagnostics. Never invent scores.
            metrics: Dict[str, Any] = {}
            metrics.update(legacy)
            metrics.update(protocol)
            metrics.pop("protocol_fsc_curve", None)

            ds_key = blob.get("_dataset_key")
            if ds_key:
                cond_src = infer_condition_from_name(ds_key)
                if cond_src:
                    tilt_abs, step = cond_src
                    cid = condition_id_from_parts(tilt_abs, step)
                    cond = {
                        "id": cid,
                        "label": f"sm{tilt_abs} · ±{tilt_abs}° · {step:g}° step",
                        "tilt_abs": tilt_abs,
                        "tilt_min": -float(tilt_abs),
                        "tilt_max": float(tilt_abs),
                        "angular_step_deg": float(step),
                        "missing_wedge_deg": 180.0 - 2.0 * float(tilt_abs),
                    }
                else:
                    cond = infer_condition_for_run(run_dir, blob)
            else:
                cond = infer_condition_for_run(run_dir, blob)

            cid = cond["id"]
            audited = _has_protocol(protocol)
            prev = conditions.get(cid)
            conditions[cid] = {
                "id": cid,
                "label": cond["label"],
                "tilt_abs": cond["tilt_abs"],
                "tilt_min": cond["tilt_min"],
                "tilt_max": cond["tilt_max"],
                "angular_step_deg": cond["angular_step_deg"],
                "missing_wedge_deg": cond["missing_wedge_deg"],
                "audited": bool((prev or {}).get("audited")) or audited,
            }

            execution = dict(blob.get("execution") or {})
            runtime = execution.get("runtime_seconds") or execution.get("wall_time_s")
            status = "audited" if audited else "legacy"
            if not metrics and not execution:
                status = "failed"

            algo_name = _canonical_algo_name(name.split("/")[-1])
            dataset_id = dataset_id_from_tilt(int(cond["tilt_abs"]))
            conditions[cid]["dataset"] = dataset_id
            rows_out.append(
                {
                    "run": run_dir.name,
                    "algorithm": algo_name,
                    "method_group": method_group_for_algorithm(algo_name, track),
                    "dataset": dataset_id,
                    "condition_id": cid,
                    "angular_step_deg": float(cond["angular_step_deg"]),
                    "tilt_abs": int(cond["tilt_abs"]),
                    "dataset_key": ds_key or execution.get("dataset_key"),
                    "status": status,
                    "metrics": metrics,
                    "execution": {
                        "runtime_seconds": runtime,
                        "docker_image": execution.get("docker_image")
                        or execution.get("image"),
                        "full_volume": execution.get("full_volume"),
                    },
                    "has_protocol": audited,
                    "_n_metrics": len(metrics),
                }
            )

    # Deduplicate: keep best row per (condition, algorithm). All methods share lists.
    ranked: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in rows_out:
        key = (row["condition_id"], row["algorithm"])
        prev = ranked.get(key)
        if prev is None or _row_better(row, prev):
            ranked[key] = row
    final_rows = list(ranked.values())
    for row in final_rows:
        row.pop("has_protocol", None)
        row.pop("_n_metrics", None)

    datasets = load_dataset_cards(datasets_root) if datasets_root else []
    for card in datasets:
        fam = sample_family_id(str(card.get("id") or ""), str(card.get("path") or ""))
        card["sample_family"] = fam
        # SM_* ids are condition labels for the aligned_model phantom only.
        if fam == "aligned_model" and card.get("tilt_max") is not None:
            card["dataset"] = dataset_id_from_tilt(int(abs(float(card["tilt_max"]))))
        elif card.get("dataset_id"):
            card["dataset"] = card["dataset_id"]
        else:
            card.setdefault("dataset", fam)

    profiles = build_dataset_profiles(
        datasets_root if datasets_root and "simulated" in str(datasets_root)
        else (_REPO / "data" / "datasets" / "simulated")
    )
    sample_families = build_sample_families(datasets, profiles)

    # Leaderboard dataset menu entries derived from conditions + profiles.
    dataset_menu: Dict[str, Dict[str, Any]] = {}
    for cond in conditions.values():
        ds = cond.get("dataset") or dataset_id_from_tilt(int(cond["tilt_abs"]))
        prev = dataset_menu.get(ds)
        dataset_menu[ds] = {
            "id": ds,
            "tilt_abs": cond["tilt_abs"],
            "label": ds,
            "audited": bool((prev or {}).get("audited")) or bool(cond.get("audited")),
        }
    for ds_id, prof in profiles.items():
        if ds_id not in dataset_menu:
            dataset_menu[ds_id] = {
                "id": ds_id,
                "tilt_abs": int(abs(float(prof.get("tilt_max") or 0))),
                "label": ds_id,
                "audited": False,
            }

    return {
        "protocol_version": protocol_version,
        "tasks": list(TASKS),
        "primary_by_task": PRIMARY_BY_TASK,
        "runs": runs_meta,
        "dataset_menu": sorted(
            dataset_menu.values(),
            key=lambda d: -int(d["tilt_abs"]),
        ),
        "dataset_profiles": profiles,
        "sample_families": sample_families,
        "conditions": sorted(
            conditions.values(),
            key=lambda c: (-c["tilt_abs"], c["angular_step_deg"], c["id"]),
        ),
        "datasets": datasets,
        "rows": sorted(
            final_rows,
            key=lambda r: (r["dataset"], r["angular_step_deg"], r["algorithm"]),
        ),
        # Explicit: no overall_score field by design.
    }


def _tilt_angle_stats(angles_path: Path) -> Optional[Dict[str, Any]]:
    if not angles_path.is_file():
        return None
    vals: List[float] = []
    for line in angles_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        try:
            vals.append(float(s.split()[0]))
        except ValueError:
            continue
    if not vals:
        return None
    diffs = [abs(vals[i + 1] - vals[i]) for i in range(len(vals) - 1)]
    median_step = float(sorted(diffs)[len(diffs) // 2]) if diffs else None
    return {
        "count": len(vals),
        "min": float(min(vals)),
        "max": float(max(vals)),
        "median_step_deg": median_step,
        "mean_step_deg": float(sum(diffs) / len(diffs)) if diffs else None,
    }


def _load_gt_analysis_slim(path: Path) -> Optional[Dict[str, Any]]:
    """Keep website-sized summary from gt_*_analysis.json."""
    if not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    intensity = raw.get("intensity") or {}
    morphology = raw.get("morphology") or {}
    geom = raw.get("geometry_anisotropy") or {}
    edge = raw.get("edge") or {}
    prepared = raw.get("prepared_gt") or raw.get("source_gt") or {}
    # Drop huge arrays from hist if present — keep for sparkline (≤64 bins OK).
    hist_counts = intensity.get("hist_counts")
    hist_edges = intensity.get("hist_edges")
    if isinstance(hist_counts, list) and len(hist_counts) > 64:
        hist_counts = hist_counts[:64]
        hist_edges = (hist_edges or [])[:65]
    return {
        "source": str(path.relative_to(_REPO)) if path.is_relative_to(_REPO) else str(path),
        "shape": prepared.get("shape"),
        "dtype": prepared.get("dtype"),
        "nbytes_mb": prepared.get("nbytes_mb"),
        "intensity": {
            k: intensity.get(k)
            for k in (
                "min",
                "max",
                "mean",
                "std",
                "median",
                "p01",
                "p99",
                "n_unique",
                "is_near_binary",
                "zero_frac",
                "nnz",
            )
            if k in intensity
        }
        | (
            {"hist_counts": hist_counts, "hist_edges": hist_edges}
            if hist_counts is not None
            else {}
        ),
        "morphology": {
            k: morphology.get(k)
            for k in (
                "threshold",
                "solid_voxels",
                "solid_fraction_global_incl_background",
                "porosity_global_incl_background",
                "solid_fraction_in_sphere",
                "porosity_in_sphere",
                "n_solid_components",
                "n_pore_components_in_sphere",
                "mean_pore_radius_edt",
                "mean_wall_thickness_edt",
            )
            if k in morphology
        },
        "geometry": {
            k: geom.get(k)
            for k in ("elongation_sqrt_lmax_lmin", "axis_std")
            if k in geom
        },
        "edge": {
            k: edge.get(k)
            for k in ("mean_grad_on_surface", "edge_rise_10_90_px", "contrast")
            if k in edge
        },
        "figure": "docs/figures/gt_sm70_analysis.png"
        if (_REPO / "docs/figures/gt_sm70_analysis.png").is_file()
        else None,
    }


def build_dataset_profiles(
    datasets_root: Optional[Path],
    analysis_json: Optional[Path] = None,
) -> Dict[str, Dict[str, Any]]:
    """Profiles keyed by public id (SM_70). Shared GT analysis attached when present."""
    profiles: Dict[str, Dict[str, Any]] = {}
    if datasets_root is None or not datasets_root.is_dir():
        return profiles

    gt_stats = _load_gt_analysis_slim(
        analysis_json
        or (_REPO / "docs" / "figures" / "gt_sm70_analysis.json")
    )

    for meta_path in sorted(datasets_root.glob("**/metadata.yaml")):
        meta = _load_yaml_simple(meta_path)
        name = meta.get("name") or meta_path.parent.name
        if "test_dataset" in str(name):
            continue
        tilt = meta.get("tilt_range")
        tilt_min = tilt_max = None
        if isinstance(tilt, list) and len(tilt) >= 2:
            tilt_min, tilt_max = float(tilt[0]), float(tilt[1])
        if tilt_max is None:
            continue
        ds_id = dataset_id_from_tilt(int(abs(tilt_max)))
        wedge = meta.get("missing_wedge_deg")
        if wedge is None:
            wedge = 180.0 - 2.0 * abs(tilt_max)
        angles = _tilt_angle_stats(meta_path.parent / "raw" / "tilt_angles.txt")
        step = meta.get("angular_step_deg") or meta.get("angular_step_deg_median")
        if step is None and angles and angles.get("median_step_deg") is not None:
            step = angles["median_step_deg"]

        # Prefer the native 1° profile when multiple folders map to same SM_* .
        prev = profiles.get(ds_id)
        candidate = {
            "id": ds_id,
            "name": name,
            "folder": str(meta_path.parent.relative_to(_REPO))
            if meta_path.parent.is_relative_to(_REPO)
            else str(meta_path.parent),
            "type": meta.get("type", "simulated"),
            "has_ground_truth": bool(meta.get("has_ground_truth")),
            "tilt_min": tilt_min,
            "tilt_max": tilt_max,
            "missing_wedge_deg": float(wedge),
            "angular_step_deg": float(step) if step is not None else None,
            "num_projections": meta.get("num_projections")
            or (angles or {}).get("count"),
            "projection_shape": meta.get("projection_shape"),
            "tilt_angles": angles,
            "gt_stats": gt_stats,
            "note": (
                "GT intensity/morphology from aligned_model SM70 analysis; "
                "same phantom family across SM_* tilt crops."
                if gt_stats
                else None
            ),
        }
        if prev is None:
            profiles[ds_id] = candidate
            continue
        # Keep the entry with step closest to 1° as the canonical SM_* card.
        prev_step = prev.get("angular_step_deg") or 99
        cand_step = candidate.get("angular_step_deg") or 99
        if abs(cand_step - 1.0) < abs(float(prev_step) - 1.0):
            profiles[ds_id] = candidate
    return profiles


def sample_family_id(name: str, path: str = "") -> str:
    """Group tilt crops / sparse variants under one sample id."""
    raw = f"{name} {path}".lower().replace("-", "_")
    if "aligned_model" in raw or "/sm" in raw or "model.tif" in raw:
        return "aligned_model"
    if "ceo2" in raw:
        return "ceo2_s5"
    if "resire_vesicle" in raw or "resire vesicle" in raw:
        return "resire_vesicle"
    if "aragonite" in raw or "resire_coral" in raw or "resire_aragonite" in raw:
        return "resire_aragonite_coral"
    if "ta_thinfilm" in raw or "ta thin" in raw or "resire_ta" in raw:
        return "resire_ta_thinfilm"
    if "walnut" in raw:
        return "walnut"
    if "fept" in raw:
        return "fept_nanoparticle"
    slug = re.sub(r"[^a-z0-9]+", "_", (name or path).lower()).strip("_")
    return slug or "unknown"


SAMPLE_FAMILY_META: Dict[str, Dict[str, Any]] = {
    "aligned_model": {
        "title": "Aligned model phantom",
        "blurb": (
            "One porous near-binary phantom with known ground truth. "
            "The same volume is forward-projected under limited tilt ranges "
            "(missing wedge) and coarser angular steps (sparse view). "
            "Leaderboard labels SM_80…SM_40 name those conditions, not different samples."
        ),
        "preview": "assets/samples/aligned_model_volume.png?v=20261121n",
        "preview_caption": "GT mid-plane",
        "analysis_figure": "../figures/gt_sm70_analysis.png",
    },
    "ceo2_s5": {
        "title": "CeO₂ S5",
        "blurb": (
            "Experimental CeO₂ nanoparticle tilt series (no ground truth). "
            "Used for methods that do not require a GT volume."
        ),
        "preview": "assets/samples/ceo2_s5_volume.png?v=20261121n",
        "preview_caption": "Volume preview",
        "analysis_figure": None,
    },
    "resire_vesicle": {
        "title": "Vesicle (simulated)",
        "blurb": (
            "RESIRE SciRep 2023 simulated biological vesicle with ground truth "
            "(64³, 41 projections, ±70° / 3.5°). Suitable for general and "
            "missing-wedge protocol tracks with GT metrics."
        ),
        "preview": "assets/samples/resire_vesicle_volume.png?v=20261122b",
        "preview_caption": "GT mid-plane",
        "analysis_figure": None,
    },
    "resire_aragonite_coral": {
        "title": "Aragonite coral",
        "blurb": (
            "Experimental ADF-STEM tilt series of an aragonite coral biomineral "
            "(69 projections, −60°…+76°, pre-aligned, no GT). "
            "Fits the experimental / no-GT reconstruction track "
            "(reprojection / consistency metrics)."
        ),
        "preview": "assets/samples/resire_aragonite_coral.png?v=20261122b",
        "preview_caption": "0° projection",
        "analysis_figure": None,
    },
    "resire_ta_thinfilm": {
        "title": "Amorphous Ta thin film",
        "blurb": (
            "Experimental ADF-STEM tilt series of an extended amorphous Ta film "
            "(51 projections, pre-aligned/cropped, no GT). "
            "Useful for missing-wedge behaviour on extended objects "
            "under the experimental / no-GT track."
        ),
        "preview": "assets/samples/resire_ta_thinfilm.png?v=20261122b",
        "preview_caption": "Near-0° projection",
        "analysis_figure": None,
    },
}


def build_sample_families(
    cards: List[Dict[str, Any]],
    profiles: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """One card per physical sample; conditions listed underneath."""
    profiles = profiles or {}
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for card in cards:
        fam = card.get("sample_family") or sample_family_id(
            str(card.get("id") or ""), str(card.get("path") or "")
        )
        buckets.setdefault(fam, []).append(card)

    families: List[Dict[str, Any]] = []
    for fam_id, members in sorted(buckets.items(), key=lambda kv: kv[0]):
        meta = dict(SAMPLE_FAMILY_META.get(fam_id, {}))
        typ = members[0].get("type", "simulated")
        has_gt = any(bool(m.get("has_ground_truth")) for m in members)
        # Prefer GT stats from SM_70 profile for aligned_model.
        gt = None
        if fam_id == "aligned_model":
            gt = (profiles.get("SM_70") or {}).get("gt_stats")
        title = meta.get("title") or members[0].get("id") or fam_id
        families.append(
            {
                "id": fam_id,
                "title": title,
                "type": typ,
                "has_ground_truth": has_gt,
                "blurb": meta.get("blurb")
                or f"Sample family with {len(members)} registered condition(s).",
                "preview": meta.get("preview"),
                "preview_caption": meta.get("preview_caption") or (
                    "Volume preview" if meta.get("preview") else None
                ),
                "analysis_figure": meta.get("analysis_figure"),
                "gt_stats": gt,
                "conditions": sorted(
                    members,
                    key=lambda m: (
                        -abs(float(m["tilt_max"])) if m.get("tilt_max") is not None else 0,
                        float(m.get("angular_step_deg") or 99),
                        str(m.get("id") or ""),
                    ),
                ),
            }
        )
    # Simulated families first, then experimental.
    families.sort(key=lambda f: (0 if f.get("type") == "simulated" else 1, f["id"]))
    return families


def load_dataset_cards(root: Path) -> List[Dict[str, Any]]:
    root = root.resolve()
    cards: List[Dict[str, Any]] = []
    if not root.is_dir():
        return cards
    for meta_path in sorted(root.glob("**/metadata.yaml")):
        meta = _load_yaml_simple(meta_path)
        name = meta.get("name") or meta_path.parent.name
        folder = str(meta_path.parent)
        if "test_dataset" in str(name).lower() or "test_dataset" in folder.lower():
            continue
        tilt = meta.get("tilt_range")
        tilt_min = tilt_max = None
        if isinstance(tilt, list) and len(tilt) >= 2:
            tilt_min, tilt_max = float(tilt[0]), float(tilt[1])
        wedge = meta.get("missing_wedge_deg")
        if wedge is None and tilt_max is not None:
            wedge = 180.0 - 2.0 * abs(tilt_max)
        try:
            rel = str(meta_path.parent.relative_to(_REPO))
        except ValueError:
            rel = str(meta_path.parent)
        cards.append(
            {
                "id": name,
                "dataset_id": meta.get("dataset_id"),
                "path": rel,
                "type": meta.get("type", "simulated"),
                "tilt_min": tilt_min,
                "tilt_max": tilt_max,
                "missing_wedge_deg": wedge,
                "angular_step_deg": meta.get("angular_step_deg")
                or meta.get("angular_step_deg_median"),
                "num_projections": meta.get("num_projections"),
                "has_ground_truth": bool(meta.get("has_ground_truth")),
                "sample_family": sample_family_id(str(name), rel),
            }
        )
    return cards


def best_protocol_only(
    values: Dict[str, float], metric: str
) -> set:
    """Public helper for tests: never mark best on non-protocol keys."""
    if metric not in PROTOCOL_KEYS:
        return set()
    return _best_for_metric(values, metric)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-dir",
        action="append",
        type=Path,
        required=True,
        help="Result directory (repeatable)",
    )
    parser.add_argument(
        "--datasets-root",
        type=Path,
        default=_REPO / "data" / "datasets",
        help="Root to scan for metadata.yaml (simulated + experimental)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_REPO / "docs" / "benchmark-site" / "data" / "cohorts.json",
    )
    parser.add_argument("--protocol-version", default="frozen-v1")
    args = parser.parse_args()

    cohorts = _json_safe(
        build_cohorts(
            list(args.run_dir),
            datasets_root=args.datasets_root,
            protocol_version=args.protocol_version,
        )
    )
    out = args.output.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(cohorts, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    n_aud = sum(1 for r in cohorts["rows"] if r.get("status") == "audited")
    print(
        f"[ok] wrote {out} · {len(cohorts['rows'])} rows "
        f"({n_aud} audited) · {len(cohorts['conditions'])} conditions",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
