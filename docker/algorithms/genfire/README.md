# GENFIRE Adapter

This directory contains an adapter script for integrating GENFIRE algorithm with ET-dflow.

## Purpose

The adapter script (`run_algorithm.py`) bridges the standard ET-dflow interface with GENFIRE's specific API.

## Standard Interface

ET-dflow expects algorithms to accept:
- `--input <path>`: Input tilt series file (.hspy)
- `--output <path>`: Output reconstruction file (.hspy)
- `--config <json>`: JSON configuration string

## GENFIRE Integration

The adapter:
1. Loads input tilt series using Hyperspy
2. Extracts configuration parameters
3. Calls GENFIRE API to perform reconstruction
4. Saves result in Hyperspy format

## Usage

### Option 1: Use with External Image (Recommended)

If you have a pre-built GENFIRE image, you can create a wrapper image:

```dockerfile
FROM registry.dp.tech/davinci/genfire-python:20260110195114

# Copy adapter script
COPY docker/algorithms/genfire/run_algorithm.py /app/run_algorithm.py
RUN chmod +x /app/run_algorithm.py
```

Then use the wrapper image in your configuration.

### Option 2: Direct Integration

If the external image already has the adapter script, use it directly:

```yaml
algorithms:
  genfire:
    docker_image: "registry.dp.tech/davinci/genfire-python:20260110195114"
    parameters:
      iterations: 100
```

## Implementation Notes

The current adapter script contains placeholder code. To complete the integration:

1. **Understand GENFIRE API**: Review GENFIRE documentation
2. **Implement Reconstruction**: Replace placeholder with actual GENFIRE calls
3. **Handle Data Formats**: Ensure proper conversion between Hyperspy and GENFIRE formats
4. **Test**: Verify the adapter works with your GENFIRE image

## Example GENFIRE Call (Placeholder)

```python
# This is a placeholder - actual implementation will vary
import genfire

# Create GENFIRE object
genfire_obj = genfire.GENFIRE()

# Load tilt series
genfire_obj.load_tilt_series(tilt_series.data, tilt_angles)

# Set parameters
genfire_obj.set_parameters(
    iterations=iterations,
    oversampling_ratio=oversampling_ratio
)

# Reconstruct
reconstruction_data = genfire_obj.reconstruct()

# Convert to Hyperspy signal
reconstruction = hs.signals.Signal1D(reconstruction_data)
```

## Testing

Test the adapter locally:

```bash
# Test with sample data
python docker/algorithms/genfire/run_algorithm.py \
  --input ./data/test_dataset/tilt_series.hspy \
  --output ./output/reconstruction.hspy \
  --config '{"iterations": 100, "oversampling_ratio": 1.5}'
```

## Related Files

- Adapter script: `run_algorithm.py`
- Integration guide: `docs/EXTERNAL_DOCKER_IMAGES_INTEGRATION.md`
- Example config: `configs/benchmark_external.yaml`

