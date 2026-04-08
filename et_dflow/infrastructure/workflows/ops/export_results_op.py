"""
dflow OP for exporting benchmark results.

Collects step artifacts into a single archive that can be downloaded
to the master node and unpacked into results/<time>/.
"""

import json
import re
import shutil
import tarfile
from pathlib import Path
from typing import List

from dflow.python import OP, OPIO, Parameter, Artifact


def _safe_path_segment(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(name))
    s = s.strip("-") or "x"
    return s[:200]


class ExportResultsOP(OP):
    """Bundle workflow artifacts into a downloadable archive."""

    @classmethod
    def get_input_sign(cls):
        return OPIO({
            "prepared_data": Artifact(str, optional=True),
            "prepared_data_list": Artifact(List[str], optional=True),
            "ground_truth": Artifact(str, optional=True),
            "ground_truth_dataset_keys": Parameter(List[str], optional=True),
            "ground_truth_list": Artifact(List[str], optional=True),
            "dataset_keys": Parameter(List[str], optional=True),
            "export_dataset_keys": Parameter(List[str], optional=True),
            "algorithm_names": Parameter(List[str]),
            "row_labels": Parameter(List[str], optional=True),
            "reconstructions": Artifact(List[str]),
            "reconstruction_npys": Artifact(List[str]),
            "execution_metadata_files": Artifact(List[str], optional=True),
            "metrics_files": Artifact(List[str]),
            "comparison_report": Artifact(str),
            "comparison_json": Artifact(str),
            "visualizations": Artifact(str, optional=True),
            "leaderboard_json": Artifact(str, optional=True),
            "preprocessing_metrics_file": Artifact(str, optional=True),
            "preprocessing_metrics_files": Artifact(List[str], optional=True),
            "preprocessing_metrics_dataset_keys": Parameter(List[str], optional=True),
        })

    @classmethod
    def get_output_sign(cls):
        return OPIO({
            "results_archive": Artifact(str),
            "export_manifest": Artifact(str),
        })

    @OP.exec_sign_check
    def execute(self, op_in: OPIO) -> OPIO:
        bundle_root = Path("/tmp/exported_results")
        bundle_root.mkdir(parents=True, exist_ok=True)

        data_dir = bundle_root / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        prepared_list: List[str] = []
        raw_prepared_list = op_in.get("prepared_data_list")
        if raw_prepared_list:
            prepared_list = [str(p) for p in raw_prepared_list]
        elif op_in.get("prepared_data"):
            prepared_list = [str(op_in["prepared_data"])]
        else:
            raise ValueError("ExportResultsOP requires prepared_data or prepared_data_list")

        dataset_keys: List[str] = op_in.get("dataset_keys") or []
        if not dataset_keys:
            dataset_keys = ["data"] * len(prepared_list)
        if len(dataset_keys) != len(prepared_list):
            raise ValueError("dataset_keys length must match prepared_data_list")

        by_ds_root = data_dir / "by_dataset"
        by_ds_root.mkdir(parents=True, exist_ok=True)
        for dk, prep in zip(dataset_keys, prepared_list):
            seg = _safe_path_segment(dk)
            ddir = by_ds_root / seg
            ddir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(prep), str(ddir / "prepared_data.hspy"))

        gt_keys: List[str] = list(op_in.get("ground_truth_dataset_keys") or [])
        gt_list = op_in.get("ground_truth_list") or []
        if gt_keys and gt_list and len(gt_keys) == len(gt_list):
            for dk, gt_path in zip(gt_keys, gt_list):
                if not gt_path:
                    continue
                seg = _safe_path_segment(dk)
                ddir = by_ds_root / seg
                ddir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(gt_path), str(ddir / "prepared_data_ground_truth.hspy"))
        elif op_in.get("ground_truth") and len(prepared_list) == 1:
            shutil.copy2(str(op_in["ground_truth"]), str(data_dir / "prepared_data_ground_truth.hspy"))

        # Legacy single-tree copy (first prepared) for older consumers
        shutil.copy2(str(prepared_list[0]), str(data_dir / "prepared_data.hspy"))

        algorithm_names = op_in["algorithm_names"]
        row_labels = op_in.get("row_labels") or list(algorithm_names)
        if len(row_labels) != len(algorithm_names):
            row_labels = [
                row_labels[i] if i < len(row_labels) else algorithm_names[i]
                for i in range(len(algorithm_names))
            ]

        reconstructions = op_in["reconstructions"]
        reconstruction_npys = op_in["reconstruction_npys"]
        metrics_files = op_in["metrics_files"]
        execution_metadata_files = op_in.get("execution_metadata_files") or []

        export_dataset_keys: List[str] = op_in.get("export_dataset_keys") or []
        if not export_dataset_keys:
            if len(prepared_list) == 1 and dataset_keys:
                export_dataset_keys = [dataset_keys[0]] * len(algorithm_names)
            elif len(dataset_keys) == len(algorithm_names):
                export_dataset_keys = list(dataset_keys)
            else:
                export_dataset_keys = ["data"] * len(algorithm_names)
        if len(export_dataset_keys) != len(algorithm_names):
            raise ValueError("export_dataset_keys length must match algorithm_names")

        for idx, (
            ds_k,
            alg_name,
            _row_label,
            reconstruction,
            reconstruction_npy,
            metrics_file,
        ) in enumerate(
            zip(
            export_dataset_keys,
            algorithm_names,
            row_labels,
            reconstructions,
            reconstruction_npys,
            metrics_files,
            )
        ):
            rel = Path("by_dataset") / _safe_path_segment(ds_k) / _safe_path_segment(alg_name)
            alg_dir = bundle_root / rel
            alg_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(reconstruction), str(alg_dir / "reconstruction.hspy"))
            shutil.copy2(str(reconstruction_npy), str(alg_dir / "reconstruction.npy"))
            shutil.copy2(str(metrics_file), str(alg_dir / "evaluation.json"))
            if idx < len(execution_metadata_files) and execution_metadata_files[idx]:
                shutil.copy2(str(execution_metadata_files[idx]), str(alg_dir / "execution_metadata.json"))

        comparison_report = Path(op_in["comparison_report"])
        comparison_json = Path(op_in["comparison_json"])
        shutil.copy2(str(comparison_report), str(bundle_root / "comparison_report.html"))
        shutil.copy2(str(comparison_json), str(bundle_root / "comparison_summary.json"))

        leaderboard_src = op_in.get("leaderboard_json")
        if leaderboard_src:
            ldb = bundle_root / "leaderboard"
            ldb.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(leaderboard_src), str(ldb / "suite_leaderboard.json"))
            src_cmp = Path(op_in["comparison_json"]).parent
            lb_dir = src_cmp / "leaderboard"
            if lb_dir.is_dir():
                for child in lb_dir.iterdir():
                    if child.is_file():
                        shutil.copy2(str(child), str(ldb / child.name))
            csv_src = src_cmp / "leaderboard.csv"
            if csv_src.is_file():
                shutil.copy2(str(csv_src), str(bundle_root / "leaderboard.csv"))

        preprocessing_metrics = op_in.get("preprocessing_metrics_file")
        if preprocessing_metrics:
            shutil.copy2(str(preprocessing_metrics), str(bundle_root / "preprocessing_metrics.json"))

        pm_files = op_in.get("preprocessing_metrics_files") or []
        pm_ds_keys = op_in.get("preprocessing_metrics_dataset_keys") or []
        if pm_files:
            pm_root = bundle_root / "preprocessing_metrics"
            pm_root.mkdir(parents=True, exist_ok=True)
            for i, pm in enumerate(pm_files):
                name = f"{i}.json"
                if i < len(pm_ds_keys):
                    name = f"{_safe_path_segment(pm_ds_keys[i])}.json"
                shutil.copy2(str(pm), str(pm_root / name))

        visualizations = op_in.get("visualizations")
        if visualizations:
            viz_path = Path(visualizations)
            if viz_path.is_dir():
                for child in viz_path.iterdir():
                    if child.is_file():
                        shutil.copy2(str(child), str(bundle_root / child.name))
            elif viz_path.is_file():
                shutil.copy2(str(viz_path), str(bundle_root / viz_path.name))

        manifest = {
            "algorithm_names": algorithm_names,
            "row_labels": row_labels,
            "dataset_keys": dataset_keys,
            "export_dataset_keys": export_dataset_keys,
            "files": sorted(
                str(path.relative_to(bundle_root)) for path in bundle_root.rglob("*") if path.is_file()
            ),
        }
        manifest_path = bundle_root / "export_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        archive_path = Path("/tmp/results_archive.tar.gz")
        with tarfile.open(archive_path, "w:gz") as tar:
            for path in bundle_root.rglob("*"):
                tar.add(path, arcname=str(path.relative_to(bundle_root)))

        return OPIO({
            "results_archive": str(archive_path),
            "export_manifest": str(manifest_path),
        })
