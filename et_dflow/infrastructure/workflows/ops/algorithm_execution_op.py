"""
dflow OP for algorithm execution.

Executes reconstruction algorithms in Docker containers.
"""

import subprocess
from pathlib import Path
from typing import Dict, Any, List

from dflow.python import OP, OPIO, Parameter, Artifact
from et_dflow.core.exceptions import AlgorithmError


class AlgorithmExecutionOP(OP):
    """
    dflow OP for algorithm execution.
    
    Executes reconstruction algorithms in Docker containers.
    """
    
    def __init__(self):
        """Initialize algorithm execution OP."""
        pass
    
    @classmethod
    def get_input_sign(cls):
        """Get input signature (use dflow.python.Artifact with type for OPIO)."""
        return OPIO({
            "prepared_data": Artifact(str),
            "algorithm_name": Parameter(str),
            "algorithm_config": Parameter(dict, default={}),
            "docker_image": Parameter(str),
            "resources": Parameter(dict, default={}),
        })
    
    @classmethod
    def get_output_sign(cls):
        """Get output signature (use dflow.python.Artifact with type for OPIO)."""
        return OPIO({
            "reconstruction": Artifact(str),
            "reconstruction_npy": Artifact(str),
            "execution_metadata": Artifact(str),
        })
    
    @OP.exec_sign_check
    def execute(self, op_in: OPIO) -> OPIO:
        """
        Execute algorithm in Docker container.
        
        This OP executes the algorithm by calling the Docker container's
        run_algorithm.py script. The Docker image should be specified in
        the workflow Step using PythonOPTemplate with image parameter.
        
        Args:
            op_in: Input OPIO
        
        Returns:
            Output OPIO with reconstruction result
        """
        import copy
        import time
        import json
        import resource
        
        prepared_data = op_in["prepared_data"]
        algorithm_name = op_in["algorithm_name"]
        algorithm_config = dict(op_in.get("algorithm_config") or {})
        docker_image = op_in["docker_image"]
        resources = op_in.get("resources", {})
        runtime_profile = algorithm_config.get("runtime_profile") or {}
        backend = str(
            algorithm_config.get("backend")
            or runtime_profile.get("backend")
            or "cpu_sirt"
        ).strip()
        execution_policy = algorithm_config.get("execution_policy") or {}
        if not isinstance(execution_policy, dict):
            execution_policy = {}
        if not isinstance(runtime_profile, dict):
            runtime_profile = {}

        active_config = self._merge_runtime_profile(algorithm_config, runtime_profile, backend)
        dataset_key = (
            str(op_in.get("dataset_key") or "").strip()
            or str(active_config.get("_et_dflow_dataset_key") or "").strip()
            or str(algorithm_config.get("_et_dflow_dataset_key") or "").strip()
        )
        dataset_metadata = dict(
            op_in.get("dataset_metadata")
            or active_config.get("_et_dflow_dataset_metadata")
            or algorithm_config.get("_et_dflow_dataset_metadata")
            or {}
        )

        try:
            execution_attempts: List[Dict[str, Any]] = []
            max_retries = int(execution_policy.get("max_retries", 1 if backend == "astra_gpu_sirt" else 0))

            result: subprocess.CompletedProcess[str] | None = None
            selected_backend = backend
            fallback_used = False
            for attempt_idx in range(max_retries + 1):
                selected_backend = str(active_config.get("backend") or selected_backend or "cpu_sirt")
                out_ext = str(
                    active_config.get("reconstruction_output_extension")
                    or "hspy"
                ).lstrip(".")
                rel = Path(dataset_key) / algorithm_name if dataset_key else Path(algorithm_name)
                output_dir = Path("/tmp/output") / rel
                self._reset_output_dir(output_dir)
                reconstruction_path = output_dir / f"reconstruction.{out_ext}"
                metadata_path = output_dir / "metadata.json"

                command = self._build_command(
                    config=active_config,
                    prepared_data=str(prepared_data),
                    reconstruction_path=str(reconstruction_path),
                )
                env = self._build_env(active_config)
                env.setdefault("ET_DFLOW_NONINTERACTIVE", "1")
                print(
                    f"Executing algorithm {algorithm_name} backend={selected_backend} "
                    f"attempt={attempt_idx + 1} image={docker_image}"
                )
                print(f"Command: {' '.join(command)}")
                t0 = time.time()
                result = subprocess.run(
                    command,
                    cwd="/tmp",
                    capture_output=True,
                    text=True,
                    check=False,
                    env=env,
                    stdin=subprocess.DEVNULL,
                )
                elapsed_s = time.time() - t0
                attempt_rec = {
                    "attempt": attempt_idx + 1,
                    "backend": selected_backend,
                    "return_code": result.returncode,
                    "duration_seconds": elapsed_s,
                    "oom_detected": self._is_oom_failure(result),
                }
                execution_attempts.append(attempt_rec)
                if result.returncode == 0:
                    break
                if not attempt_rec["oom_detected"]:
                    break
                fallback_cfg = self._prepare_oom_fallback_config(
                    active_config=active_config,
                    policy=execution_policy,
                )
                if fallback_cfg is None:
                    break
                fallback_used = True
                active_config = fallback_cfg
                print(
                    f"OOM detected for {algorithm_name}; retry with backend="
                    f"{active_config.get('backend')}"
                )

            if result is None:
                raise AlgorithmError(
                    "Algorithm execution did not start",
                    details={"algorithm": algorithm_name, "docker_image": docker_image},
                )
            if result.returncode != 0:
                error_msg = f"Algorithm execution failed with return code {result.returncode}"
                if result.stderr:
                    error_msg += f"\nStderr: {result.stderr}"
                if result.stdout:
                    error_msg += f"\nStdout: {result.stdout}"
                raise AlgorithmError(
                    error_msg,
                    details={
                        "algorithm": algorithm_name,
                        "backend": selected_backend,
                        "docker_image": docker_image,
                        "return_code": result.returncode,
                        "attempts": execution_attempts,
                    }
                )
            
            resolved_recon = self._resolve_reconstruction_file(output_dir, reconstruction_path)
            if not resolved_recon.exists():
                raise AlgorithmError(
                    f"Reconstruction output not found under {output_dir} (expected {reconstruction_path.name})",
                    details={"algorithm": algorithm_name, "output_dir": str(output_dir)},
                )

            # Load reconstruction result and save in multiple formats
            import hyperspy.api as hs
            import numpy as np

            reconstruction_signal = hs.load(str(resolved_recon))

            hspy_path = output_dir / "reconstruction.hspy"
            if resolved_recon.resolve() != hspy_path.resolve():
                if hspy_path.exists():
                    hspy_path.unlink()
                reconstruction_signal.save(str(hspy_path))
            hspy_artifact = str(hspy_path if hspy_path.exists() else resolved_recon)

            # Save as .npy format (pure numpy array for other tools)
            npy_path = output_dir / "reconstruction.npy"
            np.save(str(npy_path), reconstruction_signal.data)
            
            # Create execution metadata
            execution_metadata = {
                "algorithm": algorithm_name,
                "backend": selected_backend,
                "runtime_profile": runtime_profile,
                "dataset_key": dataset_key or None,
                "dataset_metadata": dataset_metadata,
                "config": active_config,
                "docker_image": docker_image,
                "resources": resources,
                "attempts": execution_attempts,
                "fallback_used": fallback_used,
                "peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0,
                "output_path": hspy_artifact,
                "npy_path": str(npy_path),
            }
            
            # Save metadata (optional, for debugging/logging)
            with open(metadata_path, "w") as f:
                json.dump(execution_metadata, f, indent=2)
            
            return OPIO({
                "reconstruction": hspy_artifact,  # Main output as .hspy
                "reconstruction_npy": str(npy_path),  # Additional npy output
                "execution_metadata": str(metadata_path),  # Path to metadata.json (Artifact expects str)
            })
        except subprocess.CalledProcessError as e:
            raise AlgorithmError(
                f"Algorithm execution failed: {e}",
                details={
                    "algorithm": algorithm_name,
                    "docker_image": docker_image,
                    "error": str(e)
                }
            ) from e
        except Exception as e:
            raise AlgorithmError(
                f"Algorithm execution failed: {e}",
                details={
                    "algorithm": algorithm_name,
                    "docker_image": docker_image,
                    "error": str(e)
                }
            ) from e

    @staticmethod
    def _reset_output_dir(output_dir: Path) -> None:
        """Remove the per-step output tree so container scripts never see stale files (no overwrite prompts)."""
        import shutil

        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _resolve_reconstruction_file(output_dir: Path, expected: Path) -> Path:
        if expected.is_file():
            return expected
        for p in sorted(output_dir.glob("reconstruction.*")):
            if p.is_file() and p.suffix.lower() in {
                ".hspy", ".h5", ".hdf5", ".h5py", ".mrc", ".emi", ".npy",
            }:
                return p
        return expected

    @staticmethod
    def _merge_runtime_profile(
        algorithm_config: Dict[str, Any],
        runtime_profile: Dict[str, Any],
        backend: str,
    ) -> Dict[str, Any]:
        merged = dict(algorithm_config or {})
        profile_cfg = dict(runtime_profile or {})
        for key, val in profile_cfg.items():
            merged.setdefault(key, val)
        merged["backend"] = backend
        return merged

    @staticmethod
    def _build_command(config: Dict[str, Any], prepared_data: str, reconstruction_path: str) -> List[str]:
        import json
        import shlex

        command_template = config.get("command_template")
        entrypoint_override = config.get("entrypoint")
        if command_template:
            command_str = command_template.format(
                input=prepared_data,
                output=reconstruction_path,
                config=json.dumps(config),
            )
            return shlex.split(command_str)
        if entrypoint_override:
            return [
                entrypoint_override,
                "--input", prepared_data,
                "--output", reconstruction_path,
                "--config", json.dumps(config),
            ]
        return [
            "python",
            "/app/run_algorithm.py",
            "--input", prepared_data,
            "--output", reconstruction_path,
            "--config", json.dumps(config),
        ]

    @staticmethod
    def _build_env(config: Dict[str, Any]) -> Dict[str, str]:
        import os

        env = os.environ.copy()
        threads = config.get("threads")
        if threads is not None:
            try:
                t = str(int(threads))
                env["OMP_NUM_THREADS"] = t
                env["MKL_NUM_THREADS"] = t
                env["OPENBLAS_NUM_THREADS"] = t
            except (TypeError, ValueError):
                pass
        return env

    @staticmethod
    def _is_oom_failure(result: "subprocess.CompletedProcess[str]") -> bool:
        text = f"{result.stdout or ''}\n{result.stderr or ''}".lower()
        if result.returncode in (137, 143):
            return True
        markers = (
            "out of memory",
            "cuda out of memory",
            "oom-kill",
            "oom killed",
            "memoryerror",
            "std::bad_alloc",
        )
        return any(m in text for m in markers)

    @staticmethod
    def _prepare_oom_fallback_config(
        active_config: Dict[str, Any],
        policy: Dict[str, Any],
    ) -> Dict[str, Any] | None:
        import copy

        fallback_backend = policy.get("oom_fallback_backend", "cpu_sirt")
        if not fallback_backend:
            return None
        fallback_overrides = policy.get("oom_fallback_overrides") or {}
        if not isinstance(fallback_overrides, dict):
            fallback_overrides = {}
        new_cfg = copy.deepcopy(active_config)
        new_cfg["backend"] = fallback_backend
        if fallback_backend == "cpu_sirt":
            new_cfg["use_native"] = False
        new_cfg.update(fallback_overrides)
        return new_cfg

