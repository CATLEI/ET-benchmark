#!/usr/bin/env python3
"""
Test script for WBP algorithm integration.

Use this to test your WBP implementation before running full benchmark.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import hyperspy.api as hs
from et_dflow.domain.algorithms.registry import get_algorithm_registry

def test_wbp_algorithm():
    """Test WBP algorithm with test data."""
    
    print("=" * 60)
    print("WBP Algorithm Integration Test")
    print("=" * 60)
    print()
    
    # Check if test data exists
    test_data_path = project_root / "data" / "test_dataset" / "test_data.hspy"
    if not test_data_path.exists():
        print(f"[ERROR] Test data not found: {test_data_path}")
        print("Please run: python scripts/create_test_data.py")
        return False
    
    # Load test data
    print(f"Loading test data from: {test_data_path}")
    try:
        data = hs.load(str(test_data_path))
        print(f"[OK] Data loaded: shape {data.data.shape}")
    except Exception as e:
        print(f"[ERROR] Failed to load data: {e}")
        return False
    
    # Get algorithm registry
    print("\nChecking algorithm registry...")
    registry = get_algorithm_registry()
    algorithms = registry.list_algorithms()
    print(f"Registered algorithms: {algorithms}")
    
    if "wbp" not in algorithms:
        print("[ERROR] WBP algorithm not registered!")
        print("Please ensure WBPAlgorithm is registered in et_dflow/domain/algorithms/__init__.py")
        return False
    
    # Get WBP algorithm
    print("\nGetting WBP algorithm...")
    try:
        wbp = registry.get("wbp")
        print(f"[OK] WBP algorithm loaded: {wbp.name}")
    except Exception as e:
        print(f"[ERROR] Failed to get WBP algorithm: {e}")
        return False
    
    # Test algorithm execution
    print("\nRunning WBP reconstruction...")
    print("(This may take a moment...)")
    
    try:
        config = {
            "filter_type": "ramp",
            "filter_cutoff": 1.0,
        }
        
        result = wbp.run(data, config)
        
        print(f"[OK] Reconstruction completed!")
        print(f"  Execution time: {result.execution_time:.2f} seconds")
        print(f"  Memory usage: {result.memory_usage / (1024**2):.2f} MB")
        print(f"  Reconstruction shape: {result.reconstruction.data.shape}")
        
        # Save result for inspection
        output_path = project_root / "results" / "test_wbp_output.hspy"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result.reconstruction.save(str(output_path))
        print(f"\n[OK] Result saved to: {output_path}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Algorithm execution failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_wbp_algorithm()
    
    print("\n" + "=" * 60)
    if success:
        print("[SUCCESS] WBP algorithm test passed!")
        print("\nNext steps:")
        print("1. Replace placeholder code in et_dflow/domain/algorithms/wbp.py")
        print("2. Run: python scripts/test_wbp_integration.py")
        print("3. Run: et-dflow benchmark test_config.yaml")
    else:
        print("[FAILED] WBP algorithm test failed!")
        print("Please check the errors above and fix them.")
    print("=" * 60)
    
    sys.exit(0 if success else 1)

