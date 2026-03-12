"""
dflow workflow for baseline benchmark.

Executes multiple algorithms in parallel Docker containers and evaluates results.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from dflow import Workflow, Step, Steps, upload_artifact
from dflow.plugins.dispatcher import PythonOPTemplate
from et_dflow.infrastructure.workflows.ops.data_preparation_op import DataPreparationOP
from et_dflow.infrastructure.workflows.ops.algorithm_execution_op import AlgorithmExecutionOP
from et_dflow.infrastructure.workflows.ops.evaluation_op import EvaluationOP
from et_dflow.infrastructure.workflows.ops.comparison_op import ComparisonOP
from et_dflow.infrastructure.workflows.ops.export_results_op import ExportResultsOP
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
        dflow_section = config.get("dflow") or {}
        configure_dflow(
            dflow_section=dflow_section,
            workflow_output_dir=output_dir,
            run_dir=None,
        )
    
    def build_workflow(self) -> Workflow:
        """
        Build dflow workflow.
        
        Returns:
            dflow Workflow object
        """
        # Extract configuration
        datasets = self.config.get("datasets", {})
        algorithms = self.config.get("algorithms", {})
        eval_config = self.config.get("evaluation", {})
        workflow_config = self.config.get("workflow", {})

        # Get first dataset
        dataset_name = list(datasets.keys())[0] if datasets else "default"
        dataset_config = datasets.get(dataset_name, {})
        dataset_path = dataset_config.get("path")
        
        # Runner image for non-algorithm steps in remote cluster mode
        runner_image = workflow_config.get("runner_image") or workflow_config.get("default_image")
        if not runner_image:
            raise ValueError(
                "workflow.runner_image (or workflow.default_image) is required in remote cluster mode."
            )

        dataset_artifact = upload_artifact(dataset_path)
        ground_truth_path = dataset_config.get("ground_truth_path") or eval_config.get("ground_truth_path")
        ground_truth_artifact = upload_artifact(ground_truth_path) if ground_truth_path else None
        
        # Step 1: Data Preparation (wrap in PythonOPTemplate so template has .inputs/.outputs)
        data_prep_op = DataPreparationOP()
        data_prep_template = PythonOPTemplate(data_prep_op, image=runner_image)
        data_prep_step = Step(
            name="data-preparation",
            template=data_prep_template,
            parameters={
                "dataset_format": dataset_config.get("format", "hyperspy"),
                "prepared_data": "/tmp/prepared_data.hspy",
            },
            artifacts={
                "dataset_path": dataset_artifact,
                **({"ground_truth_path": ground_truth_artifact} if ground_truth_artifact else {}),
            },
        )
        
        # Step 2: Algorithm Execution (parallel steps)
        algorithm_steps = []
        algorithm_names = {}  # Map step to algorithm name
        for alg_name, alg_config in algorithms.items():
            if not alg_config.get("enabled", True):
                continue
            
            # Get Docker image
            docker_image = alg_config.get("docker_image")
            if not docker_image:
                raise ValueError(f"Algorithm {alg_name} missing docker_image in config")
            
            # Get resources
            resources = alg_config.get("resources", {})
            
            # Create OP instance
            alg_op = AlgorithmExecutionOP()
            
            # Wrap OP with PythonOPTemplate to specify Docker image
            # This ensures the OP executes in the specified Docker container
            alg_template = PythonOPTemplate(
                alg_op,
                image=docker_image,
                # Set resource limits if provided
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
                artifacts={
                    "prepared_data": data_prep_step.outputs.artifacts["prepared_data"],
                },
            )
            algorithm_steps.append(alg_step)
            algorithm_names[alg_step] = alg_name  # Store mapping

        if not algorithm_steps:
            raise ValueError("No enabled algorithms found in configuration.")
        
        # Step 3: Evaluation (for each algorithm) (wrap in PythonOPTemplate so template has .inputs/.outputs)
        evaluation_steps = []
        for alg_step in algorithm_steps:
            alg_name = algorithm_names[alg_step]  # Get algorithm name from mapping
            
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
        
        # Step 4: Comparison and Report (aggregate all evaluations) (wrap in PythonOPTemplate so template has .inputs/.outputs)
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

        # Step 5: Export final bundle for local download
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
        export_step = Step(
            name="export-results",
            template=export_template,
            parameters={
                "algorithm_names": [algorithm_names[alg_step] for alg_step in algorithm_steps],
            },
            artifacts=export_artifacts,
        )
        
        # Build workflow (dflow Workflow expects steps to be a Steps object, not a list)
        all_steps = [data_prep_step] + algorithm_steps + evaluation_steps + [comparison_step, export_step]
        workflow_name = workflow_config.get("name", "baseline-benchmark")
        workflow = Workflow(
            name=workflow_name,
            steps=Steps(name=workflow_name + "-steps", steps=all_steps),
        )
        
        return workflow

    @staticmethod
    def _normalize_workflow_id(workflow_id: Any) -> str:
        """Extract workflow id string from dflow submit return values."""
        if isinstance(workflow_id, list) and workflow_id:
            workflow_id = workflow_id[0]
        if isinstance(workflow_id, dict):
            workflow_id = workflow_id.get("id") or workflow_id.get("uid")
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
        workflow_id = workflow.submit()
        return self._normalize_workflow_id(workflow_id)
    
    def wait(self, workflow_id: str, timeout: Optional[int] = None):
        """
        Wait for workflow to complete.
        
        Args:
            workflow_id: Workflow ID
            timeout: Timeout in seconds (reserved; dflow Workflow.wait may not support it in all versions)
        """
        from dflow import Workflow
        workflow = Workflow(id=self._normalize_workflow_id(workflow_id))
        workflow.wait()  # dflow Workflow.wait() does not accept timeout in many versions

    def download_results(self, workflow_id: str) -> Path:
        """
        Download the exported results archive from the finished workflow and
        unpack it into the local results/<time>/ directory.

        Returns:
            Local results directory path.
        """
        import tarfile
        from tempfile import TemporaryDirectory
        from dflow import Workflow, download_artifact

        workflow = Workflow(id=self._normalize_workflow_id(workflow_id))
        steps = workflow.query_step(name="export-results", phase="Succeeded")
        if not steps:
            raise RuntimeError("Could not find succeeded 'export-results' step to download results from.")

        export_step = steps[-1]
        archive_artifact = export_step.outputs.artifacts["results_archive"]

        self._run_output_dir.mkdir(parents=True, exist_ok=True)
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
        workflow = Workflow(id=self._normalize_workflow_id(workflow_id))
        return workflow.query_status()

