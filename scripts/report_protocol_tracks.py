#!/usr/bin/env python3
"""Build a Track A/B/C/oracle HTML report from an existing run (sidecar only).

Does not modify workflow ``comparison_report.html``. Reads:

- ``evaluation.json`` / ``comparison_summary.json`` for legacy metrics
- ``protocol_metrics.json`` when present (from ``reeval_protocol_metrics.py``)
- ``execution_metadata.json`` for runtime / image tags when available

Example::

    python scripts/report_protocol_tracks.py \\
      --run-dir results/aligned-model-sm70 \\
      --output results/aligned-model-sm70/protocol_tracks_report.html
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

TRACKS: Dict[str, Set[str]] = {
    "A_projection_to_volume": {
        "wbp",
        "sirt",
        "astra_fbp",
        "astra_sirt",
        "tigre_sirt",
        "tigre",
        "genfire",
        "tvm",
        "astra",
    },
    "B_post_recon_wedge_fill": {"isonet"},
    "C_self_supervised": {"deepdewedge", "wucon"},
    "oracle_prior": {"dart", "tvr_dart"},
}

# Direction for “best” highlighting. Closest-to-one handled separately.
HIGHER_BETTER = {
    "psnr",
    "ssim",
    "r2",
    "dice",
    "protocol_affine_ssim",
    "protocol_affine_cc",
    "protocol_wedge_in_cc",
    "protocol_wedge_out_cc",
}
LOWER_BETTER = {
    "mse",
    "fsc_resolution_px",
    "edge_rise_px",
    "hausdorff95_px",
    "porosity_abs_error",
    "psd_wasserstein_px",
    "ssa_rel_error",
    "void_cc_fraction_abs_error",
    "protocol_fsc_res_0p5_px",
    "protocol_fsc_res_0p143_px",
}
CLOSER_TO_ONE = {"elongation"}
NON_DISCRIMINATIVE_KEYS = {"percolation_mismatch"}

PRIMARY_BY_TRACK = {
    "A_projection_to_volume": [
        "protocol_affine_ssim",
        "protocol_affine_cc",
        "ssim",
        "psnr",
        "dice",
    ],
    "B_post_recon_wedge_fill": [
        "protocol_wedge_out_cc",
        "protocol_wedge_in_cc",
        "protocol_affine_cc",
    ],
    "C_self_supervised": [
        "protocol_wedge_out_cc",
        "protocol_wedge_in_cc",
        "protocol_affine_cc",
    ],
    "oracle_prior": [
        "protocol_affine_ssim",
        "dice",
        "psnr",
    ],
}


def _base_name(label: str) -> str:
    return label.split("/")[-1].replace("-", "_").lower()


def _assign_track(name: str) -> str:
    base = _base_name(name)
    for track, members in TRACKS.items():
        if base in members or any(base.startswith(m) for m in members):
            return track
    return "unassigned"


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _collect_algorithms(run_dir: Path) -> Dict[str, Dict[str, Any]]:
    rows: Dict[str, Dict[str, Any]] = {}

    summary = _load_json(run_dir / "comparison_summary.json") or {}
    metrics_map = summary.get("metrics") or {}
    for name, mets in metrics_map.items():
        rows.setdefault(name, {})["legacy"] = dict(mets or {})

    # Flat evaluation.json
    for child in sorted(run_dir.iterdir()):
        if not child.is_dir():
            continue
        ev = _load_json(child / "evaluation.json")
        if ev and "metrics" in ev:
            rows.setdefault(child.name, {})["legacy"] = dict(ev["metrics"])
        meta = _load_json(child / "execution_metadata.json")
        if meta:
            rows.setdefault(child.name, {})["execution"] = meta

    proto = _load_json(run_dir / "protocol_metrics.json") or {}
    for name, mets in (proto.get("algorithms") or {}).items():
        # Drop curve from HTML tables
        slim = {
            k: v
            for k, v in (mets or {}).items()
            if k != "protocol_fsc_curve" and not isinstance(v, dict)
        }
        rows.setdefault(name, {})["protocol"] = slim

    return rows


def _best_for_metric(
    values: Dict[str, float],
    metric: str,
) -> Set[str]:
    if metric in NON_DISCRIMINATIVE_KEYS:
        uniq = {round(v, 12) for v in values.values()}
        if len(uniq) <= 1:
            return set()
    finite = {k: v for k, v in values.items() if isinstance(v, (int, float))}
    if not finite:
        return set()
    if metric in HIGHER_BETTER:
        best = max(finite.values())
        return {k for k, v in finite.items() if abs(v - best) < 1e-12}
    if metric in LOWER_BETTER:
        best = min(finite.values())
        return {k for k, v in finite.items() if abs(v - best) < 1e-12}
    if metric in CLOSER_TO_ONE:
        best = min(finite.values(), key=lambda x: abs(x - 1.0))
        return {k for k, v in finite.items() if abs(v - best) < 1e-12}
    return set()


def _fmt(v: Any) -> str:
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


def _render_table(
    track: str,
    members: List[str],
    rows: Dict[str, Dict[str, Any]],
) -> str:
    preferred = PRIMARY_BY_TRACK.get(track, [])
    # Union of metric keys present
    keys: List[str] = []
    for name in members:
        blob = rows.get(name, {})
        for section in ("protocol", "legacy"):
            for k in (blob.get(section) or {}):
                if k in NON_DISCRIMINATIVE_KEYS:
                    # show but mark later
                    pass
                if k not in keys and k != "protocol_fsc_curve":
                    keys.append(k)
    # Prefer primary order first
    ordered = [k for k in preferred if k in keys]
    ordered += [k for k in keys if k not in ordered]
    if not ordered:
        return f"<p>No metrics for track {track}.</p>"

    # Precompute best sets
    best_map: Dict[str, Set[str]] = {}
    for metric in ordered:
        col = {}
        for name in members:
            blob = rows.get(name, {})
            val = (blob.get("protocol") or {}).get(metric)
            if val is None:
                val = (blob.get("legacy") or {}).get(metric)
            if isinstance(val, (int, float)):
                col[name] = float(val)
        best_map[metric] = _best_for_metric(col, metric)

    parts = [
        f"<h2>{track}</h2>",
        "<table><tr><th>Algorithm</th>",
    ]
    for m in ordered:
        note = ""
        if m in NON_DISCRIMINATIVE_KEYS:
            note = " <span class='nd'>(non-discriminative if all equal)</span>"
        parts.append(f"<th>{m}{note}</th>")
    parts.append("<th>runtime_s</th><th>image</th><th>full_volume</th></tr>")

    for name in members:
        blob = rows.get(name, {})
        parts.append(f"<tr><td><strong>{name}</strong></td>")
        for m in ordered:
            val = (blob.get("protocol") or {}).get(m)
            if val is None:
                val = (blob.get("legacy") or {}).get(m)
            cls = "best" if name in best_map.get(m, set()) else ""
            if m in NON_DISCRIMINATIVE_KEYS and not best_map.get(m):
                cls = "nd"
            cell = _fmt(val) if val is not None else "—"
            tag = " <span class='tag'>best</span>" if cls == "best" else ""
            parts.append(f"<td class='{cls}'>{cell}{tag}</td>")
        execution_meta = blob.get("execution") or {}
        runtime = (
            execution_meta.get("runtime_seconds")
            or execution_meta.get("wall_time_s")
            or "—"
        )
        image = (
            execution_meta.get("docker_image")
            or execution_meta.get("image")
            or "—"
        )
        full_vol = execution_meta.get("full_volume")
        if full_vol is None and name.lower().startswith("wucon"):
            full_vol = "check wucon_recon_subset"
        parts.append(
            f"<td>{_fmt(runtime)}</td><td>{image}</td><td>{full_vol}</td></tr>"
        )
    parts.append("</table>")
    return "\n".join(parts)


def render_html(run_dir: Path, rows: Dict[str, Dict[str, Any]]) -> str:
    by_track: Dict[str, List[str]] = {t: [] for t in TRACKS}
    by_track["unassigned"] = []
    for name in sorted(rows):
        by_track.setdefault(_assign_track(name), []).append(name)

    sections = []
    for track in list(TRACKS) + ["unassigned"]:
        members = by_track.get(track) or []
        if not members:
            sections.append(f"<h2>{track}</h2><p>No algorithms in this run.</p>")
            continue
        sections.append(_render_table(track, members, rows))

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>Protocol tracks — {run_dir.name}</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; background: #f5f5f5; }}
.container {{ max-width: 1200px; margin: 0 auto; background: #fff; padding: 24px;
  border-radius: 8px; }}
h1 {{ border-bottom: 3px solid #2f6f4e; padding-bottom: 8px; }}
h2 {{ margin-top: 28px; color: #333; }}
table {{ border-collapse: collapse; width: 100%; font-size: 0.92rem; margin-bottom: 16px; }}
th, td {{ border-bottom: 1px solid #e5e5e5; padding: 8px 10px; text-align: right; }}
th:first-child, td:first-child {{ text-align: left; }}
th {{ background: #2f6f4e; color: #fff; }}
td.best {{ background: #e8f6ee; font-weight: 700; color: #1b7a3d; }}
td.nd {{ color: #888; }}
.tag {{ display: inline-block; margin-left: 4px; padding: 1px 6px; border-radius: 999px;
  background: #1b7a3d; color: #fff; font-size: 0.7rem; }}
.nd {{ color: #888; font-size: 0.75rem; }}
.note {{ background: #f3f7f4; padding: 10px 12px; border-radius: 6px; color: #555; }}
</style></head><body><div class="container">
<h1>Protocol track report — {run_dir.name}</h1>
<p class="note">Sidecar report only. Workflow <code>comparison_report.html</code>
is unchanged. Tracks A/B/C/oracle-prior do not share a single champion.
Primary protocol keys come from <code>protocol_metrics.json</code> when present;
legacy keys are diagnostic. Non-discriminative metrics (all equal) are not tagged best.</p>
{''.join(sections)}
</div></body></html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Default: <run-dir>/protocol_tracks_report.html",
    )
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    if not run_dir.is_dir():
        print(f"Not a directory: {run_dir}", file=sys.stderr)
        return 1
    rows = _collect_algorithms(run_dir)
    if not rows:
        print(f"No algorithm results under {run_dir}", file=sys.stderr)
        return 1
    html = render_html(run_dir, rows)
    out = (args.output or (run_dir / "protocol_tracks_report.html")).resolve()
    out.write_text(html, encoding="utf-8")
    print(f"[ok] wrote {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
