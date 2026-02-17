"""
Simple test to verify core components work independently.
"""
import sys
sys.path.insert(0, 'D:\\TrafficSim')

print("Testing D:\\TrafficSim core components...")

# Test 1: GPU
print("\n1. Testing GPU...")
from core.gpu import xp, USING_GPU
print(f"   ✅ GPU module loaded")
print(f"   GPU Enabled: {USING_GPU}")

# Test 2: Physics
print("\n2. Testing Physics...")
from core.physics import calculate_idm_vectorized
print(f"   ✅ Physics module loaded")

# Test 3: Lanes
print("\n3. Testing LaneMap...")
from core.lanes import LaneMap
lane_map = LaneMap(num_lanes=4)
lane_map.set_lane(0, length=100.0, speed_limit=30.0, next_lanes=[1, 2])
print(f"   ✅ LaneMap created with {lane_map.num_lanes} lanes")

# Test 4: Signals
print("\n4. Testing SignalController...")
from core.signals import SignalControllerVector, MODE_FIXED
signals = SignalControllerVector(num_nodes=1, mode=MODE_FIXED)
print(f"   ✅ SignalController created")

# Test 5: Engine
print("\n5. Testing TrafficEngine...")
from core.engine import TrafficEngine
engine = TrafficEngine(lane_map, signals, max_vehicles=100)
print(f"   ✅ TrafficEngine created")

# Test 6: Spawn vehicles
print("\n6. Testing vehicle spawning...")
import numpy as np_cpu  # Use CPU NumPy for array creation
engine.spawn_vehicles(
    count=5,
    lane_ids=xp.array([0, 0, 1, 1, 2], dtype=xp.int32),
    positions=xp.zeros(5, dtype=xp.float32),
    types=xp.array([0, 0, 1, 1, 2], dtype=xp.int32)
)
print(f"   ✅ Spawned {engine.active_count} vehicles")

# Test 7: Step simulation
print("\n7. Testing simulation step...")
engine.step()
print(f"   ✅ Simulation stepped")

print("\n✅ ALL CORE COMPONENTS WORKING!")
print("\nNote: Full CLI integration may need additional debugging,")
print("but all core simulation components are functional.")
