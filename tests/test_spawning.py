
import numpy as np
import time
import sys
import os

# Robustly find root dir
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from core.intersection import SingleIntersection
from traffic_grid.python_sim.grid_network import TrafficGridNetwork

def verify_density(name, model, steps=500):
    print(f"--- Verifying {name} ---")
    start_time = time.time()
    for _ in range(steps):
        model.step()
    
    active = model.engine.active_count
    # In my logic, entry_lane_ids are where cars start (pos=0)
    # Let's count how many vehicles currently have X < 10.0 (near entry)
    # Actually, let's just use total active as a proxy for 'busy-ness'
    print(f"Steps: {steps} | Active Vehicles: {active}")
    return active

def main():
    rate = 0.05 # Low rate for clear comparison
    
    # 1. Single Intersection (12 entry lanes)
    si = SingleIntersection(spawn_rate=rate, lane_length=100.0)
    si_active = verify_density("Single Intersection", si)
    
    # 2. Grid Network 3x3 (12 entry lanes at the edges)
    # A 3x3 grid has 3*4 = 12 entry APPROACHES? 
    # Let's check boundary lanes.
    grid3 = TrafficGridNetwork(size=3, spawn_rate=rate, lane_length=100.0)
    print(f"Grid 3x3 Boundary Lanes: {len(grid3.boundary_lanes)}")
    grid3_active = verify_density("Grid 3x3", grid3)
    
    # If logic is correct, both should have similar active vehicle counts
    # because they have a similar number of ENTRY POINTS (12 each).
    # si_active and grid3_active should be close.
    
    # 3. Grid Network 5x5 (20 entry lanes at the edges)
    grid5 = TrafficGridNetwork(size=5, spawn_rate=rate, lane_length=100.0)
    print(f"Grid 5x5 Boundary Lanes: {len(grid5.boundary_lanes)}")
    grid5_active = verify_density("Grid 5x5", grid5)
    
    # Grid 5 ratio should be roughly (20/12) * si_active
    print("\nScaling Check:")
    print(f"SI Active: {si_active}")
    print(f"Grid 3x3 Active: {grid3_active} (Expect ~{si_active})")
    print(f"Grid 5x5 Active: {grid5_active} (Expect ~{int(grid5_active * 12/20)} normalized)")

if __name__ == "__main__":
    main()
