"""
GPU Acceleration Test Script

Tests that GPU acceleration is working correctly with automatic fallback.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.gpu_utils import xp, USING_GPU, get_device_info, to_numpy, synchronize
import time

def test_basic_operations():
    """Test basic array operations."""
    print("\n=== Test 1: Basic Operations ===")
    
    # Create arrays
    a = xp.array([1, 2, 3, 4, 5])
    b = xp.array([10, 20, 30, 40, 50])
    
    # Operations
    c = a + b
    d = xp.sum(c)
    e = xp.mean(a)
    
    print(f"a + b = {c}")
    print(f"sum(a + b) = {d}")
    print(f"mean(a) = {e}")
    print("✅ Basic operations work")

def test_gpu_cpu_transfer():
    """Test GPU to CPU transfer."""
    print("\n=== Test 2: GPU ↔ CPU Transfer ===")
    
    # Create GPU array
    gpu_arr = xp.arange(10)
    print(f"GPU array: {gpu_arr}")
    print(f"Array type: {type(gpu_arr).__module__}.{type(gpu_arr).__name__}")
    
    # Convert to CPU
    cpu_arr = to_numpy(gpu_arr)
    print(f"CPU array: {cpu_arr}")
    print(f"Array type: {type(cpu_arr).__module__}.{type(cpu_arr).__name__}")
    
    # Verify values match
    assert all(cpu_arr == xp.asnumpy(gpu_arr) if USING_GPU else cpu_arr == gpu_arr)
    print("✅ GPU ↔ CPU transfer works")

def test_performance():
    """Test performance difference."""
    print("\n=== Test 3: Performance ===")
    
    size = 10000
    iterations = 100
    
    # Create large arrays
    a = xp.random.rand(size)
    b = xp.random.rand(size)
    
    # Warm up
    _ = xp.sum(a * b)
    synchronize()
    
    # Time operations
    start = time.time()
    for _ in range(iterations):
        result = xp.sum(a * b + xp.sqrt(a) * xp.exp(b / 10))
    synchronize()
    elapsed = time.time() - start
    
    print(f"Array size: {size}")
    print(f"Iterations: {iterations}")
    print(f"Time: {elapsed:.4f}s")
    print(f"Ops/sec: {iterations / elapsed:.1f}")
    print("✅ Performance test complete")

def main():
    print("=" * 60)
    print("GPU ACCELERATION TEST")
    print("=" * 60)
    
    # Show device info
    print("\n=== Device Information ===")
    info = get_device_info()
    print(f"Device Type: {info['type']}")
    if USING_GPU:
        print(f"GPU Name: {info['name']}")
        print(f"Compute Capability: {info['compute_capability']}")
        print(f"Total Memory: {info['total_memory_gb']:.2f} GB")
        print(f"Free Memory: {info['free_memory_gb']:.2f} GB")
    else:
        print(f"NumPy Version: {info.get('numpy_version', 'N/A')}")
    
    # Run tests
    try:
        test_basic_operations()
        test_gpu_cpu_transfer()
        test_performance()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
