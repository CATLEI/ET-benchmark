# ET-dflow Data Directory

This directory contains all datasets, metadata, and cached data for the ET-dflow benchmark framework.

## Directory Structure

```
data/
├── datasets/                    # Dataset collections
│   ├── simulated/              # Simulated datasets
│   └── experimental/           # Experimental datasets
│       ├── public/             # Public datasets
│       └── private/            # Private datasets
├── metadata/                    # Dataset metadata
│   ├── datasets.yaml           # Dataset configuration
│   ├── index.json              # Dataset index (auto-generated)
│   ├── manifest.yaml          # Dataset manifest
│   └── schemas/                # Metadata schemas
├── cache/                       # Cache directory (not version controlled)
│   ├── preprocessed/           # Preprocessed data
│   └── converted/              # Format-converted data
└── archive/                     # Archived datasets (optional)
```

## Dataset Organization

### Naming Convention

- **Format**: `{material}_{sample_type}_v{version}`
- **Examples**: 
  - `au_nanoparticle_v1`
  - `fept_interface_v2`
  - `walnut_public_v1`

### Dataset Structure

Each dataset follows this structure:

```
{dataset_name}_v{version}/
├── README.md                    # Dataset description
├── metadata.yaml                # Dataset metadata (required)
├── raw/                         # Original data
│   ├── tilt_series.hspy        # Tilt series (required)
│   ├── tilt_angles.txt         # Tilt angles (required)
│   └── acquisition_parameters.json  # Optional
├── ground_truth/                # Ground truth (if available)
│   ├── volume.hspy             # 3D volume
│   └── README.md               # Ground truth description
├── preprocessing/               # Preprocessed data (optional)
└── annotations/                 # Annotations (optional)
```

## Metadata Management

### Quality Metrics (Replaces Complexity)

Instead of subjective complexity levels, datasets use objective quality metrics:

- **SNR** (Signal-to-Noise Ratio): Quantitative measure of data quality
- **Missing Wedge Angle**: Degrees of missing data in Fourier space
- **Data Completeness**: Coverage of tilt series (0-1)
- **Resolution Estimate**: Estimated resolution in nm

These metrics are automatically calculated using `scripts/calculate_quality_metrics.py`.

## Adding a New Dataset

1. **Create directory structure**:
   ```bash
   mkdir -p datasets/{type}/{dataset_name}_v1/{raw,ground_truth}
   ```

2. **Copy metadata template**:
   ```bash
   cp metadata/dataset_template.yaml datasets/{type}/{dataset_name}_v1/metadata.yaml
   ```

3. **Fill in metadata.yaml** with dataset information

4. **Add data files**:
   - Place `tilt_series.{ext}` in `raw/`
   - Place `tilt_angles.txt` in `raw/`
   - Place ground truth in `ground_truth/` (if available)

5. **Calculate quality metrics**:
   ```bash
   python scripts/calculate_quality_metrics.py datasets/{type}/{dataset_name}_v1 --update
   ```

6. **Register dataset**:
   ```bash
   python scripts/register_dataset.py datasets/{type}/{dataset_name}_v1
   ```

7. **Validate dataset**:
   ```bash
   python scripts/validate_dataset.py datasets/{type}/{dataset_name}_v1
   ```

See `docs/DATASET_ADDING_GUIDE.md` for detailed instructions.

## Management Tools

- **`scripts/register_dataset.py`**: Register a dataset to the index
- **`scripts/calculate_quality_metrics.py`**: Calculate quality metrics
- **`scripts/validate_dataset.py`**: Validate dataset structure and metadata

## Version Control

- Large data files (`.hspy`, `.mrc`, etc.) should use Git LFS
- Only metadata and index files are tracked in Git
- See `.gitattributes` for LFS configuration

## Best Practices

1. **Use version numbers**: Always include version in dataset name (e.g., `_v1`, `_v2`)
2. **Complete metadata**: Fill in all required fields in `metadata.yaml`
3. **Calculate metrics**: Run quality metrics calculation before registering
4. **Validate**: Always validate dataset before use
5. **Document**: Include README.md in each dataset directory

## References

- [Dataset Adding Guide](../docs/DATASET_ADDING_GUIDE.md)
- [Metadata Schema](../data/metadata/schemas/dataset_schema.yaml)
- [Dataset Template](../data/metadata/dataset_template.yaml)

