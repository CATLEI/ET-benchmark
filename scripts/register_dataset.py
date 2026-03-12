#!/usr/bin/env python3
"""
Dataset Registration Script
Registers a new dataset to the metadata index and validates its structure.
"""

import argparse
import json
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, Any


def load_metadata(dataset_path: Path) -> Dict[str, Any]:
    """Load dataset metadata.yaml file."""
    metadata_path = dataset_path / "metadata.yaml"
    if not metadata_path.exists():
        raise FileNotFoundError(f"metadata.yaml not found at {metadata_path}")
    
    with open(metadata_path, 'r') as f:
        return yaml.safe_load(f)


def validate_dataset_structure(dataset_path: Path) -> bool:
    """Validate that dataset has required files and structure."""
    required_dirs = ['raw']
    required_files = [
        'raw/tilt_series.hspy',  # At least one format should exist
        'metadata.yaml'
    ]
    
    errors = []
    
    # Check required directories
    for dir_name in required_dirs:
        dir_path = dataset_path / dir_name
        if not dir_path.exists():
            errors.append(f"Missing required directory: {dir_name}")
    
    # Check required files (at least one tilt_series format)
    tilt_series_found = False
    for ext in ['.hspy', '.mrc', '.tiff', '.tif', '.h5']:
        if (dataset_path / f"raw/tilt_series{ext}").exists():
            tilt_series_found = True
            break
    
    if not tilt_series_found:
        errors.append("Missing tilt_series file (raw/tilt_series.{hspy|mrc|tiff|h5})")
    
    # Check metadata.yaml
    if not (dataset_path / "metadata.yaml").exists():
        errors.append("Missing metadata.yaml")
    
    if errors:
        print("Validation errors:")
        for error in errors:
            print(f"  - {error}")
        return False
    
    return True


def update_index(dataset_path: Path, metadata: Dict[str, Any], index_path: Path):
    """Update the dataset index with new dataset information."""
    # Load existing index
    if index_path.exists():
        with open(index_path, 'r') as f:
            index = json.load(f)
    else:
        index = {
            "version": "1.0",
            "last_updated": "",
            "datasets": {},
            "statistics": {
                "total_datasets": 0,
                "by_type": {"simulated": 0, "experimental": 0},
                "by_ground_truth": {"with_gt": 0, "without_gt": 0},
                "by_missing_wedge": {"small": 0, "medium": 0, "large": 0}
            }
        }
    
    # Calculate relative path from data/ directory
    data_dir = index_path.parent.parent
    rel_path = dataset_path.relative_to(data_dir)
    
    # Extract quality metrics
    quality_metrics = metadata.get('quality_metrics', {})
    missing_wedge = quality_metrics.get('missing_wedge_angle', 0)
    
    # Categorize missing wedge
    if missing_wedge < 60:
        wedge_category = "small"
    elif missing_wedge < 120:
        wedge_category = "medium"
    else:
        wedge_category = "large"
    
    # Add dataset to index
    dataset_id = metadata.get('dataset_id', dataset_path.name)
    index['datasets'][dataset_id] = {
        "path": str(rel_path),
        "type": metadata.get('type', 'unknown'),
        "has_ground_truth": metadata.get('data_files', {}).get('ground_truth', {}).get('available', False),
        "size_mb": 0.0,  # Will be calculated
        "tags": [metadata.get('type', 'unknown')],
        "quality_metrics": {
            "snr": quality_metrics.get('snr', 0.0),
            "missing_wedge_angle": missing_wedge,
            "data_completeness": quality_metrics.get('data_completeness', 0.0)
        },
        "metadata_path": str(rel_path / "metadata.yaml")
    }
    
    # Update statistics
    index['statistics']['total_datasets'] = len(index['datasets'])
    
    # Count by type
    type_counts = {"simulated": 0, "experimental": 0}
    for ds in index['datasets'].values():
        ds_type = ds.get('type', 'unknown')
        if ds_type in type_counts:
            type_counts[ds_type] += 1
    index['statistics']['by_type'] = type_counts
    
    # Count by ground truth
    gt_counts = {"with_gt": 0, "without_gt": 0}
    for ds in index['datasets'].values():
        if ds.get('has_ground_truth', False):
            gt_counts['with_gt'] += 1
        else:
            gt_counts['without_gt'] += 1
    index['statistics']['by_ground_truth'] = gt_counts
    
    # Count by missing wedge
    wedge_counts = {"small": 0, "medium": 0, "large": 0}
    for ds in index['datasets'].values():
        wedge_angle = ds.get('quality_metrics', {}).get('missing_wedge_angle', 0)
        if wedge_angle < 60:
            wedge_counts['small'] += 1
        elif wedge_angle < 120:
            wedge_counts['medium'] += 1
        else:
            wedge_counts['large'] += 1
    index['statistics']['by_missing_wedge'] = wedge_counts
    
    # Update timestamp
    index['last_updated'] = datetime.now().isoformat()
    
    # Save index
    with open(index_path, 'w') as f:
        json.dump(index, f, indent=2)
    
    print(f"✓ Updated index: {index_path}")
    print(f"  Total datasets: {index['statistics']['total_datasets']}")


def main():
    parser = argparse.ArgumentParser(description="Register a dataset to the metadata index")
    parser.add_argument("dataset_path", type=Path, help="Path to dataset directory")
    parser.add_argument("--index", type=Path, default=None, help="Path to index.json (default: data/metadata/index.json)")
    
    args = parser.parse_args()
    
    dataset_path = Path(args.dataset_path).resolve()
    if not dataset_path.exists():
        print(f"Error: Dataset path does not exist: {dataset_path}")
        return 1
    
    # Determine index path
    if args.index:
        index_path = Path(args.index).resolve()
    else:
        # Assume dataset_path is relative to data/ directory
        data_dir = dataset_path.parent.parent if dataset_path.name.endswith('_v1') else dataset_path.parent.parent.parent
        index_path = data_dir / "metadata" / "index.json"
    
    print(f"Registering dataset: {dataset_path}")
    print(f"Index file: {index_path}")
    
    # Validate structure
    if not validate_dataset_structure(dataset_path):
        print("Error: Dataset structure validation failed")
        return 1
    
    # Load metadata
    try:
        metadata = load_metadata(dataset_path)
        print(f"✓ Loaded metadata: {metadata.get('dataset_id', 'unknown')}")
    except Exception as e:
        print(f"Error loading metadata: {e}")
        return 1
    
    # Update index
    try:
        update_index(dataset_path, metadata, index_path)
        print("✓ Dataset registered successfully!")
        return 0
    except Exception as e:
        print(f"Error updating index: {e}")
        return 1


if __name__ == "__main__":
    exit(main())

