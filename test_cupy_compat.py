"""
Comprehensive CuPy compatibility test
Tests each operation step-by-step to identify exact failure point
"""
import sys
import traceback
sys.path.insert(0, 'D:\\TrafficSim')

def test_step(name, func):
    """Test a single step and report result"""
    try:
        result = func()
        print(f"✓ {name}")
        return result
    except Exception as e:
        print(f"✗ {name}: {e}")
        traceback.print_exc()
        sys.exit(1)

print("="*60)
print("CuPy Compatibility Test Suite")
print("="*60)

# Test 1: Import
def test_import():
    from core import TrafficGridNetwork, xp, USING_GPU
    print(f"  Using: {'CuPy (GPU)' if USING_GPU else 'NumPy (CPU)'}")
    return TrafficGridNetwork, xp, USING_GPU

GridNet, xp, using_gpu = test_step("1. Import modules", test_import)

# Test 2: Create network
def test_create():
    return GridNet(grid_size=2, spawn_rate=0.1)

network = test_step("2. Create network", test_create)

# Test 3: First step (no vehicles)
def test_empty_step():
    network.step()
    return True

test_step("3. Empty step", test_empty_step)

# Test 4: Spawn vehicles
def test_spawn():
    # Spawner needs entry lanes for the network
    entry_lanes = list(range(min(4, network.map.num_lanes)))
    count = network.spawner.step(entry_lanes, network.engine)
    return count

count = test_step("4. Spawn vehicles", test_spawn)
print(f"  Spawned: {count} vehicles")

# Test 5: Step with vehicles
def test_vehicle_step():
    network.step()
    return True

test_step("5. Step with vehicles", test_vehicle_step)

# Test 6: Multiple steps
def test_multiple_steps():
    for i in range(5):
        network.step()
    return True

test_step("6. Multiple steps", test_multiple_steps)

print("="*60)
print("✓ ALL TESTS PASSED!")
print("="*60)
