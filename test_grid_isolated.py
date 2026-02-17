"""
Isolated test for grid simulation to identify exact error.
"""
import sys
sys.path.insert(0, 'D:\\TrafficSim')

print("Step 1: Import modules...")
from core import TrafficGridNetwork, VectorStatsRecorder

print("Step 2: Create grid network...")
network = TrafficGridNetwork(
    grid_size=2,
    spawn_rate=0.1,
    control_mode='fixed'
)
print(f"✅ Network created with {network.size}x{network.size} grid")

print("\nStep 3: Create stats recorder...")
recorder = VectorStatsRecorder(network.engine, prefix="test_grid")
print("✅ Recorder created")

print("\nStep 4: Run simulation loop...")
duration = 5.0
steps = int(duration / network.dt)
print(f"Running {steps} steps...")

for i in range(min(steps, 10)):  # Just 10 steps for testing
    print(f"  Step {i+1}...", end='')
    network.step()
    print(" OK")
    
print("\n✅ Simulation completed!")
print(f"Active vehicles: {network.engine.active_count}")
