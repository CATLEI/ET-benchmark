"""Tests for docs/benchmark-site cohorts export."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_SCRIPT = (
    Path(__file__).resolve().parents[2] / "scripts" / "export_leaderboard_site.py"
)
_spec = importlib.util.spec_from_file_location("export_leaderboard_site", _SCRIPT)
assert _spec and _spec.loader
export_mod = importlib.util.module_from_spec(_spec)
sys.modules["export_leaderboard_site"] = export_mod
_spec.loader.exec_module(export_mod)


def _write_algo(
    run: Path,
    name: str,
    metrics: dict,
    *,
    protocol: dict | None = None,
    execution: dict | None = None,
) -> None:
    algo = run / name
    algo.mkdir(parents=True, exist_ok=True)
    (algo / "evaluation.json").write_text(
        json.dumps({"metrics": metrics, "algorithm_name": name}),
        encoding="utf-8",
    )
    if execution is not None:
        (algo / "execution_metadata.json").write_text(
            json.dumps(execution),
            encoding="utf-8",
        )
    if protocol is not None:
        proto_path = run / "protocol_metrics.json"
        blob = {"algorithms": {}}
        if proto_path.is_file():
            blob = json.loads(proto_path.read_text(encoding="utf-8"))
        blob.setdefault("algorithms", {})[name] = protocol
        proto_path.write_text(json.dumps(blob), encoding="utf-8")


def test_export_assigns_tracks_and_keeps_failures(tmp_path: Path):
    run = tmp_path / "aligned-model-sm70"
    run.mkdir()
    _write_algo(
        run,
        "wbp",
        {"psnr": 14.0, "ssim": 0.88},
        execution={
            "runtime_seconds": 12.5,
            "docker_image": "registry.example/wbp:1",
            "dataset_metadata": {
                "variant": "sm70",
                "tilt_range": [-70, 70],
                "missing_wedge_deg": 40,
            },
        },
    )
    _write_algo(
        run,
        "isonet",
        {"psnr": 10.0},
        execution={"runtime_seconds": 100.0},
    )
    # Failed / empty algorithm folder with only a marker log — still a dir without metrics
    failed = run / "genfire"
    failed.mkdir()
    (failed / "algorithm.log").write_text("boom\n", encoding="utf-8")

    cohorts = export_mod.build_cohorts([run], datasets_root=None)
    assert "overall_score" not in cohorts
    assert cohorts["tasks"] == ["general", "missing wedge", "sparse view"]
    algs = {r["algorithm"]: r for r in cohorts["rows"]}
    assert algs["wbp"]["method_group"] == "classical"
    assert algs["isonet"]["method_group"] == "self-supervised"
    assert algs["wbp"]["dataset"] == "SM_70"
    assert "category" not in algs["wbp"]
    assert algs["wbp"]["condition_id"] == "sm70_step1"
    assert algs["wbp"]["status"] == "legacy"
    assert all(r.get("status") != "audited" for r in cohorts["rows"])


def test_protocol_absent_does_not_mark_best():
    values = {"wbp": 0.9, "sirt": 0.8}
    assert export_mod.best_protocol_only(values, "ssim") == set()
    assert export_mod.best_protocol_only(values, "psnr") == set()
    winners = export_mod.best_protocol_only(
        {"wbp": 0.91, "sirt": 0.88}, "protocol_affine_ssim"
    )
    assert winners == {"wbp"}


def test_audited_when_protocol_keys_present(tmp_path: Path):
    run = tmp_path / "aligned-model-sm70"
    run.mkdir()
    _write_algo(
        run,
        "wbp",
        {"psnr": 14.0, "ssim": 0.88},
        protocol={"protocol_affine_ssim": 0.91, "protocol_affine_cc": 0.93},
        execution={
            "dataset_metadata": {
                "variant": "sm70",
                "tilt_range": [-70, 70],
                "missing_wedge_deg": 40,
                "angular_step_deg": 1,
            }
        },
    )
    _write_algo(
        run,
        "astra-sirt",
        {"psnr": 10.0, "ssim": 0.57},
        protocol={"protocol_affine_ssim": 0.70, "protocol_affine_cc": 0.75},
    )
    cohorts = export_mod.build_cohorts([run])
    cond = next(c for c in cohorts["conditions"] if c["id"] == "sm70_step1")
    assert cond["audited"] is True
    rows = [r for r in cohorts["rows"] if r["condition_id"] == "sm70_step1"]
    assert all(r["status"] == "audited" for r in rows)
    assert "protocol_affine_ssim" in rows[0]["metrics"]


def test_condition_id_helpers():
    assert export_mod.condition_id_from_parts(70, 1) == "sm70_step1"
    assert export_mod.condition_id_from_parts(40, 2) == "sm40_step2"
    assert export_mod.infer_condition_from_name("aligned_model_sm70_step2_v1") == (
        70,
        2.0,
    )


def test_resire_sample_family_ids():
    assert (
        export_mod.sample_family_id(
            "RESIRE Vesicle (simulated)",
            "data/datasets/simulated/resire_vesicle_v1",
        )
        == "resire_vesicle"
    )
    assert (
        export_mod.sample_family_id(
            "RESIRE Aragonite Coral",
            "data/datasets/experimental/public/resire_aragonite_coral_v1",
        )
        == "resire_aragonite_coral"
    )
    assert (
        export_mod.sample_family_id(
            "RESIRE Amorphous Ta Thin Film",
            "data/datasets/experimental/public/resire_ta_thinfilm_v1",
        )
        == "resire_ta_thinfilm"
    )
    meta = export_mod.SAMPLE_FAMILY_META
    assert "resire_vesicle" in meta
    assert "resire_aragonite_coral" in meta
    assert "resire_ta_thinfilm" in meta


def test_method_group_labels():
    assert (
        export_mod.method_group_for_algorithm("tvm", "A_projection_to_volume")
        == "TV regularized iterative"
    )
    assert (
        export_mod.method_group_for_algorithm("dart", "oracle_prior") == "grey prior"
    )
    assert (
        export_mod.method_group_for_algorithm("tvr-dart", "oracle_prior")
        == "grey prior"
    )
    assert (
        export_mod.method_group_for_algorithm("wbp", "A_projection_to_volume")
        == "classical"
    )
    assert (
        export_mod.method_group_for_algorithm("isonet", "B_post_recon_wedge_fill")
        == "self-supervised"
    )


def test_build_dataset_profiles_from_metadata(tmp_path: Path):
    ds = tmp_path / "simulated" / "aligned_model_sm70_v1"
    (ds / "raw").mkdir(parents=True)
    (ds / "metadata.yaml").write_text(
        "\n".join(
            [
                "name: aligned_model_sm70",
                "type: simulated",
                "has_ground_truth: true",
                "tilt_range: [-70, 70]",
                "missing_wedge_deg: 40",
                "angular_step_deg: 1",
                "num_projections: 3",
                "projection_shape: [3, 8, 8]",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (ds / "raw" / "tilt_angles.txt").write_text("-70\n0\n70\n", encoding="utf-8")
    analysis = tmp_path / "gt.json"
    analysis.write_text(
        json.dumps(
            {
                "prepared_gt": {"shape": [8, 8, 8], "dtype": "float32"},
                "intensity": {
                    "min": 0.0,
                    "max": 1.0,
                    "mean": 0.2,
                    "std": 0.4,
                    "zero_frac": 0.8,
                    "is_near_binary": True,
                    "n_unique": 2,
                },
                "morphology": {"porosity_in_sphere": 0.5},
                "geometry_anisotropy": {"elongation_sqrt_lmax_lmin": 1.1},
            }
        ),
        encoding="utf-8",
    )
    profiles = export_mod.build_dataset_profiles(
        tmp_path / "simulated", analysis_json=analysis
    )
    assert "SM_70" in profiles
    card = profiles["SM_70"]
    assert card["tilt_min"] == -70.0
    assert card["missing_wedge_deg"] == 40.0
    assert card["tilt_angles"]["count"] == 3
    assert card["gt_stats"]["shape"] == [8, 8, 8]
    assert card["gt_stats"]["intensity"]["mean"] == 0.2
