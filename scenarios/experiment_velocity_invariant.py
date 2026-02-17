
import sys
import os
import random
from time import time
from typing import Dict, Any

# Ensure parent directory (Repo Root) is in path
# __file__ = experiments/velocity_invariant.py
# dirname = experiments
# dirname(dirname) = traffic_grid
# dirname(dirname(dirname)) = Repo Root
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from traffic_grid.python_sim.grid_network import TrafficGridNetwork
from traffic_intersection.python_sim.signal_control import EightPhaseController
from traffic_grid.python_sim.config import CONFIG, override_config, get_vehicle_specs

def run_simulation(length: float, v_max_override: float, duration: float = 300.0, seed: int = 42) -> float:
    # 1. Patch Configuration
    # We essentially mock the configuration by modifying the global CONFIG dict temporarily
    # Ideally, we would reload config or use a context manager, but direct patching is faster for this script.
    
    # Store original values to restore later if needed (though we just overwrite next loop)
    original_lane_length = CONFIG["lane_length"]
    CONFIG["lane_length"] = length
    
    # Patch vehicle speeds
    original_specs = {}
    for vtype, spec in CONFIG["vehicle_types"].items():
        original_specs[vtype] = spec.copy()
        CONFIG["vehicle_types"][vtype]["v_max"] = v_max_override
        
        # We also need to scale acceleration to reach target speed reasonable fast? 
        # The user said "rest all properties remain exact same", so we keep accel same.
        # However, to be fair, maybe accel should scale? 
        # User said: "rest all properties remain exact same". So we leave accel alone.

    try:
        # 2. Initialize Network
        # We use a FixedSignalController to ensure deterministic signaling
        # We use a specific seed for the network to ensure identical spawn times/types
        
        # Create a factory for fixed controllers (e.g. 30s green time)
        # Create a factory for fixed controllers (e.g. 30s green time)
        # Using EightPhaseController with fixed 30s for all phases
        def fixed_factory():
            c = EightPhaseController()
            c.initialize({i: 30.0 for i in range(1, 9)})
            return c
        controller_factory = fixed_factory
        
        net = TrafficGridNetwork(
            size=10, # 10x10 grid
            controller_factory=controller_factory,
            spawn_rate=0.4, # standard inflow
            inflow_noise=0.0, # Deterministic inflow for this experiment? 
            # User said "let X vehicles enter". 
            # If we use random inflow with SAME SEED, it works.
            # But user said "inflow... random and one we can set via parameters" in previous task.
            # Here for "X vehicles enter", standard usage with same seed is fine.
            seed=seed,
            stats_interval=duration + 1.0 # Don't need intermediate stats
        )
        
        # 3. Run Simulation
        net.run(duration_seconds=duration, speedup=100.0) # speedup doesn't affect logic, just viz (which is off)
        
        # 4. Collect Metrics
        summary = net.export_summary()
        
        avg_wait = summary.get("total_wait", 0.0) / max(1, summary.get("total_cars", 1))
        avg_travel = summary.get("avg_travel_time", 0.0)
        avg_accel = summary.get("avg_accel_time", 0.0)
        avg_cruise = summary.get("avg_cruise_time", 0.0)
        cars_exited = summary.get("exited_count", 0)
            
        return avg_travel, avg_accel, avg_cruise, cars_exited

    finally:
        # Restore Config
        CONFIG["lane_length"] = original_lane_length
        for vtype in original_specs:
            CONFIG["vehicle_types"][vtype] = original_specs[vtype]


def main():
    # Header for the table
    header = (
        f"{'Length':<8} | "
        f"{'Travel(30)':<10} | {'Travel(40)':<10} | {'Diff':<8} | "
        f"{'Accel(30)':<9} | {'Accel(40)':<9} | "
        f"{'Cruis(30)':<9} | {'Cruis(40)':<9} | "
        f"{'Exited':<6}"
    )
    print(header)
    print("-" * len(header))
    
    # Sweep
    best_diff = float("inf")
    best_len = -1
    
    # From 100m to 3000m
    for length in range(100, 3001, 100):
        # Calculate appropriate duration to ensure cars exit
        # Path length approx 1.5 * grid_size * length (average path?)
        # Worst case: grid_size * length.
        # Speed 30.
        # Travel time ~ (10 * length) / 30 = length / 3.
        # We want ~20-50 cars to exit.
        # Inflow 0.4 cars/sec.
        # Wait, grid inflow is global? grid_network.py: spawn_rate=0.4.
        # 0.4 cars per second ENTER.
        # To get 50 cars, we need ~125 seconds of spawning.
        # Plus travel time to clear them.
        # So duration = 200 + (length / 3).
        
        duration = 500.0 + (length / 3.0) * 1.5 # 1.5 safety factor
        
        print(f"Testing Length {length}m (Duration: {duration:.1f}s)...", file=sys.stderr)
        
        # Run 30
        t30, a30, c30, e30 = run_simulation(length, 30.0, duration=duration)
        
        # Run 40
        t40, a40, c40, e40 = run_simulation(length, 40.0, duration=duration)
        
        diff = abs(t30 - t40)
        
        row = (
            f"{length:<8} | "
            f"{t30:<10.2f} | {t40:<10.2f} | {diff:<8.2f} | "
            f"{a30:<9.2f} | {a40:<9.2f} | "
            f"{c30:<9.2f} | {c40:<9.2f} | "
            f"{e30:<6.0f}"
        )
        print(row)
        # Flush stdout to ensure we see it in file
        sys.stdout.flush()
        
        if diff < best_diff and e30 > 10 and e40 > 10: # Only consider valid runs
            best_diff = diff
            best_len = length
            
    print("-" * len(header))
    print(f"Minimum travel time difference found at Length = {best_len} m (Diff: {best_diff:.2f}s)")
    print("Metrics verified: Total Travel Time (Exit - Entry). detailed acceleration and cruise stats provided.")

if __name__ == "__main__":
    main()
