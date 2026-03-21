"""
dflow workflow for baseline benchmark.

Executes multiple algorithms in parallel Docker containers and evaluates results.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

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


class BaselineBenchmarkWorkflow:
    """
    Baseline benchmark workflow using dflow.
    
    Workflow structure:
    1. Data Preparation (single step)
    2. Algorithm Execution (parallel steps, one per algorithm)
    3. Evaluation (single step, depends on all algorithms)
    4. Report Generation (single step, depends on evaluation)
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize workflow.
        
        Args:
            config: Configuration dictionary containing:
                - datasets: Dataset configuration
                - algorithms: Algorithm configuration with docker_image
                - evaluation: Evaluation configuration
                - workflow: Workflow configuration
        """
        self.config = config
        workflow_config = config.get("workflow", {})
        output_dir = workflow_config.get("output_dir", "./results")
        self._run_output_dir = Path(output_dir).resolve() / datetime.now().strftime("%Y%m%d-%H%M%S")
        self._run_output_dir.mkdir(parents=True, exist_ok=True)
        self._hybrid = (workflow_config.get("execution_mode") or "remote").lower() == "hybrid"
        self._algorithm_names_list = []
        self._local_prepared_data_path = None
        self._local_ground_truth_path = None
        self._submitted_workflow = None
        self._submitted_workflow_id = None
        dflow_section = config.get("dflow") or {}
        configure_dflow(
            dflow_section=dflow_section,
            workflow_output_dir=output_dir,
            run_dir=None,
        )
    
    def _run_local_data_preparation(
        self,
        dataset_path: str,
        ground_truth_path: Optional[str],
        dataset_format: str,
        preprocessing_steps: Optional[List],
        preprocessing_evaluation_config: Optional[Dict[str, Any]],
        metadata: dict,
    ) -> tuple:
        """Run data preparation on the master node; return (prepared_data_path, ground_truth_path or None)."""
        prep_dir = self._run_output_dir / "_local_prep"
        prep_dir.mkdir(parents=True, exist_ok=True)
        prepared_data_path = prep_dir / "prepared_data.hspy"
        op_in = OPIO({
            "dataset_path": str(dataset_path),
            "dataset_format": dataset_format,
            "preprocessing_steps": preprocessing_steps,
            "preprocessing_evaluation_config": preprocessing_evaluation_config or {},
            "metadata": metadata or {},
            "prepared_data": str(prepared_data_path),
        })
        if ground_truth_path:
            op_in["ground_truth_path"] = str(ground_truth_path)
        op = DataPreparationOP()
        out = op.execute(op_in)
        gt_path = out.get("ground_truth")
        return (out["prepared_data"], gt_path if gt_path else None)

    def build_workflow(self) -> Workflow:
        """
        Build dflow workflow.
        
        In hybrid mode: data prep runs locally; only algorithm steps run remotely (no runner_image).
        In remote mode: all steps run in remote containers (runner_image required).
        
        Returns:
            dflow Workflow object
        """
        datasets = self.config.get("datasets", {})
        algorithms = self.config.get("algorithms", {})
        eval_config = self.config.get("evaluation", {})
        workflow_config = self.config.get("workflow", {})

        dataset_name = list(datasets.keys())[0] if datasets else "default"
        dataset_config = datasets.get(dataset_name, {})
        dataset_path = dataset_config.get("path")
        ground_truth_path = dataset_config.get("ground_truth_path") or eval_config.get("ground_truth_path")

        if self._hybrid:
            # Hybrid: data prep locally, only algorithm steps in Argo. runner_image not required.
            self._local_prepared_data_path, self._local_ground_truth_path = self._run_local_data_preparation(
                dataset_path=dataset_path,
                ground_truth_path=ground_truth_path,
                dataset_format=dataset_config.get("format", "hyperspy"),
                preprocessing_steps=dataset_config.get("preprocessing_steps"),
                preprocessing_evaluation_config=dataset_config.get("preprocessing_evaluation"),
                metadata=dataset_config.get("metadata", {}),
            )
            prepared_artifact = upload_artifact(self._local_prepared_data_path)
            # Algorithm steps only
            algorithm_steps = []
            for alg_name, alg_config in algorithms.items():
                if not alg_config.get("enabled", True):
                    continue
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
                alg_step = Step(
                    name=f"algorithm-{alg_name}",
                    template=alg_template,
                    parameters={
                        "algorithm_name": alg_name,
                        "algorithm_config": alg_config.get("parameters", {}),
                        "docker_image": docker_image,
                        "resources": resources,
                    },
                    artifacts={"prepared_data": prepared_artifact},
                )
                algorithm_steps.append(alg_step)
                self._algorithm_names_list.append(alg_name)

            if not algorithm_steps:
                raise ValueError("No enabled algorithms found in configuration.")

            workflow_name = workflow_config.get("name", "baseline-benchmark")
            return Workflow(
                name=workflow_name,
                steps=Steps(name=workflow_name + "-steps", steps=algorithm_steps),
            )

        # Remote mode: all steps in Argo, runner_image required
        runner_image = workflow_config.get("runner_image") or workflow_config.get("default_image")
        if not runner_image:
            raise ValueError(
                "workflow.runner_image (or workflow.default_image) is required in remote cluster mode. "
                "Use execution_mode: hybrid to run data prep and evaluation on the master node and omit runner_image."
            )

        dataset_artifact = upload_artifact(dataset_path)
        ground_truth_artifact = upload_artifact(ground_truth_path) if ground_truth_path else None

        prep_steps = dataset_config.get("preprocessing_steps")
        prep_eval_cfg = dataset_config.get("preprocessing_evaluation") or {}
        prep_config_artifact = None
        if prep_steps is not None or prep_eval_cfg:
            prep_config_path = self._run_output_dir / "_prep_config.json"
            with open(prep_config_path, "w", encoding="utf-8") as f:
                json.dump({
                    "preprocessing_steps": prep_steps,
                    "preprocessing_evaluation_config": prep_eval_cfg,
                }, f, ensure_ascii=False)
            prep_config_artifact = upload_artifact(str(prep_config_path))

        data_prep_artifacts = {
            "dataset_path": dataset_artifact,
            **({"ground_truth_path": ground_truth_artifact} if ground_truth_artifact else {}),
        }
        if prep_config_artifact is not None:
            data_prep_artifacts["preprocessing_config"] = prep_config_artifact

        # [debug] 打印本侧传入数据准备 step 的内容，便于核对是否把大对象塞进 parameters
        _prep_params = {
            "dataset_format": dataset_config.get("format", "hyperspy"),
            "prepared_data": "/tmp/prepared_data.hspy",
            "preprocessing_steps": None,
            "preprocessing_evaluation_config": {},
        }

        data_prep_op = DataPreparationOP()
        data_prep_template = PythonOPTemplate(data_prep_op, image=runner_image)
        data_prep_step = Step(
            name="data-preparation",
            template=data_prep_template,
            parameters=_prep_params,
            artifacts=data_prep_artifacts,
        )

        algorithm_steps = []
        algorithm_names = {}
        for alg_name, alg_config in algorithms.items():
            if not alg_config.get("enabled", True):
                continue
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
            # 只传算法参数字段，避免把 enabled/docker_image 等整段 config 塞进 workflow 模板
            _alg_params = {
                "algorithm_name": alg_name,
                "algorithm_config": alg_config.get("parameters", {}),
                "docker_image": docker_image,
                "resources": resources,
            }
            alg_step = Step(
                name=f"algorithm-{alg_name}",
                template=alg_template,
                parameters=_alg_params,
                artifacts={
                    "prepared_data": data_prep_step.outputs.artifacts["prepared_data"],
                },
            )
            algorithm_steps.append(alg_step)
            algorithm_names[alg_step] = alg_name

        if not algorithm_steps:
            raise ValueError("No enabled algorithms found in configuration.")

        preprocessing_eval_step = None
        if prep_eval_cfg:
            prep_eval_op = PreprocessingEvaluationOP()
            prep_eval_template = PythonOPTemplate(prep_eval_op, image=runner_image)
            prep_eval_artifacts = {
                "alignment_output": data_prep_step.outputs.artifacts.get("alignment_output"),
                "denoising_output": data_prep_step.outputs.artifacts.get("denoising_output"),
            }
            prep_eval_artifacts = {k: v for k, v in prep_eval_artifacts.items() if v is not None}
            preprocessing_eval_step = Step(
                name="preprocessing-evaluation",
                template=prep_eval_template,
                parameters={
                    "alignment_metrics": prep_eval_cfg.get("alignment_metrics", ["shift_stability", "cross_correlation_peak"]),
                    "denoising_metrics": prep_eval_cfg.get("denoising_metrics", ["snr_estimate", "local_variance"]),
                    "metrics_output": "/tmp/preprocessing_metrics.json",
                },
                artifacts=prep_eval_artifacts,
            )

        evaluation_steps = []
        for alg_step in algorithm_steps:
            alg_name = algorithm_names[alg_step]
            eval_op = EvaluationOP()
            eval_template = PythonOPTemplate(eval_op, image=runner_image)
            eval_artifacts = {
                "reconstruction": alg_step.outputs.artifacts["reconstruction"],
            }
            if "ground_truth" in data_prep_step.outputs.artifacts:
                eval_artifacts["ground_truth"] = data_prep_step.outputs.artifacts["ground_truth"]
            eval_step = Step(
                name=f"evaluation-{alg_name}",
                template=eval_template,
                parameters={
                    "algorithm_name": alg_name,
                    "metrics": eval_config.get("metrics", ["psnr", "ssim", "mse"]),
                    "metrics_file": f"/tmp/{alg_name}_evaluation.json",
                },
                artifacts=eval_artifacts,
            )
            evaluation_steps.append(eval_step)

        comparison_op = ComparisonOP()
        comparison_template = PythonOPTemplate(comparison_op, image=runner_image)
        comparison_step = Step(
            name="comparison-report",
            template=comparison_template,
            parameters={
                "algorithm_names": [algorithm_names[alg_step] for alg_step in algorithm_steps],
            },
            artifacts={
                "metrics_files": [step.outputs.artifacts["metrics_file"] for step in evaluation_steps],
            },
        )

        export_op = ExportResultsOP()
        export_template = PythonOPTemplate(export_op, image=runner_image)
        export_artifacts = {
            "prepared_data": data_prep_step.outputs.artifacts["prepared_data"],
            "reconstructions": [step.outputs.artifacts["reconstruction"] for step in algorithm_steps],
            "reconstruction_npys": [step.outputs.artifacts["reconstruction_npy"] for step in algorithm_steps],
            "metrics_files": [step.outputs.artifacts["metrics_file"] for step in evaluation_steps],
            "comparison_report": comparison_step.outputs.artifacts["comparison_report"],
            "comparison_json": comparison_step.outputs.artifacts["comparison_json"],
            "visualizations": comparison_step.outputs.artifacts["visualizations"],
        }
        if "ground_truth" in data_prep_step.outputs.artifacts:
            export_artifacts["ground_truth"] = data_prep_step.outputs.artifacts["ground_truth"]
        steps_before_export = [data_prep_step] + algorithm_steps + evaluation_steps + [comparison_step]
        if preprocessing_eval_step is not None:
            steps_before_export.append(preprocessing_eval_step)
            export_artifacts["preprocessing_metrics_file"] = preprocessing_eval_step.outputs.artifacts["preprocessing_metrics_file"]
        export_step = Step(
            name="export-results",
            template=export_template,
            parameters={
                "algorithm_names": [algorithm_names[alg_step] for alg_step in algorithm_steps],
            },
            artifacts=export_artifacts,
        )

        all_steps = steps_before_export + [export_step]
        workflow_name = workflow_config.get("name", "baseline-benchmark")
        workflow_kwargs = {
            "name": workflow_name,
            "steps_name": workflow_name + "-steps",
            "steps_count": len(all_steps),
        }
        print("[et-dflow debug] Workflow(...) args:", workflow_kwargs)
        return Workflow(
            name=workflow_name,
            steps=Steps(name=workflow_name + "-steps", steps=all_steps),
        )

    @staticmethod
    def _normalize_workflow_id(workflow_id: Any) -> str:
        """Extract workflow id string from dflow submit return values."""
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
    
    def submit(self) -> str:
        """
        Submit workflow to dflow server.
        
        Returns:
            Workflow ID
        """
        workflow = self.build_workflow()
        # Print only safe, small config summary (no secrets, no full workflow payload).
        from dflow import config as dflow_config
        submit_view = {
            "host": dflow_config.get("host"),
            "namespace": dflow_config.get("namespace"),
        }
        print("[et-dflow debug] submit() input:", submit_view)
        submit_result = workflow.submit()
        workflow_id = self._normalize_workflow_id(submit_result)
        self._submitted_workflow = workflow
        self._submitted_workflow_id = workflow_id
        return workflow_id
    
    def wait(self, workflow_id: str, timeout: Optional[int] = None):
        """
        Wait for workflow to complete.
        
        Args:
            workflow_id: Workflow ID
            timeout: Timeout in seconds (reserved; dflow Workflow.wait may not support it in all versions)
        """
        from dflow import Workflow
        wid = self._normalize_workflow_id(workflow_id)
        print("[et-dflow debug] Workflow.wait() input:", {"id": wid})
        print("[et-dflow debug] wait: dflow will poll Argo (may trigger 414 on gateway GET URI)")
        if self._submitted_workflow is not None and self._submitted_workflow_id == wid:
            workflow = self._submitted_workflow
        else:
            workflow = Workflow(id=wid)
        workflow.wait()  # dflow Workflow.wait() does not accept timeout in many versions

    def download_results(self, workflow_id: str) -> Path:
        """
        Download results into the local results/<time>/ directory.
        In hybrid mode: download each algorithm step's artifacts, then run evaluation and comparison locally.
        In remote mode: download the export-results archive and unpack it.
        """
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

    def _download_results_hybrid(self, workflow: Workflow) -> Path:
        """Download algorithm outputs and run evaluation/comparison locally."""
        import os
        import shutil
        from tempfile import TemporaryDirectory
        from dflow import download_artifact

        eval_config = self.config.get("evaluation", {})
        metrics_list = eval_config.get("metrics", ["psnr", "ssim", "mse"])

        # Download each algorithm step's outputs
        for alg_name in self._algorithm_names_list:
            steps = workflow.query_step(name=f"algorithm-{alg_name}", phase="Succeeded")
            if not steps:
                continue
            step = steps[-1]
            alg_dir = self._run_output_dir / alg_name
            alg_dir.mkdir(parents=True, exist_ok=True)
            for key, target_name in (("reconstruction", "reconstruction.hspy"), ("reconstruction_npy", "reconstruction.npy")):
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

        # Copy local prep outputs to results/data/
        data_dir = self._run_output_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        if self._local_prepared_data_path and os.path.exists(self._local_prepared_data_path):
            shutil.copy2(self._local_prepared_data_path, data_dir / "prepared_data.hspy")
        if self._local_ground_truth_path and os.path.exists(self._local_ground_truth_path):
            shutil.copy2(self._local_ground_truth_path, data_dir / "prepared_data_ground_truth.hspy")

        # Run evaluation locally for each algorithm
        eval_op = EvaluationOP()
        for alg_name in self._algorithm_names_list:
            recon_path = self._run_output_dir / alg_name / "reconstruction.hspy"
            if not recon_path.exists():
                continue
            metrics_file = self._run_output_dir / alg_name / "evaluation.json"
            op_in = OPIO({
                "reconstruction": str(recon_path),
                "metrics": metrics_list,
                "algorithm_name": alg_name,
                "metrics_file": str(metrics_file),
            })
            if self._local_ground_truth_path and os.path.exists(self._local_ground_truth_path):
                op_in["ground_truth"] = self._local_ground_truth_path
            eval_op.execute(op_in)

        # Run comparison locally
        metrics_files = [str(self._run_output_dir / a / "evaluation.json") for a in self._algorithm_names_list]
        existing = [p for p in metrics_files if os.path.exists(p)]
        if existing:
            comp_op = ComparisonOP()
            comp_out = comp_op.execute(OPIO(
                metrics_files=existing,
                algorithm_names=self._algorithm_names_list,
            ))
            for name, path_key in (("comparison_report", "comparison_report.html"), ("comparison_json", "comparison_summary.json")):
                src = comp_out.get(name)
                if src and os.path.exists(src):
                    shutil.copy2(src, self._run_output_dir / path_key)

        return self._run_output_dir

    def _download_results_remote(self, workflow: Workflow) -> Path:
        """Download export-results archive and unpack."""
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
        """
        Get workflow status.
        
        Args:
            workflow_id: Workflow ID
        
        Returns:
            Workflow status
        """
        from dflow import Workflow
        wid = self._normalize_workflow_id(workflow_id)
        if self._submitted_workflow is not None and self._submitted_workflow_id == wid:
            workflow = self._submitted_workflow
        else:
            workflow = Workflow(id=wid)
        return workflow.query_status()

