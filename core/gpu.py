"""
GPU Acceleration Module

Provides automatic GPU/CPU abstraction using CuPy/NumPy.
GPU is enabled by default with automatic fallback to CPU.
"""

import sys
import warnings

# GPU enabled by default - automatic fallback to CPU
FORCE_CPU = False

if FORCE_CPU:
    import numpy as np
    xp = np
    USING_GPU = False
    GPU_NAME = None
    print("[INFO] GPU Acceleration DISABLED: Forced CPU mode")
else:
    try:
        import cupy as cp
        
        # Verify CUDA availability
        try:
            test_array = cp.zeros(10)
            _ = cp.asnumpy(test_array)
            del test_array
            
            device = cp.cuda.Device()
            gpu_name = device.name if hasattr(device, 'name') else "CUDA GPU"
            
            xp = cp
            USING_GPU = True
            GPU_NAME = gpu_name
            print(f"✅ GPU Acceleration ENABLED: {gpu_name}")
            mem_info = device.mem_info
            print(f"   GPU Memory: {mem_info[1] / (1024**3):.2f} GB total, {mem_info[0] / (1024**3):.2f} GB free")
            
        except Exception as e:
            import numpy as np
            xp = np
            USING_GPU = False
            GPU_NAME = None
            print(f"[WARN] GPU Acceleration DISABLED: CUDA failed ({e})")
            print("   Falling back to CPU (NumPy)")
            
    except ImportError:
        import numpy as np
        xp = np
        USING_GPU = False
        GPU_NAME = None
        print("⚠️  GPU Acceleration DISABLED: CuPy not installed")
        print("   Install with: pip install cupy-cuda12x")
        print("   Falling back to CPU (NumPy)")


def to_numpy(arr):
    """Convert array to NumPy (from GPU if needed)."""
    if USING_GPU:
        import cupy as cp
        if isinstance(arr, cp.ndarray):
            return cp.asnumpy(arr)
    import numpy as np
    if isinstance(arr, np.ndarray):
        return arr
    return np.asarray(arr)


def to_gpu(arr):
    """Convert NumPy array to GPU if available."""
    if not USING_GPU:
        return arr
    
    import cupy as cp
    import numpy as np
    
    if isinstance(arr, cp.ndarray):
        return arr
    elif isinstance(arr, np.ndarray):
        return cp.asarray(arr)
    else:
        return cp.asarray(np.asarray(arr))


def synchronize():
    """Synchronize GPU operations."""
    if USING_GPU:
        import cupy as cp
        cp.cuda.Stream.null.synchronize()


def get_device_info():
    """Get compute device information."""
    if USING_GPU:
        import cupy as cp
        device = cp.cuda.Device()
        mem_info = device.mem_info
        cc = device.compute_capability
        return {
            'type': 'GPU',
            'name': GPU_NAME,
            'compute_capability': f"{cc[0]}.{cc[1]}" if isinstance(cc, tuple) else str(cc),
            'total_memory_gb': mem_info[1] / (1024**3),
            'free_memory_gb': mem_info[0] / (1024**3),
            'device_id': device.id,
        }
    else:
        import numpy as np
        return {
            'type': 'CPU',
            'name': 'NumPy',
            'numpy_version': np.__version__,
        }


__all__ = ['xp', 'USING_GPU', 'to_numpy', 'to_gpu', 'synchronize', 'get_device_info']
