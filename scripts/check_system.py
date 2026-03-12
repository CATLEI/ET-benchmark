#!/usr/bin/env python3
"""
System check script for ET-dflow.

Checks if the system is ready to run benchmarks.
"""

import sys
import os
from pathlib import Path
from typing import List, Tuple

# Fix encoding for Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def check_python_version() -> Tuple[bool, str]:
    """Check Python version."""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        return True, f"Python {version.major}.{version.minor}.{version.micro} [OK]"
    return False, f"Python {version.major}.{version.minor}.{version.micro} (requires >= 3.8)"

def check_dependencies() -> List[Tuple[bool, str]]:
    """Check if required dependencies are installed."""
    results = []
    required_packages = [
        ("numpy", "numpy"),
        ("scipy", "scipy"),
        ("hyperspy", "hyperspy"),
        ("pydantic", "pydantic"),
        ("yaml", "pyyaml"),
        ("dflow", "dflow"),
        ("click", "click"),
    ]
    
    for module_name, package_name in required_packages:
        try:
            __import__(module_name)
            results.append((True, f"{package_name} [OK]"))
        except ImportError:
            results.append((False, f"{package_name} [MISSING] (not installed)"))
    
    return results

def check_docker() -> Tuple[bool, str]:
    """Check if Docker is available."""
    import subprocess
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            return True, f"{version} [OK]"
        return False, "Docker not found"
    except FileNotFoundError:
        return False, "Docker not installed"
    except Exception as e:
        return False, f"Docker check failed: {e}"

def check_directories() -> List[Tuple[bool, str]]:
    """Check if required directories exist."""
    results = []
    required_dirs = [
        ("results", Path("results")),
        (".cache", Path(".cache")),
        ("logs", Path("logs")),
    ]
    
    for name, path in required_dirs:
        if path.exists() and path.is_dir():
            results.append((True, f"{name}/ directory exists [OK]"))
        else:
            results.append((False, f"{name}/ directory missing [MISSING]"))
    
    return results

def check_config_files() -> List[Tuple[bool, str]]:
    """Check if configuration files exist."""
    results = []
    config_files = [
        ("configs/base.yaml", Path("configs/base.yaml")),
        ("configs/algorithms.yaml", Path("configs/algorithms.yaml")),
        ("configs/datasets.yaml", Path("configs/datasets.yaml")),
    ]
    
    for name, path in config_files:
        if path.exists() and path.is_file():
            results.append((True, f"{name} exists [OK]"))
        else:
            results.append((False, f"{name} missing [MISSING]"))
    
    return results

def check_env_vars() -> List[Tuple[bool, str]]:
    """Check if environment variables are set."""
    results = []
    env_vars = [
        ("DOCKER_REGISTRY", os.getenv("DOCKER_REGISTRY", "localhost")),
        ("DFLOW_HOST", os.getenv("DFLOW_HOST", "http://localhost:2746")),
        ("DFLOW_NAMESPACE", os.getenv("DFLOW_NAMESPACE", "default")),
    ]
    
    for name, value in env_vars:
        if value:
            results.append((True, f"{name}={value} [OK]"))
        else:
            results.append((False, f"{name} not set [MISSING]"))
    
    return results

def check_cli_installation() -> Tuple[bool, str]:
    """Check if CLI is installed."""
    try:
        import subprocess
        result = subprocess.run(
            ["et-dflow", "--help"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return True, "CLI command 'et-dflow' available [OK]"
        return False, "CLI command 'et-dflow' not working [FAILED]"
    except FileNotFoundError:
        return False, "CLI command 'et-dflow' not found (run: pip install -e .) [MISSING]"
    except Exception as e:
        return False, f"CLI check failed: {e}"

def main():
    """Run all checks."""
    print("=" * 60)
    print("ET-dflow System Check")
    print("=" * 60)
    print()
    
    all_passed = True
    
    # Python version
    print("1. Python Environment")
    print("-" * 60)
    passed, msg = check_python_version()
    print(f"  {msg}")
    if not passed:
        all_passed = False
    print()
    
    # Dependencies
    print("2. Python Dependencies")
    print("-" * 60)
    dep_results = check_dependencies()
    for passed, msg in dep_results:
        print(f"  {msg}")
        if not passed:
            all_passed = False
    print()
    
    # Docker
    print("3. Docker Environment")
    print("-" * 60)
    passed, msg = check_docker()
    print(f"  {msg}")
    if not passed:
        all_passed = False
    print()
    
    # Directories
    print("4. Required Directories")
    print("-" * 60)
    dir_results = check_directories()
    for passed, msg in dir_results:
        print(f"  {msg}")
        if not passed:
            all_passed = False
    print()
    
    # Config files
    print("5. Configuration Files")
    print("-" * 60)
    config_results = check_config_files()
    for passed, msg in config_results:
        print(f"  {msg}")
        if not passed:
            all_passed = False
    print()
    
    # Environment variables
    print("6. Environment Variables")
    print("-" * 60)
    env_results = check_env_vars()
    for passed, msg in env_results:
        print(f"  {msg}")
    print()
    
    # CLI
    print("7. CLI Installation")
    print("-" * 60)
    passed, msg = check_cli_installation()
    print(f"  {msg}")
    if not passed:
        all_passed = False
    print()
    
    # Summary
    print("=" * 60)
    if all_passed:
        print("[SUCCESS] All checks passed! System is ready to run.")
    else:
        print("[FAILED] Some checks failed. Please fix the issues above.")
        print("\nNext steps:")
        print("  1. Install missing dependencies: pip install -r requirements.txt")
        print("  2. Install package: pip install -e .")
        print("  3. Set environment variables (see env_template.txt)")
        print("  4. Create missing directories")
    print("=" * 60)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())

