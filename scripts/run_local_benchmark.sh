#!/bin/bash
# Quick script to run a local benchmark test

set -e

echo "=========================================="
echo "ET-dflow Local Benchmark Test"
echo "=========================================="
echo ""

# Step 1: Create test data
echo "Step 1: Creating test data..."
python scripts/create_test_data.py --output-dir ./data/test_dataset --size 64 64 64

# Step 2: Create configuration
echo ""
echo "Step 2: Creating configuration..."
et-dflow quick-start ./data/test_dataset/test_data.hspy --algorithm wbp --output test_config.yaml

# Step 3: Validate configuration
echo ""
echo "Step 3: Validating configuration..."
et-dflow validate test_config.yaml

# Step 4: Run benchmark
echo ""
echo "Step 4: Running benchmark..."
et-dflow benchmark test_config.yaml --output-dir ./results/test_run

# Step 5: Show results
echo ""
echo "Step 5: Benchmark completed!"
echo "Results are in: ./results/test_run"
echo ""
ls -la ./results/test_run/

