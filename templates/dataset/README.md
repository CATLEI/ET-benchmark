# Dataset Directory Template

This is a template for creating a new dataset directory structure.

## Directory Structure

```
{dataset_name}_v{version}/
├── README.md                    # Dataset description
├── metadata.yaml                # Dataset metadata (copy from data/metadata/dataset_template.yaml)
├── raw/                         # Original data
│   ├── tilt_series.hspy        # Tilt series (required)
│   ├── tilt_angles.txt         # Tilt angles (required)
│   └── acquisition_parameters.json  # Optional: acquisition parameters
├── ground_truth/                # Ground truth (if available)
│   ├── volume.hspy             # 3D volume
│   └── README.md               # Ground truth description
├── preprocessing/               # Preprocessed data (optional, use cache/)
│   ├── aligned.hspy
│   └── normalized.hspy
└── annotations/                 # Annotations (optional)
    ├── regions.json
    └── landmarks.json
```

## Steps to Create a New Dataset

1. **Create directory structure**:
   ```bash
   mkdir -p datasets/{type}/{dataset_name}_v1/{raw,ground_truth,preprocessing,annotations}
   ```

2. **Copy metadata template**:
   ```bash
   cp data/metadata/dataset_template.yaml datasets/{type}/{dataset_name}_v1/metadata.yaml
   ```

3. **Fill in metadata.yaml**:
   - Update dataset_id, name, version
   - Fill in experimental_parameters
   - Add sample information
   - Quality metrics can be auto-calculated later

4. **Add data files**:
   - Place tilt_series.hspy in raw/
   - Place tilt_angles.txt in raw/
   - Place ground_truth volume in ground_truth/ (if available)

5. **Calculate quality metrics**:
   ```bash
   python scripts/calculate_quality_metrics.py datasets/{type}/{dataset_name}_v1
   ```

6. **Register dataset**:
   ```bash
   python scripts/register_dataset.py datasets/{type}/{dataset_name}_v1
   ```

## Naming Convention

- Dataset name: `{material}_{sample_type}_v{version}`
- Examples: `au_nanoparticle_v1`, `fept_interface_v2`
- Use lowercase letters and underscores
- Version starts from v1

## Required Files

- `raw/tilt_series.hspy` - Tilt series data (required)
- `raw/tilt_angles.txt` - Tilt angles (required)
- `metadata.yaml` - Dataset metadata (required)

## Optional Files

- `ground_truth/volume.hspy` - Ground truth 3D volume
- `preprocessing/*` - Preprocessed data (should be in cache/)
- `annotations/*` - Annotation files

