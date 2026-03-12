"""
Docker image validator.

Validates Docker images before workflow execution to ensure
they are available and can be run.
"""

import subprocess
import time
from typing import Tuple, Optional
from pathlib import Path
from et_dflow.core.exceptions import ETDflowError


class DockerValidationError(ETDflowError):
    """
    Docker image validation errors.
    
    Raised when Docker image validation fails.
    """
    pass


class DockerImageValidator:
    """
    Validator for Docker images.
    
    Checks if Docker images exist locally, can be pulled,
    and can be executed successfully.
    """
    
    def __init__(self, timeout: int = 30, pull_if_missing: bool = True):
        """
        Initialize Docker image validator.
        
        Args:
            timeout: Timeout in seconds for validation operations
            pull_if_missing: Whether to pull image if not found locally
        """
        self.timeout = timeout
        self.pull_if_missing = pull_if_missing
    
    def check_docker_available(self) -> Tuple[bool, Optional[str]]:
        """
        Check if Docker is available and accessible.
        
        Returns:
            (is_available, error_message)
        """
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Also check if Docker daemon is running
                daemon_result = subprocess.run(
                    ["docker", "info"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if daemon_result.returncode != 0:
                    return False, "Docker is installed but daemon is not running. Start Docker daemon and try again"
                return True, None
            else:
                return False, "Docker command failed"
        except FileNotFoundError:
            return False, "Docker is not installed or not in PATH. Install Docker and ensure it's in your PATH"
        except subprocess.TimeoutExpired:
            return False, "Docker command timed out. Docker may be unresponsive"
        except Exception as e:
            return False, f"Docker check failed: {str(e)}"
    
    def check_image_exists(self, image_name: str) -> bool:
        """
        Check if Docker image exists locally.
        
        Args:
            image_name: Docker image name (e.g., "et-dflow/wbp:latest")
        
        Returns:
            True if image exists locally, False otherwise
        """
        try:
            result = subprocess.run(
                ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                images = result.stdout.strip().split("\n")
                return image_name in images
            return False
        except Exception:
            return False
    
    def pull_image(self, image_name: str) -> Tuple[bool, Optional[str]]:
        """
        Pull Docker image from registry.
        
        Supports both public and private registries. For private registries,
        ensure you are logged in using `docker login <registry>`.
        
        Args:
            image_name: Docker image name to pull (e.g., "registry.dp.tech/davinci/genfire-python:tag")
        
        Returns:
            (success, error_message)
        """
        try:
            # Extract registry from image name for better error messages
            registry = image_name.split('/')[0] if '/' in image_name else "docker.io"
            
            result = subprocess.run(
                ["docker", "pull", image_name],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            if result.returncode == 0:
                return True, None
            else:
                error_msg = result.stderr.strip() or result.stdout.strip()
                # Provide more helpful error messages
                if "unauthorized" in error_msg.lower() or "authentication required" in error_msg.lower():
                    return False, f"Authentication failed for registry '{registry}'. Please login: docker login {registry}"
                elif "not found" in error_msg.lower() or "manifest unknown" in error_msg.lower():
                    return False, f"Image not found in registry: {image_name}. Verify the image name and tag are correct"
                elif "network" in error_msg.lower() or "connection" in error_msg.lower():
                    return False, f"Network error while pulling image from '{registry}'. Check your internet connection and registry accessibility"
                elif "denied" in error_msg.lower() or "forbidden" in error_msg.lower():
                    return False, f"Access denied to registry '{registry}'. Check your permissions and authentication"
                else:
                    return False, f"Failed to pull image: {error_msg}"
        except subprocess.TimeoutExpired:
            return False, f"Image pull timed out after {self.timeout} seconds. The image may be large or network is slow"
        except FileNotFoundError:
            return False, "Docker command not found. Please ensure Docker is installed and in PATH"
        except Exception as e:
            return False, f"Unexpected error pulling image: {str(e)}"
    
    def test_image(self, image_name: str) -> Tuple[bool, Optional[str]]:
        """
        Test if Docker image can be run.
        
        Runs a simple test command to verify the image is functional.
        
        Args:
            image_name: Docker image name to test
        
        Returns:
            (is_valid, error_message)
        """
        try:
            # Test by running python --version in the container
            # This verifies the image can start and has Python available
            result = subprocess.run(
                [
                    "docker", "run", "--rm",
                    image_name,
                    "python", "--version"
                ],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            if result.returncode == 0:
                return True, None
            else:
                error_msg = result.stderr.strip() or result.stdout.strip()
                # Provide more helpful error messages
                if "permission denied" in error_msg.lower():
                    return False, f"Permission denied. You may need to run with sudo or add user to docker group"
                elif "cannot connect" in error_msg.lower():
                    return False, f"Cannot connect to Docker daemon. Is Docker running?"
                elif "no such file" in error_msg.lower() or "executable file not found" in error_msg.lower():
                    return False, f"Image appears corrupted or missing required files. Try rebuilding the image"
                else:
                    return False, f"Image test failed: {error_msg}"
        except subprocess.TimeoutExpired:
            return False, f"Image test timed out after {self.timeout} seconds. The image may be slow to start"
        except FileNotFoundError:
            return False, "Docker command not found. Please ensure Docker is installed and in PATH"
        except Exception as e:
            return False, f"Unexpected error testing image: {str(e)}"
    
    def validate_image(
        self,
        image_name: str,
        pull_if_missing: Optional[bool] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate Docker image is available and can be run.
        
        This method:
        1. Checks if Docker is available
        2. Checks if image exists locally
        3. Pulls image if missing and pull_if_missing is True
        4. Tests image by running a simple command
        
        Args:
            image_name: Docker image name to validate
            pull_if_missing: Whether to pull if missing (overrides instance default)
        
        Returns:
            (is_valid, error_message)
        """
        # Check Docker availability
        docker_available, docker_error = self.check_docker_available()
        if not docker_available:
            return False, f"Docker is not available: {docker_error}"
        
        # Use instance default if not specified
        should_pull = pull_if_missing if pull_if_missing is not None else self.pull_if_missing
        
        # Check if image exists locally
        image_exists = self.check_image_exists(image_name)
        
        if not image_exists:
            if should_pull:
                # Try to pull the image
                pull_success, pull_error = self.pull_image(image_name)
                if not pull_success:
                    return False, pull_error
            else:
                return False, f"Image not found locally and pull_if_missing is False: {image_name}"
        
        # Test the image
        test_success, test_error = self.test_image(image_name)
        if not test_success:
            return False, test_error
        
        return True, None
    
    def validate_images(
        self,
        image_names: list[str],
        pull_if_missing: Optional[bool] = None
    ) -> Tuple[dict[str, Tuple[bool, Optional[str]]], bool]:
        """
        Validate multiple Docker images.
        
        Args:
            image_names: List of Docker image names to validate
            pull_if_missing: Whether to pull if missing
        
        Returns:
            (validation_results, all_valid)
            validation_results: dict mapping image_name to (is_valid, error_message)
            all_valid: True if all images are valid
        """
        results = {}
        for image_name in image_names:
            is_valid, error = self.validate_image(image_name, pull_if_missing)
            results[image_name] = (is_valid, error)
        
        all_valid = all(is_valid for is_valid, _ in results.values())
        return results, all_valid

