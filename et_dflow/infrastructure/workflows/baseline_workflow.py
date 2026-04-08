"""
dflow workflow for baseline benchmark.

Executes multiple algorithms in parallel Docker containers and evaluates results.
Supports multiple datasets in one Workflow.submit() (dataset × algorithm fan-out).
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from dflow import Workflow, Step, Steps, upload_artifact
from dflow.python import OPIO
from dflow.plugins.dispatcher import PythonOPTemplate
from et_dflow.infrastructure.workflows.ops.data_preparation_op import DataPreparationOP
from et_dflow.infrastructure.workflows.ops.algorithm_execution_op import AlgorithmExecutionOP
from et_dflow.infrastructure.workflows.ops.evaluation_op import EvaluationOP
from et_dflow.infrastructure.workflows.ops.comparison_op import ComparisonOP
from et_dflow.infrastructure.workflows.ops.export_results_op import ExportResultsOP
from et_dflow.infrastructure.workflows.ops.preprocessing_evaluation_op import PreprocessingEvaluationOP
from et_dflow.infrastructure.workflows.dflow_config import configure_dflow


def _sanitize_step_segment(name: str) -> str:
    # Argo step names are stricter than file paths: use only lowercase
    # alphanumerics and '-'.
    s = str(name).lower()
    s = re.sub(r"[^a-z0-9-]+", "-", s)
    s = s.strip("-") or "x"
    return s[:80]


class BaselineBenchmarkWorkflow:
    """
    Baseline benchmark workflow using dflow.

    Remote: per-dataset data prep → (optional) preprocessing eval → algorithm × dataset →
    evaluation × (dataset, algorithm) → comparison → export.
    Hybrid: local prep for each dataset, remote algorithm steps only; local eval/comparison.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        workflow_config = config.get("workflow", {})
        output_dir = workflow_config.get("output_dir", "./results")
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self._base_run_output_dir = Path(output_dir).resolve() / timestamp
        self._run_output_dir = self._base_run_output_dir
        self._run_output_dir.mkdir(parents=True, exist_ok=True)
        self._hybrid = (workflow_config.get("execution_mode") or "remote").lower() == "hybrid"
        self._algorithm_names_list: List[str] = []
        self._local_prepared_data_path: Optional[str] = None
        self._local_ground_truth_path: Optional[str] = None
        self._hybrid_pairs: List[Tuple[str, str]] = []
        self._hybrid_local_by_ds: Dict[str, Tuple[str, Optional[str]]] = {}
        self._hybrid_dataset_cfgs: Dict[str, Dict[str, Any]] = {}
        self._submitted_workflow = None
        self._submitted_workflow_id: Optional[str] = None
        self._submitted_workflow_ids: List[str] = []
        self._active_dataset_keys: Optional[List[str]] = None
        self._remote_pairs: List[Tuple[str, str]] = []
        self._hybrid_downloaded_pairs: set[Tuple[str, str]] = set()
        dflow_section = config.get("dflow") or {}
        configure_dflow(
            dflow_section=dflow_section,
            workflow_output_dir=output_dir,
            run_dir=None,
        )

    @property
    def enabled_algorithm_names(self) -> List[str]:
        """Labels for enabled (dataset, algorithm) rows after ``build_workflow`` / ``submit``."""
        return list(self._algorithm_names_list)

    def _enabled_dataset_items(self) -> List[Tuple[str, Dict[str, Any]]]:
        datasets = self.config.get("datasets", {})
        out: List[Tuple[str, Dict[str, Any]]] = []
        for ds_key, ds_cfg in datasets.items():
            if ds_cfg.get("enabled", True) is False:
                continue
            if self._active_dataset_keys is not None and ds_key not in self._active_dataset_keys:
                continue
            out.append((ds_key, ds_cfg))
        return out

    def _enabled_algorithms(self) -> List[Tuple[str, Dict[str, Any]]]:
        algorithms = self.config.get("algorithms", {})
        return [(n, c) for n, c in algorithms.items() if c.get("enabled", True) is not False]

    def _workflow_steps_parallelism(self) -> Optional[int]:
        """Cap concurrent pods per ``Steps`` group (``workflow`` / ``benchmark_suite`` ``parallelism``)."""
        wf = self.config.get("workflow") or {}
        suite = self.config.get("benchmark_suite") or {}
        for src in (wf, suite):
            for key in ("parallelism", "steps_parallelism"):
                val = src.get(key)
                if val is None:
                    continue
                try:
                    n = int(val)
                    return n if n > 0 else None
                except (TypeError, ValueError):
                    continue
        return None

    @staticmethod
    def _count_steps_in_rows(rows: List[Union[Step, List[Step]]]) -> int:
        n = 0
        for item in rows:
            if isinstance(item, list):
                n += len(item)
            else:
                n += 1
        return n

    def _classify_dataset_size(self, ds_cfg: Dict[str, Any]) -> str:
        md = ds_cfg.get("metadata") or {}
        dims = md.get("recon_shape") or md.get("reconstruction_shape") or []
        proj_shape = md.get("projection_shape") or []
        num_proj = md.get("num_projections")
        score = 0
        try:
            if isinstance(dims, list) and len(dims) >= 3:
                score += int(dims[0]) * int(dims[1]) * int(dims[2])
            if isinstance(proj_shape, list) and len(proj_shape) >= 2:
                score += int(proj_shape[0]) * int(proj_shape[1]) * 8
            if num_proj is not None:
                score += int(num_proj) * 100000
        except Exception:
            score = 0
        if score >= 2_500_000_000:
            return "L"
        if score >= 600_000_000:
            return "M"
        return "S"

    def _resolve_runtime_profile(
        self,
        ds_key: str,
        ds_cfg: Dict[str, Any],
        alg_name: str,
        alg_cfg: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], str]:
        runtime_profiles = self.config.get("runtime_profiles") or {}
        dataset_profiles = self.config.get("dataset_profiles") or {}
        policy = self.config.get("policy") or {}
        params = alg_cfg.get("parameters") or {}
        selected_name = params.get("runtime_profile")
        size_class = self._classify_dataset_size(ds_cfg)
        if not selected_name:
            ds_profile = dataset_profiles.get(size_class) or {}
            selected_name = ds_profile.get("runtime_profile")
        if not selected_name:
            selected_name = policy.get("default_runtime_profile")
        selected = runtime_profiles.get(selected_name, {}) if selected_name else {}
        if selected_name:
            print(
                f"[et-dflow] runtime profile selected for {ds_key}/{alg_name}: "
                f"{selected_name} (size_class={size_class})"
            )
        return dict(selected or {}), size_class

    def _run_local_data_preparation(
        self,
        dataset_path: str,
        ground_truth_path: Optional[str],
        dataset_format: str,
        preprocessing_steps: Optional[List],
        preprocessing_evaluation_config: Optional[Dict[str, Any]],
        metadata: dict,
        prepared_output_path: Optional[str] = None,
    ) -> Tuple[str, Optional[str]]:
        """Run data preparation on the master node; return (prepared_data_path, ground_truth_path or None)."""
        prep_dir = self._run_output_dir / "_local_prep"
        prep_dir.mkdir(parents=True, exist_ok=True)
        out_path = prepared_output_path or str(prep_dir / "prepared_data.hspy")
        op_in = OPIO({
            "dataset_path": str(dataset_path),
            "dataset_format": dataset_format,
            "preprocessing_steps": preprocessing_steps,
            "preprocessing_evaluation_config": preprocessing_evaluation_config or {},
            "metadata": metadata or {},
            "prepared_data": str(out_path),
        })
        if ground_truth_path:
            op_in["ground_truth_path"] = str(ground_truth_path)
        op = DataPreparationOP()
        out = op.execute(op_in)
        gt_path = out.get("ground_truth")
        return (out["prepared_data"], gt_path if gt_path else None)

    def build_workflow(self) -> Workflow:
        datasets_items = self._enabled_dataset_items()
        algorithms_items = self._enabled_algorithms()
        eval_config = self.config.get("evaluation", {})
        workflow_config = self.config.get("workflow", {})

        if not datasets_items:
            raise ValueError("No enabled datasets in configuration.")
        if not algorithms_items:
            raise ValueError("No enabled algorithms found in configuration.")

        multi_dataset = len(datasets_items) > 1
        self._algorithm_names_list = []
        self._hybrid_pairs = []
        self._remote_pairs = []
        self._hybrid_local_by_ds = {}
        self._hybrid_dataset_cfgs = {}
        self._hybrid_downloaded_pairs = set()

        if self._hybrid:
            return self._build_workflow_hybrid(
                datasets_items,
                algorithms_items,
                eval_config,
                workflow_config,
                multi_dataset,
            )
        return self._build_workflow_remote(
            datasets_items,
            algorithms_items,
            eval_config,
            workflow_config,
            multi_dataset,
        )

    def _build_workflow_hybrid(
        self,
        datasets_items: List[Tuple[str, Dict[str, Any]]],
        algorithms_items: List[Tuple[str, Dict[str, Any]]],
        eval_config: Dict[str, Any],
        workflow_config: Dict[str, Any],
        multi_dataset: bool,
    ) -> Workflow:
        algorithm_steps = []
        for ds_key, ds_cfg in datasets_items:
            self._hybrid_dataset_cfgs[ds_key] = ds_cfg
            dataset_path = ds_cfg.get("path")
            if not dataset_path:
                raise ValueError(f"Dataset {ds_key} missing path in config")
            ground_truth_path = ds_cfg.get("ground_truth_path") or eval_config.get("ground_truth_path")
            san_ds = _sanitize_step_segment(ds_key)
            print(
                f"[et-dflow] Preparing dataset locally for hybrid mode: {ds_key} "
                f"(input={dataset_path}, ground_truth={'yes' if ground_truth_path else 'no'})"
            )
            if ground_truth_path:
                print(
                    f"[et-dflow] Hybrid mode defers GT loading to local evaluation: {ds_key} "
                    f"(ground_truth_path={ground_truth_path})"
                )
            prep_file = self._run_output_dir / "_local_prep" / f"{san_ds}_prepared.hspy"
            prepared, _ = self._run_local_data_preparation(
                dataset_path=dataset_path,
                ground_truth_path=None,
                dataset_format=ds_cfg.get("format", "hyperspy"),
                preprocessing_steps=ds_cfg.get("preprocessing_steps"),
                preprocessing_evaluation_config=ds_cfg.get("preprocessing_evaluation"),
                metadata=ds_cfg.get("metadata", {}),
                prepared_output_path=str(prep_file),
            )
            self._hybrid_local_by_ds[ds_key] = (prepared, ground_truth_path if ground_truth_path else None)
            print(f"[et-dflow] Uploading prepared artifact for dataset: {ds_key}")
            prepared_artifact = upload_artifact(prepared)
            print(f"[et-dflow] Prepared artifact upload finished for dataset: {ds_key}")

            for alg_name, alg_config in algorithms_items:
                docker_image = alg_config.get("docker_image")
                if not docker_image:
                    raise ValueError(f"Algorithm {alg_name} missing docker_image in config")
                resources = alg_config.get("resources", {})
                alg_op = AlgorithmExecutionOP()
                alg_template = PythonOPTemplate(
                    alg_op,
                    image=docker_image,
                    requests={
                        "cpu": str(resources.get("cpu", 2)),
                        "memory": resources.get("memory", "4Gi"),
                    } if resources else None,
                    limits={
                        "cpu": str(resources.get("cpu", 2)),
                        "memory": resources.get("memory", "4Gi"),
                    } if resources else None,
                )
                step_name = f"algorithm-{_sanitize_step_segment(ds_key)}-{_sanitize_step_segment(alg_name)}"
                compat_algorithm_config = {
                    **(alg_config.get("parameters", {}) or {}),
                    "_et_dflow_dataset_key": ds_key,
                    "_et_dflow_dataset_metadata": ds_cfg.get("metadata", {}),
                }
                runtime_profile_cfg, size_class = self._resolve_runtime_profile(
                    ds_key=ds_key,
                    ds_cfg=ds_cfg,
                    alg_name=alg_name,
                    alg_cfg=alg_config,
                )
                if runtime_profile_cfg:
                    compat_algorithm_config["runtime_profile"] = runtime_profile_cfg
                compat_algorithm_config.setdefault(
                    "execution_policy",
                    dict((self.config.get("policy") or {}).get("execution_policy") or {}),
                )
                compat_algorithm_config["_et_dflow_size_class"] = size_class
                # dataset_key / metadata live in algorithm_config (_et_dflow_*); do not pass as
                # separate Step parameters — older cluster et_dflow OP signatures without those
                # keys would raise KeyError in the generated staging script.
                alg_step = Step(
                    name=step_name,
                    template=alg_template,
                    parameters={
                        "algorithm_name": alg_name,
                        "algorithm_config": compat_algorithm_config,
                        "docker_image": docker_image,
                        "resources": resources,
                    },
                    artifacts={"prepared_data": prepared_artifact},
                )
                algorithm_steps.append(alg_step)
                self._hybrid_pairs.append((ds_key, alg_name))
                self._algorithm_names_list.append(f"{ds_key}/{alg_name}" if multi_dataset else alg_name)

        if len(datasets_items) == 1:
            dk0 = datasets_items[0][0]
            p, g = self._hybrid_local_by_ds[dk0]
            self._local_prepared_data_path = p
            self._local_ground_truth_path = g
        else:
            self._local_prepared_data_path = None
            self._local_ground_truth_path = None

        workflow_name = workflow_config.get("name", "baseline-benchmark")
        para = self._workflow_steps_parallelism()
        step_rows: List[Union[Step, List[Step]]] = [algorithm_steps]
        return Workflow(
            name=workflow_name,
            steps=Steps(
                name=workflow_name + "-steps",
                steps=step_rows,
                parallelism=para,
            ),
        )

    def _build_workflow_remote(
        self,
        datasets_items: List[Tuple[str, Dict[str, Any]]],
        algorithms_items: List[Tuple[str, Dict[str, Any]]],
        eval_config: Dict[str, Any],
        workflow_config: Dict[str, Any],
        multi_dataset: bool,
    ) -> Workflow:
        runner_image = workflow_config.get("runner_image") or workflow_config.get("default_image")
        if not runner_image:
            raise ValueError(
                "workflow.runner_image (or workflow.default_image) is required in remote cluster mode. "
                "Use execution_mode: hybrid to run data prep and evaluation on the master node and omit runner_image."
            )

        data_prep_steps: Dict[str, Step] = {}
        preprocessing_eval_steps: Dict[str, Step] = {}

        for ds_key, ds_cfg in datasets_items:
            dataset_path = ds_cfg.get("path")
            if not dataset_path:
                raise ValueError(f"Dataset {ds_key} missing path in config")
            ground_truth_path = ds_cfg.get("ground_truth_path") or eval_config.get("ground_truth_path")
            san_ds = _sanitize_step_segment(ds_key)

            print(
                f"[et-dflow] Uploading input dataset artifact: {ds_key} "
                f"(path={dataset_path})"
            )
            dataset_artifact = upload_artifact(dataset_path)
            print(f"[et-dflow] Dataset artifact upload finished: {ds_key}")
            if ground_truth_path:
                print(
                    f"[et-dflow] Uploading ground truth artifact: {ds_key} "
                    f"(path={ground_truth_path})"
                )
            ground_truth_artifact = upload_artifact(ground_truth_path) if ground_truth_path else None
            if ground_truth_path:
                print(f"[et-dflow] Ground truth artifact upload finished: {ds_key}")

            prep_steps = ds_cfg.get("preprocessing_steps")
            prep_eval_cfg = ds_cfg.get("preprocessing_evaluation") or {}
            prep_config_artifact = None
            if prep_steps is not None or prep_eval_cfg:
                prep_config_path = self._run_output_dir / f"_prep_config_{san_ds}.json"
                with open(prep_config_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "preprocessing_steps": prep_steps,
                        "preprocessing_evaluation_config": prep_eval_cfg,
                    }, f, ensure_ascii=False)
                print(f"[et-dflow] Uploading preprocessing config artifact: {ds_key}")
                prep_config_artifact = upload_artifact(str(prep_config_path))
                print(f"[et-dflow] Preprocessing config upload finished: {ds_key}")

            data_prep_artifacts: Dict[str, Any] = {"dataset_path": dataset_artifact}
            if ground_truth_artifact is not None:
                data_prep_artifacts["ground_truth_path"] = ground_truth_artifact
            if prep_config_artifact is not None:
                data_prep_artifacts["preprocessing_config"] = prep_config_artifact

            _prep_params = {
                "dataset_format": ds_cfg.get("format", "hyperspy"),
                "prepared_data": "/tmp/prepared_data.hspy",
                "preprocessing_steps": None,
                "preprocessing_evaluation_config": {},
                "metadata": ds_cfg.get("metadata", {}),
            }

            data_prep_op = DataPreparationOP()
            data_prep_template = PythonOPTemplate(data_prep_op, image=runner_image)
            dp_step = Step(
                name=f"data-prep-{san_ds}",
                template=data_prep_template,
                parameters=_prep_params,
                artifacts=data_prep_artifacts,
            )
            data_prep_steps[ds_key] = dp_step

            if prep_eval_cfg:
                prep_eval_op = PreprocessingEvaluationOP()
                prep_eval_template = PythonOPTemplate(prep_eval_op, image=runner_image)
                pe_artifacts = {
                    "alignment_output": dp_step.outputs.artifacts.get("alignment_output"),
                    "denoising_output": dp_step.outputs.artifacts.get("denoising_output"),
                }
                pe_artifacts = {k: v for k, v in pe_artifacts.items() if v is not None}
                if pe_artifacts:
                    preprocessing_eval_steps[ds_key] = Step(
                        name=f"preprocessing-evaluation-{san_ds}",
                        template=prep_eval_template,
                        parameters={
                            "alignment_metrics": prep_eval_cfg.get(
                                "alignment_metrics", ["shift_stability", "cross_correlation_peak"]
                            ),
                            "denoising_metrics": prep_eval_cfg.get(
                                "denoising_metrics", ["snr_estimate", "local_variance"]
                            ),
                            "metrics_output": f"/tmp/preprocessing_metrics_{san_ds}.json",
                        },
                        artifacts=pe_artifacts,
                    )

        algorithm_steps: List[Step] = []
        algorithm_meta: List[Tuple[str, str, Step]] = []
        ds_cfg_by_key: Dict[str, Dict[str, Any]] = dict(datasets_items)

        for ds_key, ds_cfg in datasets_items:
            san_ds = _sanitize_step_segment(ds_key)
            dp_step = data_prep_steps[ds_key]
            for alg_name, alg_config in algorithms_items:
                docker_image = alg_config.get("docker_image")
                if not docker_image:
                    raise ValueError(f"Algorithm {alg_name} missing docker_image in config")
                resources = alg_config.get("resources", {})
                alg_op = AlgorithmExecutionOP()
                alg_template = PythonOPTemplate(
                    alg_op,
                    image=docker_image,
                    requests={
                        "cpu": str(resources.get("cpu", 2)),
                        "memory": resources.get("memory", "4Gi"),
                    } if resources else None,
                    limits={
                        "cpu": str(resources.get("cpu", 2)),
                        "memory": resources.get("memory", "4Gi"),
                    } if resources else None,
                )
                compat_algorithm_config = {
                    **(alg_config.get("parameters", {}) or {}),
                    "_et_dflow_dataset_key": ds_key,
                    "_et_dflow_dataset_metadata": ds_cfg.get("metadata", {}),
                }
                runtime_profile_cfg, size_class = self._resolve_runtime_profile(
                    ds_key=ds_key,
                    ds_cfg=ds_cfg,
                    alg_name=alg_name,
                    alg_cfg=alg_config,
                )
                if runtime_profile_cfg:
                    compat_algorithm_config["runtime_profile"] = runtime_profile_cfg
                compat_algorithm_config.setdefault(
                    "execution_policy",
                    dict((self.config.get("policy") or {}).get("execution_policy") or {}),
                )
                compat_algorithm_config["_et_dflow_size_class"] = size_class
                _alg_params = {
                    "algorithm_name": alg_name,
                    "algorithm_config": compat_algorithm_config,
                    "docker_image": docker_image,
                    "resources": resources,
                }
                alg_step = Step(
                    name=f"algorithm-{san_ds}-{_sanitize_step_segment(alg_name)}",
                    template=alg_template,
                    parameters=_alg_params,
                    artifacts={
                        "prepared_data": dp_step.outputs.artifacts["prepared_data"],
                    },
                )
                algorithm_steps.append(alg_step)
                algorithm_meta.append((ds_key, alg_name, alg_step))
                self._algorithm_names_list.append(f"{ds_key}/{alg_name}" if multi_dataset else alg_name)

        evaluation_steps: List[Step] = []
        for ds_key, alg_name, alg_step in algorithm_meta:
            san_ds = _sanitize_step_segment(ds_key)
            san_alg = _sanitize_step_segment(alg_name)
            ds_cfg = ds_cfg_by_key[ds_key]
            suite_meta = ds_cfg.get("metadata", {}) or {}
            dp_step = data_prep_steps[ds_key]
            eval_op = EvaluationOP()
            eval_template = PythonOPTemplate(eval_op, image=runner_image)
            eval_artifacts: Dict[str, Any] = {
                "reconstruction": alg_step.outputs.artifacts["reconstruction"],
            }
            if "ground_truth" in dp_step.outputs.artifacts:
                eval_artifacts["ground_truth"] = dp_step.outputs.artifacts["ground_truth"]
            eval_step = Step(
                name=f"evaluation-{san_ds}-{san_alg}",
                template=eval_template,
                parameters={
                    "algorithm_name": alg_name,
                    "metrics": eval_config.get("metrics", ["psnr", "ssim", "mse"]),
                    "metrics_file": f"/tmp/{san_ds}_{san_alg}_evaluation.json",
                    "dataset_key": ds_key,
                    "suite_metadata": suite_meta,
                },
                artifacts=eval_artifacts,
            )
            evaluation_steps.append(eval_step)

        algorithm_names_plain = [alg for _, alg, _ in algorithm_meta]
        row_labels = [
            f"{dk}/{alg}" if multi_dataset else alg for dk, alg, _ in algorithm_meta
        ]

        comparison_op = ComparisonOP()
        comparison_template = PythonOPTemplate(comparison_op, image=runner_image)
        comparison_step = Step(
            name="comparison-report",
            template=comparison_template,
            parameters={
                "algorithm_names": algorithm_names_plain,
                "row_labels": row_labels,
            },
            artifacts={
                "metrics_files": [st.outputs.artifacts["metrics_file"] for st in evaluation_steps],
                "execution_metadata_files": [
                    st.outputs.artifacts["execution_metadata"] for st in algorithm_steps
                ],
            },
        )

        ordered_ds_keys = list(dict.fromkeys(ds_key for ds_key, _, _ in algorithm_meta))
        prepared_list = [data_prep_steps[dk].outputs.artifacts["prepared_data"] for dk in ordered_ds_keys]
        gt_keys: List[str] = []
        gt_arts: List[Any] = []
        for dk in ordered_ds_keys:
            dp = data_prep_steps[dk]
            if "ground_truth" in dp.outputs.artifacts:
                gt_keys.append(dk)
                gt_arts.append(dp.outputs.artifacts["ground_truth"])

        export_dataset_keys = [ds_key for ds_key, _, _ in algorithm_meta]

        export_op = ExportResultsOP()
        export_template = PythonOPTemplate(export_op, image=runner_image)
        export_artifacts: Dict[str, Any] = {
            "prepared_data_list": prepared_list,
            "dataset_keys": ordered_ds_keys,
            "export_dataset_keys": export_dataset_keys,
            "algorithm_names": algorithm_names_plain,
            "row_labels": row_labels,
            "reconstructions": [st.outputs.artifacts["reconstruction"] for st in algorithm_steps],
            "reconstruction_npys": [st.outputs.artifacts["reconstruction_npy"] for st in algorithm_steps],
            "execution_metadata_files": [
                st.outputs.artifacts["execution_metadata"] for st in algorithm_steps
            ],
            "metrics_files": [st.outputs.artifacts["metrics_file"] for st in evaluation_steps],
            "comparison_report": comparison_step.outputs.artifacts["comparison_report"],
            "comparison_json": comparison_step.outputs.artifacts["comparison_json"],
            "visualizations": comparison_step.outputs.artifacts["visualizations"],
            "leaderboard_json": comparison_step.outputs.artifacts["leaderboard_json"],
        }
        if gt_arts:
            export_artifacts["ground_truth_dataset_keys"] = gt_keys
            export_artifacts["ground_truth_list"] = gt_arts

        if preprocessing_eval_steps:
            export_artifacts["preprocessing_metrics_files"] = [
                preprocessing_eval_steps[dk].outputs.artifacts["preprocessing_metrics_file"]
                for dk in ordered_ds_keys
                if dk in preprocessing_eval_steps
            ]
            export_artifacts["preprocessing_metrics_dataset_keys"] = [
                dk for dk in ordered_ds_keys if dk in preprocessing_eval_steps
            ]

        export_step = Step(
            name="export-results",
            template=export_template,
            parameters={},
            artifacts=export_artifacts,
        )

        step_rows: List[Union[Step, List[Step]]] = [list(data_prep_steps.values())]
        if preprocessing_eval_steps:
            step_rows.append(list(preprocessing_eval_steps.values()))
        step_rows.append(algorithm_steps)
        step_rows.append(evaluation_steps)
        step_rows.append(comparison_step)
        step_rows.append(export_step)

        self._remote_pairs = [(dk, alg) for dk, alg, _ in algorithm_meta]
        workflow_name = workflow_config.get("name", "baseline-benchmark")
        para = self._workflow_steps_parallelism()
        flat_count = self._count_steps_in_rows(step_rows)
        workflow_kwargs = {
            "name": workflow_name,
            "steps_name": workflow_name + "-steps",
            "steps_count": flat_count,
        }
        print("[et-dflow debug] Workflow(...) args:", workflow_kwargs)
        return Workflow(
            name=workflow_name,
            steps=Steps(
                name=workflow_name + "-steps",
                steps=step_rows,
                parallelism=para,
            ),
        )

    @staticmethod
    def _normalize_workflow_id(workflow_id: Any) -> str:
        """Normalize dflow/Argo return value to a single workflow id string.

        If the API returns a list, only the first element is used (single-workflow submit).
        """
        if isinstance(workflow_id, list) and workflow_id:
            workflow_id = workflow_id[0]
        if hasattr(workflow_id, "id"):
            workflow_id = getattr(workflow_id, "id")
        if hasattr(workflow_id, "name"):
            workflow_id = getattr(workflow_id, "name")
        if isinstance(workflow_id, dict):
            metadata = workflow_id.get("metadata") if isinstance(workflow_id.get("metadata"), dict) else {}
            workflow_id = workflow_id.get("id") or workflow_id.get("uid") or metadata.get("name")
        if not workflow_id:
            raise ValueError(f"Invalid workflow id for remote mode: {workflow_id}")
        return str(workflow_id)

    def _full_enabled_dataset_keys(self) -> List[str]:
        datasets = self.config.get("datasets", {})
        keys: List[str] = []
        for ds_key, ds_cfg in datasets.items():
            if ds_cfg.get("enabled", True) is False:
                continue
            keys.append(ds_key)
        return keys

    @staticmethod
    def _suite_shard_chunk_size(config: Dict[str, Any]) -> int:
        suite = config.get("benchmark_suite") or {}
        max_per = suite.get("max_datasets_per_workflow")
        if max_per is None:
            return 0
        try:
            n = int(max_per)
            return n if n > 0 else 0
        except (TypeError, ValueError):
            return 0

    def submit(self):
        """Submit workflow(s) to dflow. Returns a single id or a list of ids when sharded."""
        suite_cfg = self.config.get("benchmark_suite") or {}
        if suite_cfg.get("enabled") is False:
            raise ValueError("benchmark_suite.enabled is false; refusing to submit.")

        chunk_size = self._suite_shard_chunk_size(self.config)
        full_keys = self._full_enabled_dataset_keys()

        if chunk_size > 0 and len(full_keys) > chunk_size:
            ids: List[str] = []
            for si, i in enumerate(range(0, len(full_keys), chunk_size)):
                chunk = full_keys[i: i + chunk_size]
                self._active_dataset_keys = chunk
                self._run_output_dir = self._base_run_output_dir / f"shard_{si:03d}"
                self._run_output_dir.mkdir(parents=True, exist_ok=True)
                ids.append(self._submit_once())
            self._active_dataset_keys = None
            self._run_output_dir = self._base_run_output_dir
            self._submitted_workflow_ids = ids
            self._submitted_workflow = None
            self._submitted_workflow_id = None
            return ids if len(ids) > 1 else ids[0]

        self._active_dataset_keys = None
        self._submitted_workflow_ids = []
        wid = self._submit_once()
        self._submitted_workflow_ids = [wid]
        return wid

    def _submit_once(self) -> str:
        workflow = self.build_workflow()
        from dflow import config as dflow_config
        submit_view = {
            "host": dflow_config.get("host"),
            "namespace": dflow_config.get("namespace"),
        }
        print("[et-dflow debug] submit() input:", submit_view)
        pairs = self._hybrid_pairs if self._hybrid else self._remote_pairs
        if pairs:
            remote_step_labels = ", ".join(
                f"algorithm-{_sanitize_step_segment(ds)}-{_sanitize_step_segment(alg)}"
                for ds, alg in pairs
            )
            print(f"[et-dflow] Enabled algorithm container step(s): {remote_step_labels}")
            if not self._hybrid:
                eval_labels = ", ".join(
                    f"evaluation-{_sanitize_step_segment(ds)}-{_sanitize_step_segment(alg)}"
                    for ds, alg in pairs
                )
                print(f"[et-dflow] Matching evaluation step(s) (remote mode): {eval_labels}")
        submit_result = workflow.submit()
        workflow_id = self._normalize_workflow_id(submit_result)
        self._submitted_workflow = workflow
        self._submitted_workflow_id = workflow_id
        return workflow_id

    def wait(self, workflow_id: str, timeout: Optional[int] = None):
        from dflow import Workflow
        wid = self._normalize_workflow_id(workflow_id)
        print("[et-dflow debug] Workflow.wait() input:", {"id": wid})
        print("[et-dflow debug] wait: dflow will poll Argo (may trigger 414 on gateway GET URI)")
        if self._submitted_workflow is not None and self._submitted_workflow_id == wid:
            workflow = self._submitted_workflow
        else:
            workflow = Workflow(id=wid)
        if self._hybrid:
            self._wait_hybrid_incremental(workflow, timeout=timeout)
            return
        workflow.wait()

    def _wait_hybrid_incremental(self, workflow, timeout: Optional[int] = None):
        import time

        poll_interval_s = 10
        started = time.time()
        last_status = None
        total_pairs = len(self._hybrid_pairs)

        while True:
            status = workflow.query_status()
            if status != last_status:
                print(f"[et-dflow] Hybrid workflow status: {status}")
                last_status = status

            self._download_available_hybrid_results(workflow)
            completed = len(self._hybrid_downloaded_pairs)
            if completed:
                print(
                    f"[et-dflow] Hybrid incremental download progress: "
                    f"{completed}/{total_pairs} algorithm instance(s) downloaded"
                )

            if status in {"Succeeded", "Failed", "Error"}:
                break
            if timeout is not None and (time.time() - started) > timeout:
                raise TimeoutError(f"Hybrid workflow wait timed out after {timeout} seconds")
            time.sleep(poll_interval_s)

        if status != "Succeeded":
            print(
                f"[et-dflow] Hybrid workflow finished with status={status}; "
                "downloading any remaining successful algorithm artifacts before returning."
            )
            self._download_available_hybrid_results(workflow)

    def _download_available_hybrid_results(self, workflow) -> None:
        for ds_key, alg_name in self._hybrid_pairs:
            pair = (ds_key, alg_name)
            if pair in self._hybrid_downloaded_pairs:
                continue
            step_name = f"algorithm-{_sanitize_step_segment(ds_key)}-{_sanitize_step_segment(alg_name)}"
            steps = workflow.query_step(name=step_name, phase="Succeeded")
            if not steps:
                continue
            self._download_single_hybrid_algorithm_step(steps[-1], ds_key, alg_name)
            self._hybrid_downloaded_pairs.add(pair)
            print(f"[et-dflow] Downloaded completed hybrid result: {ds_key}/{alg_name}")

    def _download_single_hybrid_algorithm_step(self, step, ds_key: str, alg_name: str) -> None:
        import shutil
        from tempfile import TemporaryDirectory
        from dflow import download_artifact

        safe_ds = _sanitize_step_segment(ds_key)
        safe_alg = _sanitize_step_segment(alg_name)
        alg_dir = self._run_output_dir / "by_dataset" / safe_ds / safe_alg
        alg_dir.mkdir(parents=True, exist_ok=True)
        for key, target_name in (
            ("reconstruction", "reconstruction.hspy"),
            ("reconstruction_npy", "reconstruction.npy"),
            ("execution_metadata", "execution_metadata.json"),
        ):
            if key not in step.outputs.artifacts:
                continue
            with TemporaryDirectory() as tmp:
                downloaded = download_artifact(step.outputs.artifacts[key], path=tmp)
                if not downloaded:
                    continue
                path = Path(downloaded[0])
                if path.is_file():
                    shutil.copy2(path, alg_dir / target_name)
                elif path.is_dir():
                    for f in path.rglob("*"):
                        if f.is_file() and (f.suffix == ".hspy" or f.suffix == ".npy"):
                            shutil.copy2(f, alg_dir / target_name)
                            break

    def download_results(self, workflow_id: str) -> Path:
        import shutil
        import tarfile
        from tempfile import TemporaryDirectory
        from dflow import Workflow, download_artifact

        wid = self._normalize_workflow_id(workflow_id)
        if self._submitted_workflow is not None and self._submitted_workflow_id == wid:
            workflow = self._submitted_workflow
        else:
            workflow = Workflow(id=wid)
        self._run_output_dir.mkdir(parents=True, exist_ok=True)

        if self._hybrid:
            return self._download_results_hybrid(workflow)
        return self._download_results_remote(workflow)

    def _download_results_hybrid(self, workflow) -> Path:
        import os
        import shutil

        eval_config = self.config.get("evaluation", {})
        metrics_list = eval_config.get("metrics", ["psnr", "ssim", "mse"])

        self._download_available_hybrid_results(workflow)

        data_dir = self._run_output_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        by_ds = data_dir / "by_dataset"
        by_ds.mkdir(parents=True, exist_ok=True)
        for ds_key, (prep_path, gt_path) in self._hybrid_local_by_ds.items():
            safe_ds = _sanitize_step_segment(ds_key)
            ddir = by_ds / safe_ds
            ddir.mkdir(parents=True, exist_ok=True)
            if prep_path and os.path.exists(prep_path):
                shutil.copy2(prep_path, ddir / "prepared_data.hspy")
            if gt_path and os.path.exists(gt_path):
                shutil.copy2(gt_path, ddir / "prepared_data_ground_truth.hspy")
        if len(self._hybrid_local_by_ds) == 1:
            only = next(iter(self._hybrid_local_by_ds.values()))
            if only[0] and os.path.exists(only[0]):
                shutil.copy2(only[0], data_dir / "prepared_data.hspy")
            if only[1] and os.path.exists(only[1]):
                shutil.copy2(only[1], data_dir / "prepared_data_ground_truth.hspy")

        eval_op = EvaluationOP()
        algorithm_names_plain: List[str] = []
        row_labels: List[str] = []
        metrics_files: List[str] = []
        execution_metadata_files: List[str] = []
        multi = len(self._hybrid_local_by_ds) > 1
        for ds_key, alg_name in self._hybrid_pairs:
            safe_ds = _sanitize_step_segment(ds_key)
            safe_alg = _sanitize_step_segment(alg_name)
            recon_path = self._run_output_dir / "by_dataset" / safe_ds / safe_alg / "reconstruction.hspy"
            if not recon_path.exists():
                continue
            ds_cfg = self._hybrid_dataset_cfgs.get(ds_key, {})
            suite_meta = ds_cfg.get("metadata", {}) or {}
            metrics_file = self._run_output_dir / "by_dataset" / safe_ds / safe_alg / "evaluation.json"
            execution_metadata_file = self._run_output_dir / "by_dataset" / safe_ds / safe_alg / "execution_metadata.json"
            op_in = OPIO({
                "reconstruction": str(recon_path),
                "metrics": metrics_list,
                "algorithm_name": alg_name,
                "metrics_file": str(metrics_file),
                "dataset_key": ds_key,
                "suite_metadata": suite_meta,
            })
            _prep, gt_path = self._hybrid_local_by_ds.get(ds_key, (None, None))
            if gt_path and os.path.exists(gt_path):
                op_in["ground_truth"] = gt_path
            eval_op.execute(op_in)
            algorithm_names_plain.append(alg_name)
            row_labels.append(f"{ds_key}/{alg_name}" if multi else alg_name)
            metrics_files.append(str(metrics_file))
            if execution_metadata_file.exists():
                execution_metadata_files.append(str(execution_metadata_file))
        if metrics_files:
            comp_op = ComparisonOP()
            op_comp = {
                "metrics_files": metrics_files,
                "algorithm_names": algorithm_names_plain,
                "row_labels": row_labels,
            }
            if len(execution_metadata_files) == len(metrics_files):
                op_comp["execution_metadata_files"] = execution_metadata_files
            comp_out = comp_op.execute(OPIO(op_comp))
            for name, path_key in (
                ("comparison_report", "comparison_report.html"),
                ("comparison_json", "comparison_summary.json"),
                ("leaderboard_json", "leaderboard/suite_leaderboard.json"),
            ):
                src = comp_out.get(name)
                if src and os.path.exists(src):
                    dest = self._run_output_dir / path_key
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)
            src_cmp = Path(comp_out.get("comparison_json", "")).parent
            if src_cmp.is_dir():
                lb_dir = src_cmp / "leaderboard"
                if lb_dir.is_dir():
                    out_lb = self._run_output_dir / "leaderboard"
                    out_lb.mkdir(parents=True, exist_ok=True)
                    for child in lb_dir.iterdir():
                        if child.is_file():
                            shutil.copy2(str(child), str(out_lb / child.name))
                csv_src = src_cmp / "leaderboard.csv"
                if csv_src.is_file():
                    shutil.copy2(str(csv_src), str(self._run_output_dir / "leaderboard.csv"))

        return self._run_output_dir

    def _download_results_remote(self, workflow) -> Path:
        import tarfile
        from tempfile import TemporaryDirectory
        from dflow import download_artifact

        steps = workflow.query_step(name="export-results", phase="Succeeded")
        if not steps:
            raise RuntimeError("Could not find succeeded 'export-results' step to download results from.")
        export_step = steps[-1]
        archive_artifact = export_step.outputs.artifacts["results_archive"]
        with TemporaryDirectory() as tmp_dir:
            downloaded = download_artifact(archive_artifact, extract=False, path=tmp_dir)
            if not downloaded:
                raise RuntimeError("Failed to download results archive from workflow artifacts.")
            archive_path = Path(downloaded[0])
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.extractall(path=self._run_output_dir)
        return self._run_output_dir

    def get_status(self, workflow_id: str) -> str:
        from dflow import Workflow
        wid = self._normalize_workflow_id(workflow_id)
        if self._submitted_workflow is not None and self._submitted_workflow_id == wid:
            workflow = self._submitted_workflow
        else:
            workflow = Workflow(id=wid)
        return workflow.query_status()
