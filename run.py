#!/usr/bin/env python3
"""
Unified Traffic Simulation Runner

Execute any simulation with a single command using YAML configuration files.

Usage:
    python run.py configs/grid_baseline.yaml
    python run.py configs/grid_adaptive.yaml
    python run.py configs/intersection_directional.yaml
    python run.py configs/delhi_baseline.yaml
    
Available configs:
    Grid Network:
        - grid_baseline.yaml          : Uniform spawning, fixed signals
        - grid_adaptive.yaml          : Uniform spawning, adaptive signals
        - grid_targeted.yaml          : 80% vehicles to center
        - grid_subgrid.yaml           : Region-specific signal timings
        - grid_lambda_decay.yaml      : Exponential spawn rate decay
        - grid_morning_rush.yaml      : Time-varying morning rush profile
    
    Intersection:
        - intersection_baseline.yaml  : Standard 4-way intersection
        - intersection_directional.yaml : Heavy N-S flow
    
    Real Map (Delhi):
        - delhi_baseline.yaml         : Standard OSM with adaptive signals
        - delhi_fixed.yaml            : OSM with fixed signals
        - delhi_targeted.yaml         : Navigation to specific coordinates
    
    Experiments:
        - experiment_speed_threshold.yaml : Speed vs throughput analysis
        - experiment_velocity_30.yaml     : 30 kmph performance
        - experiment_velocity_40.yaml     : 40 kmph performance
"""

import sys
import yaml
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from core.grid_network import TrafficGridNetwork
from core.real_network import RealTrafficNetwork
from core.intersection import TrafficIntersection
from core.stats import VectorStatsRecorder


def load_config(config_path: str) -> dict:
    """Load YAML configuration file."""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config


def create_network(config: dict):
    """Create network based on configuration mode."""
    mode = config.get('mode', 'grid')
    sim_config = config.get('simulation', {})
    spawn_config = config.get('spawning', {})
    signal_config = config.get('signals', {})
    
    # Map signal control mode
    control_mode_map = {'fixed': 0, 'adaptive': 1, 'gap_out': 2}
    control_mode = control_mode_map.get(signal_config.get('control_mode', 'fixed'), 0)
    
    if mode == 'grid':
        grid_config = config.get('grid', {})
        
        # Prepare lambda decay if present
        lambda_decay = spawn_config.get('lambda_decay', None)
        
        network = TrafficGridNetwork(
            grid_size=grid_config.get('grid_size', 5),
            spawn_rate=spawn_config.get('spawn_rate', 1.0),
            variation=spawn_config.get('variation', 0.5),
            stats_interval=sim_config.get('stats_interval', 60.0),
            subgrid_regions=grid_config.get('subgrid_regions', None),
            seed=sim_config.get('seed', 42),
            lane_length=grid_config.get('lane_length', 100.0),
            control_mode='adaptive' if control_mode == 1 else 'fixed',
        )
        
        # Override spawner if lambda decay is specified
        if lambda_decay:
            from core.spawning import Spawner
            network.spawner = Spawner(
                mode=spawn_config.get('mode', 'uniform'),
                mean_rate=spawn_config.get('spawn_rate', 1.0),
                variation=spawn_config.get('variation', 0.5),
                dt=sim_config.get('dt', 0.1),
                seed=sim_config.get('seed', 42),
                lambda_decay=lambda_decay,
            )
        
        # Override spawner for targeted mode
        if spawn_config.get('mode') == 'targeted':
            from core.spawning import Spawner
            network.spawner = Spawner(
                mode='targeted',
                mean_rate=spawn_config.get('spawn_rate', 1.0),
                variation=spawn_config.get('variation', 0.5),
                dt=sim_config.get('dt', 0.1),
                seed=sim_config.get('seed', 42),
                lane_map=network.lane_map,
                target_ratio=spawn_config.get('target_fraction', 0.8),
                targets=[tuple(spawn_config.get('target_coord', [250.0, 250.0]))],
            )
        
        return network
    
    elif mode == 'intersection':
        network = TrafficIntersection(
            spawn_rate=spawn_config.get('spawn_rate', 0.8),
            variation=spawn_config.get('variation', 0.5),
            seed=sim_config.get('seed', 42),
            control_mode=control_mode,
        )
        
        # Override spawner for directional mode
        if spawn_config.get('mode') == 'directional':
            from core.spawning import Spawner
            network.spawner = Spawner(
                mode='directional',
                mean_rate=spawn_config.get('spawn_rate', 0.8),
                variation=spawn_config.get('variation', 0.5),
                dt=sim_config.get('dt', 0.1),
                seed=sim_config.get('seed', 42),
                lane_biases=spawn_config.get('lane_biases', {}),
            )
        
        return network
    
    elif mode == 'real':
        real_config = config.get('real_map', {})
        
        network = RealTrafficNetwork(
            graphml_path=real_config.get('graphml_path'),
            sim_duration=sim_config.get('duration', 3600.0),
            spawn_rate=spawn_config.get('spawn_rate', 0.5),
            variation=spawn_config.get('variation', 0.5),
            seed=sim_config.get('seed', 42),
            control_mode=control_mode,
            map_filter=real_config.get('map_filter', 'backbone'),
            enforce_speed_limit=real_config.get('enforce_speed_limit', True),
            enforce_lanes=real_config.get('enforce_lanes', True),
            enforce_oneway=real_config.get('enforce_oneway', True),
        )
        
        # Override spawner for targeted mode
        if spawn_config.get('mode') == 'targeted':
            from core.spawning import Spawner
            network.spawner = Spawner(
                mode='targeted',
                mean_rate=spawn_config.get('spawn_rate', 0.5),
                variation=spawn_config.get('variation', 0.5),
                dt=sim_config.get('dt', 0.1),
                seed=sim_config.get('seed', 42),
                lane_map=network.lane_map,
                target_ratio=spawn_config.get('target_fraction', 0.7),
                targets=[tuple(spawn_config.get('target_coord', [0.0, 0.0]))],
            )
        
        return network
    
    else:
        raise ValueError(f"Unknown mode: {mode}")


