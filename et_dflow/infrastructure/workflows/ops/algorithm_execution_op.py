"""
dflow OP for algorithm execution.

Executes reconstruction algorithms in Docker containers.
"""

from typing import Dict, Any
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
            "dataset_key": Parameter(str, default=""),
            "dataset_metadata": Parameter(dict, default={}),
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
        import json
        import subprocess
        from pathlib import Path
        
        prepared_data = op_in["prepared_data"]
        algorithm_name = op_in["algorithm_name"]
        algorithm_config = op_in.get("algorithm_config", {})
        docker_image = op_in["docker_image"]
        resources = op_in.get("resources", {})
        dataset_key = (op_in.get("dataset_key") or "").strip()
        dataset_metadata = op_in.get("dataset_metadata") or {}
        
        try:
            # Prepare output paths (unique per dataset × algorithm on shared workers)
            rel = Path(dataset_key) / algorithm_name if dataset_key else Path(algorithm_name)
            output_dir = Path("/tmp/output") / rel
            output_dir.mkdir(parents=True, exist_ok=True)
            reconstruction_path = output_dir / "reconstruction.hspy"
            metadata_path = output_dir / "metadata.json"
            
            # Prepare execution command
            # Support both standard interface and custom command templates
            # Standard interface: algorithms should accept:
            #   --input: input data path
            #   --output: output reconstruction path
            #   --config: JSON configuration string
            
            # Check if custom command template is provided
            command_template = algorithm_config.get("command_template")
            entrypoint_override = algorithm_config.get("entrypoint")
            
            if command_template:
                # Use custom command template with placeholders
                # Placeholders: {input}, {output}, {config}
                command_str = command_template.format(
                    input=str(prepared_data),
                    output=str(reconstruction_path),
                    config=json.dumps(algorithm_config)
                )
                # Split into command list (handles quoted arguments)
                import shlex
                command = shlex.split(command_str)
            elif entrypoint_override:
                # Use custom entrypoint with standard arguments
                command = [
                    entrypoint_override,
                    "--input", str(prepared_data),
                    "--output", str(reconstruction_path),
                    "--config", json.dumps(algorithm_config),
                ]
            else:
                # Use default standard interface
                command = [
                    "python",
                    "/app/run_algorithm.py",
                    "--input", str(prepared_data),
                    "--output", str(reconstruction_path),
                    "--config", json.dumps(algorithm_config),
                ]
            
            # Remote cluster mode only: this OP already runs inside the algorithm image.
            print(f"Executing algorithm {algorithm_name} in remote container {docker_image}")
            print(f"Command: {' '.join(command)}")
            result = subprocess.run(
                command,
                cwd="/tmp",
                capture_output=True,
                text=True,
                check=False,
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
                        "docker_image": docker_image,
                        "return_code": result.returncode
                    }
                )
            
            # Verify output exists
            if not reconstruction_path.exists():
                raise AlgorithmError(
                    f"Reconstruction output not found: {reconstruction_path}",
                    details={"algorithm": algorithm_name}
                )
            
            # Load reconstruction result and save in multiple formats
            import hyperspy.api as hs
            import numpy as np
            
            reconstruction_signal = hs.load(str(reconstruction_path))
            
            # Save as .hspy (HyperSpy HDF5 format, compatible with ETSpy/HyperSpy)
            hspy_path = output_dir / "reconstruction.hspy"
            reconstruction_signal.save(str(hspy_path))
            
            # Save as .npy format (pure numpy array for other tools)
            npy_path = output_dir / "reconstruction.npy"
            np.save(str(npy_path), reconstruction_signal.data)
            
            # Create execution metadata
            execution_metadata = {
                "algorithm": algorithm_name,
                "dataset_key": dataset_key or None,
                "dataset_metadata": dataset_metadata,
                "config": algorithm_config,
                "docker_image": docker_image,
                "resources": resources,
                "output_path": str(hspy_path),
                "npy_path": str(npy_path),
            }
            
            # Save metadata (optional, for debugging/logging)
            with open(metadata_path, "w") as f:
                json.dump(execution_metadata, f, indent=2)
            
            return OPIO({
                "reconstruction": str(hspy_path),  # Main output as .hspy
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

