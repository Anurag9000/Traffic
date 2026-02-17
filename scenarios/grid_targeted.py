

import os
import sys
import numpy as np
import argparse

# Ensure root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from core.grid_network import TrafficGridNetwork
from core.spawning import Spawner
from core.stats import VectorStatsRecorder
from core.paths import get_results_dir

def run_targeted_grid(size: int, duration: int, rate: float, target_center: bool = True):
    print(f"\n--- Running Targeted Grid (Size={size}x{size}) | Rate={rate} ---")
    
    # 1. Setup Grid
    network = TrafficGridNetwork(size=size, spawn_rate=rate, lane_length=100.0)
    
    # 2. Define Target (Center Intersection)
    # Grid coordinates: (size // 2, size // 2)
    # Physical coordinates: x = c * 100, y = r * 100
    mid = size // 2
    target_x = float(mid) * 100.0
    target_y = float(mid) * 100.0
    
    targets = [(target_x, target_y)]
    print(f"Target: ({target_x}, {target_y}) [Node {mid},{mid}]")
    
    # 3. Inject Spawner
    # 50% of cars will target the center. Others random walk.
    network.spawner = Spawner(
        mode='targeted',
        lane_map=network.lane_map,
        mean_rate=rate,
        variation=0.2,
        dt=0.1,
        target_ratio=0.8,
        targets=targets
    )
    
    # 4. Recorder
    output_dir = get_results_dir("targeted")
    recorder = VectorStatsRecorder(network.engine, output_dir=output_dir, prefix="grid_center")
    
    steps = int(duration / 0.1)
    
    for i in range(steps):
        network.step()
        
        if i % 1000 == 0:
            active = network.engine.active_count
            print(f"\rStep {i}/{steps} | Active: {active}", end="")
            
        if i % 10 == 0:
            recorder.log_step(network.engine.current_time)
            
    print("\nSimulation Complete.")
    stats = recorder.compute_summary()
    print(f"Total Trips (Arrived+Exited): {stats['total_vehicles']}")
    print(f"Avg Duration: {stats['avg_delay']:.2f}s")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # Mode 1: Config File
    parser.add_argument("--config", type=str, help="Path to JSON config")
    
    # Mode 2: CLI Overrides
    parser.add_argument("--size", type=int, default=5, help="Grid Size")
    parser.add_argument("--rate", type=float, default=0.2, help="Spawn Rate")
    parser.add_argument("--duration", type=int, default=1000, help="Duration")
    
    args = parser.parse_args()
    
    # Defaults
    size = args.size
    rate = args.rate
    duration = args.duration
    target_center = True
    
    if args.config:
        import json
        with open(args.config, 'r') as f:
            cfg = json.load(f)
            
        print(f"Loaded config: {args.config}")
        size = cfg.get("grid_size", size)
        rate = cfg.get("spawn_rate", rate)
        duration = cfg.get("duration", duration)
        
        # We could add support for custom (x,y) targets in JSON later
        # For now, default to center if not specified or type is "center"
        tgt = cfg.get("target", {})
        if tgt.get("type") == "center":
            target_center = True
    
    # Results directory created automatically by get_results_dir()
        
    run_targeted_grid(size, duration, rate, target_center)
