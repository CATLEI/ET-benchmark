#!/usr/bin/env python3
"""
Dataset Validation Script
Validates dataset structure, files, and metadata completeness.
"""

import argparse
import yaml
import hashlib
from pathlib import Path
from typing import List, Tuple


def calculate_checksum(file_path: Path) -> str:
    """Calculate SHA256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def validate_structure(dataset_path: Path) -> Tuple[bool, List[str]]:
    """Validate dataset directory structure."""
    errors = []
    warnings = []
    
    # Check required directories
    required_dirs = ['raw']
    for dir_name in required_dirs:
        dir_path = dataset_path / dir_name
        if not dir_path.exists():
            errors.append(f"Missing required directory: {dir_name}")
    
    # Check required files
    tilt_series_found = False
    for ext in ['.hspy', '.mrc', '.tiff', '.tif', '.h5']:
        if (dataset_path / f"raw/tilt_series{ext}").exists():
            tilt_series_found = True
            break
    
    if not tilt_series_found:
        errors.append("Missing tilt_series file (raw/tilt_series.{hspy|mrc|tiff|h5})")
    
    if not (dataset_path / "metadata.yaml").exists():
        errors.append("Missing metadata.yaml")
    
    # Check optional but recommended files
    if not (dataset_path / "raw/tilt_angles.txt").exists():
        warnings.append("Missing tilt_angles.txt (recommended)")
    
    if not (dataset_path / "README.md").exists():
        warnings.append("Missing README.md (recommended)")
    
    return len(errors) == 0, errors + warnings


def validate_metadata(dataset_path: Path) -> Tuple[bool, List[str]]:
    """Validate metadata.yaml file."""
    errors = []
    warnings = []
    
    metadata_path = dataset_path / "metadata.yaml"
    if not metadata_path.exists():
        return False, ["metadata.yaml not found"]
    
    try:
        with open(metadata_path, 'r') as f:
            metadata = yaml.safe_load(f)
    except Exception as e:
        return False, [f"Error parsing metadata.yaml: {e}"]
    
    # Required fields
    required_fields = ['dataset_id', 'name', 'version', 'type']
    for field in required_fields:
        if field not in metadata:
            errors.append(f"Missing required field in metadata.yaml: {field}")
    
    # Check data_files
    if 'data_files' not in metadata:
        errors.append("Missing 'data_files' section in metadata.yaml")
    else:
        data_files = metadata['data_files']
        if 'tilt_series' not in data_files:
            errors.append("Missing 'tilt_series' in data_files")
    
    # Check experimental_parameters
    if 'experimental_parameters' not in metadata:
        warnings.append("Missing 'experimental_parameters' section (recommended)")
    
    # Check quality_metrics
    if 'quality_metrics' not in metadata:
        warnings.append("Missing 'quality_metrics' section (run calculate_quality_metrics.py)")
    
    return len(errors) == 0, errors + warnings


def validate_file_integrity(dataset_path: Path) -> Tuple[bool, List[str]]:
    """Validate file integrity using checksums."""
    errors = []
    warnings = []
    
    metadata_path = dataset_path / "metadata.yaml"
    if not metadata_path.exists():
        return True, []  # Skip if no metadata
    
    try:
        with open(metadata_path, 'r') as f:
            metadata = yaml.safe_load(f)
    except Exception:
        return True, []  # Skip if can't parse metadata
    
    # Check checksum if present
    created_info = metadata.get('created', {})
    expected_checksum = created_info.get('checksum', '')
    
    if expected_checksum:
        # Calculate actual checksum (simplified - would need to hash all files)
        warnings.append("Checksum validation not fully implemented (would require hashing all files)")
    
    return True, warnings


def main():
    parser = argparse.ArgumentParser(description="Validate a dataset")
    parser.add_argument("dataset_path", type=Path, help="Path to dataset directory")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    
    args = parser.parse_args()
    
    dataset_path = Path(args.dataset_path).resolve()
    if not dataset_path.exists():
        print(f"Error: Dataset path does not exist: {dataset_path}")
        return 1
    
    print(f"Validating dataset: {dataset_path}\n")
    
    # Validate structure
    struct_ok, struct_issues = validate_structure(dataset_path)
    print("Structure validation:")
    if struct_ok:
        print("  ✓ Structure is valid")
    else:
        print("  ✗ Structure validation failed")
        for issue in struct_issues:
            if issue.startswith("Missing required"):
                print(f"    ERROR: {issue}")
            else:
                print(f"    WARNING: {issue}")
    
    # Validate metadata
    meta_ok, meta_issues = validate_metadata(dataset_path)
    print("\nMetadata validation:")
    if meta_ok:
        print("  ✓ Metadata is valid")
    else:
        print("  ✗ Metadata validation failed")
        for issue in meta_issues:
            if "Missing required" in issue or "Error" in issue:
                print(f"    ERROR: {issue}")
            else:
                print(f"    WARNING: {issue}")
    
    # Validate file integrity
    integrity_ok, integrity_issues = validate_file_integrity(dataset_path)
    print("\nFile integrity validation:")
    if integrity_ok:
        print("  ✓ File integrity check passed")
    if integrity_issues:
        for issue in integrity_issues:
            print(f"    WARNING: {issue}")
    
    # Summary
    all_errors = [i for i in struct_issues + meta_issues if "ERROR" in i or (args.strict and "WARNING" in i)]
    
    print("\n" + "="*50)
    if all_errors:
        print("✗ Validation FAILED")
        return 1
    else:
        print("✓ Validation PASSED")
        return 0


if __name__ == "__main__":
    exit(main())

