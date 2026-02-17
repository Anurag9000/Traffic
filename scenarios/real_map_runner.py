
import os
import sys
import numpy as np
import json
import argparse
import networkx as nx

# Ensure root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from core.real_network import RealTrafficNetwork
from core.spawning import Spawner
from core.stats import VectorStatsRecorder
from core.paths import get_results_dir

def run_targeted_real(map_name: str, duration: int, rate: float, 
                      target_lat: float, target_lon: float,
                      radius_km: float = 1.0):
                      
    print(f"\n--- Running Targeted Real Map ({map_name}) | Rate={rate} ---")
    print(f"Target: ({target_lat}, {target_lon}) | Focus Radius: {radius_km}km")
    
    # 1. Setup Map
    network = RealTrafficNetwork(map_filter=map_name, sim_duration=duration, spawn_rate=rate)
    
    # 2. Get Target Node coordinates in Project/Graph Frame
    # OSMnx usually keeps lat/lon if simplify=False, or projects to UTM?
    # Our graph loading in real_network uses ox.load_graphml
    # Typically, nodes have 'x' (lon) and 'y' (lat).
    
    # We want to use the user-provided Lat/Lon as the target (x, y).
    # NOTE: In OSMnx, x=Lon, y=Lat.
    target_x = target_lon
    target_y = target_lat
    
    targets = [(target_x, target_y)]
    
    # 3. Inject Spawner
    # 80% should target the hotspot to see effect.
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
    output_dir = get_results_dir("targeted_real")
    recorder = VectorStatsRecorder(network.engine, output_dir=output_dir, prefix=f"{map_name}_targeted")
    
    steps = int(duration / 0.1)
    
    for i in range(steps):
        network.step()
        
        if i % 1000 == 0:
            active = network.engine.active_count
            print(f"\rStep {i}/{steps} | Active: {active}", end="")
            
        if i % 100 == 0:
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
    parser.add_argument("--map", type=str, default="all", help="Map filter (all/backbone)")
    parser.add_argument("--rate", type=float, default=0.5, help="Spawn Rate")
    parser.add_argument("--duration", type=int, default=1000, help="Duration")
    
    # Default Target: Connaught Place, Delhi
    # Lat: 28.6304, Lon: 77.2177
    parser.add_argument("--lat", type=float, default=28.6304, help="Target Latitude")
    parser.add_argument("--lon", type=float, default=77.2177, help="Target Longitude")
    
    args = parser.parse_args()
    
    # Defaults
    map_name = args.map
    rate = args.rate
    duration = args.duration
    lat = args.lat
    lon = args.lon
    radius = 1.0
    
    if args.config:
        import json
        with open(args.config, 'r') as f:
            cfg = json.load(f)
            
        # Parse Config
        # If 'map_name' in JSON, use it. Else use default/CLI.
        map_name = cfg.get("map_name", map_name)
        if map_name.endswith(".graphml"): # Fix for mismatch names
             # The loader uses 'all' or 'backbone' or path. 
             # Let's strip extension for filter or pass raw if complex.
             # real_network loader is smart.
             pass
             
        rate = cfg.get("spawn_rate", rate)
        duration = cfg.get("duration", duration)
        
        target = cfg.get("target", {})
        lat = target.get("lat", lat)
        lon = target.get("lon", lon)
        radius = cfg.get("radius_km", radius)
        
        print(f"Loaded config: {args.config}")

    # Results directory created automatically by get_results_dir()
        
    run_targeted_real(map_name, duration, rate, lat, lon, radius)
