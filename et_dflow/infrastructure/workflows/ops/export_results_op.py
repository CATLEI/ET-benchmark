"""
dflow OP for exporting benchmark results.

Collects step artifacts into a single archive that can be downloaded
to the master node and unpacked into results/<time>/.
"""

import json
import shutil
import tarfile
from pathlib import Path
from typing import List

from dflow.python import OP, OPIO, Parameter, Artifact


class ExportResultsOP(OP):
    """Bundle workflow artifacts into a downloadable archive."""

    @classmethod
    def get_input_sign(cls):
        return OPIO({
            "prepared_data": Artifact(str),
            "ground_truth": Artifact(str, optional=True),
            "algorithm_names": Parameter(List[str]),
            "reconstructions": Artifact(List[str]),
            "reconstruction_npys": Artifact(List[str]),
            "metrics_files": Artifact(List[str]),
            "comparison_report": Artifact(str),
            "comparison_json": Artifact(str),
            "visualizations": Artifact(str, optional=True),
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

        prepared_data = Path(op_in["prepared_data"])
        shutil.copy2(str(prepared_data), str(data_dir / "prepared_data.hspy"))

        ground_truth = op_in.get("ground_truth")
        if ground_truth:
            shutil.copy2(str(ground_truth), str(data_dir / "prepared_data_ground_truth.hspy"))

        algorithm_names = op_in["algorithm_names"]
        reconstructions = op_in["reconstructions"]
        reconstruction_npys = op_in["reconstruction_npys"]
        metrics_files = op_in["metrics_files"]

        for alg_name, reconstruction, reconstruction_npy, metrics_file in zip(
            algorithm_names,
            reconstructions,
            reconstruction_npys,
            metrics_files,
        ):
            alg_dir = bundle_root / alg_name
            alg_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(reconstruction), str(alg_dir / "reconstruction.hspy"))
            shutil.copy2(str(reconstruction_npy), str(alg_dir / "reconstruction.npy"))
            shutil.copy2(str(metrics_file), str(alg_dir / "evaluation.json"))

        comparison_report = Path(op_in["comparison_report"])
        comparison_json = Path(op_in["comparison_json"])
        shutil.copy2(str(comparison_report), str(bundle_root / "comparison_report.html"))
        shutil.copy2(str(comparison_json), str(bundle_root / "comparison_summary.json"))

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
            "algorithms": algorithm_names,
            "files": sorted(str(path.relative_to(bundle_root)) for path in bundle_root.rglob("*") if path.is_file()),
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
