# PowerShell script to run a local benchmark test

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "ET-dflow Local Benchmark Test" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Create test data
Write-Host "Step 1: Creating test data..." -ForegroundColor Yellow
Write-Host "(Note: Hyperspy warnings about Numba are harmless and can be ignored)" -ForegroundColor Gray
python scripts/create_test_data.py --output-dir ./data/test_dataset --size 64 64 64

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error creating test data!" -ForegroundColor Red
    exit 1
}

# Step 2: Create configuration
Write-Host ""
Write-Host "Step 2: Creating configuration..." -ForegroundColor Yellow
et-dflow quick-start ./data/test_dataset/test_data.hspy --algorithm wbp --output test_config.yaml

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error creating configuration!" -ForegroundColor Red
    exit 1
}

# Step 3: Validate configuration
Write-Host ""
Write-Host "Step 3: Validating configuration..." -ForegroundColor Yellow
et-dflow validate test_config.yaml

if ($LASTEXITCODE -ne 0) {
    Write-Host "Configuration validation failed!" -ForegroundColor Red
    exit 1
}

# Step 4: Run benchmark
Write-Host ""
Write-Host "Step 4: Running benchmark..." -ForegroundColor Yellow
et-dflow benchmark test_config.yaml --output-dir ./results/test_run

# Step 5: Show results
Write-Host ""
Write-Host "Step 5: Benchmark completed!" -ForegroundColor Green
Write-Host "Results are in: ./results/test_run" -ForegroundColor Green
Write-Host ""
Get-ChildItem ./results/test_run/ -ErrorAction SilentlyContinue | Format-Table

