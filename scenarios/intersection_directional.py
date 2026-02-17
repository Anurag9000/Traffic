

import os
import sys
import json
import argparse
import numpy as np
from typing import Dict, List

# Ensure root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from core.intersection import SingleIntersection
from core.signals import MODE_FIXED, MODE_ADAPTIVE
from core.stats import VectorStatsRecorder
from core.spawning import Spawner
from core.paths import get_results_dir

# LANE MAPPING for Single Intersection (12 Lanes)
# Based on standard counter-clockwise or array indexing usually used in the repo
# South (0,1,2), West (3,4,5), North (6,7,8), East (9,10,11)
# Each arm has [Left, Straight, Right]
LANE_MAP = {
    "south_incoming": [0, 1, 2], # Coming FROM South (going North)
    "west_incoming":  [3, 4, 5], # Coming FROM West (going East)
    "north_incoming": [6, 7, 8], # Coming FROM North (going South)
    "east_incoming":  [9, 10, 11] # Coming FROM East (going West)
}

TURN_INDICES = {
    "left": 0,
    "straight": 1, 
    "right": 2
}

def parse_config(config_path: str) -> Dict[int, float]:
    """
    Parses semantic config into Lane ID Bias Map.
    Supports global turn ratios and per-direction overrides.
    """
    with open(config_path, 'r') as f:
        cfg = json.load(f)
        
    biases = cfg.get("flow_biases", {})
    turn_cfg = cfg.get("turn_biases", {})
    global_turns = turn_cfg.get("global", {"left": 1.0, "straight": 1.0, "right": 1.0})
    overrides = turn_cfg.get("overrides", {})
    
    lane_bias_map = {}
    
    for direction, direction_multiplier in biases.items():
        if direction not in LANE_MAP:
            print(f"Warning: Unknown direction '{direction}'")
            continue
            
        lane_ids = LANE_MAP[direction]
        # lane_ids is [Left, Straight, Right]
        
        # Get appropriate turn ratios
        if direction in overrides:
            turns = overrides[direction]
            # Merge with global defaults if missing, let's assume override is partial or full.
            t_left = turns.get("left", global_turns.get("left", 1.0))
            t_straight = turns.get("straight", global_turns.get("straight", 1.0))
            t_right = turns.get("right", global_turns.get("right", 1.0))
        else:
            t_left = global_turns.get("left", 1.0)
            t_straight = global_turns.get("straight", 1.0)
            t_right = global_turns.get("right", 1.0)
            
        # Apply Direction Multiplier * Turn Multiplier
        # Lane 0: Turn Left
        lane_bias_map[lane_ids[0]] = direction_multiplier * t_left
        
        # Lane 1: Go Straight
        lane_bias_map[lane_ids[1]] = direction_multiplier * t_straight
        
        # Lane 2: Turn Right
        lane_bias_map[lane_ids[2]] = direction_multiplier * t_right
        
    return lane_bias_map, cfg

def run_simulation(config_path: str, mode_name: str, control_mode: int):
    lane_biases, cfg = parse_config(config_path)
    rate = cfg.get("spawn_rate", 0.1)
    duration = cfg.get("duration", 3600)
    
    print(f"\n--- Running {mode_name} | Config: {config_path} ---")
    print(f"Base Rate: {rate} | Duration: {duration}s")
    print(f"Biases: {lane_biases}")
    
    sim = SingleIntersection(spawn_rate=rate, control_mode=control_mode)
    sim.spawner = Spawner(mode='directional', mean_rate=rate, variation=0.2, dt=0.1, lane_biases=lane_biases)
    
    output_dir = get_results_dir("directional")
    recorder = VectorStatsRecorder(sim.engine, output_dir=output_dir, prefix=f"{mode_name}")
    
    steps = int(duration / 0.1)
    
    for i in range(steps):
        sim.step()
        if i % 1000 == 0:
            active = sim.engine.active_count
            print(f"\rStep {i}/{steps} | Active: {active}", end="")
        if i % 10 == 0:
             recorder.log_step(sim.engine.current_time)
             
    print(f"\nComputing stats for {mode_name}...")
    stats = recorder.compute_summary()
    return stats

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, required=True, help="Path to JSON config")
    args = parser.parse_args()
    
    # Results directory created automatically by get_results_dir()
        
    # Run Fixed
    f_stats = run_simulation(args.config, "FIXED", MODE_FIXED)
    
    # Run Dynamic
    d_stats = run_simulation(args.config, "DYNAMIC", MODE_ADAPTIVE)
    
    print("\n=== DIRECTIONAL MODE RESULTS ===")
    print(f"FIXED:   Total={f_stats['total_vehicles']}, Delay={f_stats['avg_delay']:.2f}s")
    print(f"DYNAMIC: Total={d_stats['total_vehicles']}, Delay={d_stats['avg_delay']:.2f}s")
    
    if f_stats['avg_delay'] > 0:
        imp = (f_stats['avg_delay'] - d_stats['avg_delay']) / f_stats['avg_delay'] * 100
        print(f"IMPROVEMENT: {imp:.2f}%")

if __name__ == "__main__":
    main()