def run_simulation(config_path: str):
    """Run simulation from YAML configuration."""
    print(f"\n{'='*70}")
    print(f"TRAFFIC SIMULATION RUNNER")
    print(f"{'='*70}")
    print(f"Config: {config_path}")
    
    # Load configuration
    config = load_config(config_path)
    sim_config = config.get('simulation', {})
    output_config = config.get('output', {})
    
    print(f"Mode: {config.get('mode', 'grid')}")
    print(f"Duration: {sim_config.get('duration', 3600.0)}s")
    print(f"Output: {output_config.get('output_dir', 'results')}")
    print(f"{'='*70}\n")
    
    # Create network
    network = create_network(config)
    
    # Create stats recorder
    stats = VectorStatsRecorder(
        network.engine,
        output_dir=output_config.get('output_dir', 'results'),
        prefix=config.get('mode', 'sim'),
        live_export=output_config.get('live_export', False)
    )
    
    # Run simulation
    duration = sim_config.get('duration', 3600.0)
    dt = sim_config.get('dt', 0.1)
    steps = int(duration / dt)
    stats_interval = sim_config.get('stats_interval', 60.0)
    stats_steps = int(stats_interval / dt)
    
    print(f"Starting simulation...")
    print(f"Total steps: {steps:,}")
    print(f"Stats interval: {stats_interval}s ({stats_steps} steps)\n")
    
    for step in range(steps):
        network.step()
        
        # Log stats periodically
        if step % stats_steps == 0:
            stats.log_step(network.time)
            progress = (step / steps) * 100
            print(f"Progress: {progress:5.1f}% | Time: {network.time:7.1f}s | "
                  f"Active: {network.engine.active_count:5d} vehicles")
    
    # Final stats
    stats.log_step(network.time)
    if hasattr(stats, 'close'):
        stats.close()
    
    print(f"\n{'='*70}")
    print(f"SIMULATION COMPLETE")
    print(f"{'='*70}")
    print(f"Output directory: {output_config.get('output_dir', 'results')}")
    print(f"Metrics file: {stats.metrics_file}")
    print(f"Trips file: {stats.trips_file}")
    print(f"{'='*70}\n")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nError: No configuration file specified")
        print("Usage: python run.py <config.yaml>")
        print("\nExample: python run.py configs/grid_baseline.yaml")
        sys.exit(1)
    
    config_path = sys.argv[1]
    
    if not Path(config_path).exists():
        print(f"Error: Configuration file not found: {config_path}")
        sys.exit(1)
    
    try:
        run_simulation(config_path)
    except Exception as e:
        print(f"\nError running simulation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
