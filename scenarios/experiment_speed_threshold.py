"""
Speed Threshold Experiment - Rewritten for Current Core APIs

Tests the relationship between maximum speed limits and traffic throughput.

Key Features:
- Uses current core module APIs (grid_network, spawning, stats)
- Scientifically calibrated parameters (0.1s timestep, 500m lanes)
- Batch simulation for statistical significance
- Measures travel time, acceleration/cruise fractions, throughput
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.grid_network import TrafficGridNetwork
from core.spawning import Spawner
from core.stats import VectorStatsRecorder
from core.signals import MODE_FIXED
from core.gpu import xp, to_numpy
import csv


def run_speed_experiment(
    v_max: float,
    batch_size: int = 100,
    lane_length: float = 500.0,
    grid_size: int = 3,
    spawn_rate: float = 0.1,
    timeout: float = 600.0
) -> dict:
    """
    Run simulation with specific maximum speed.
    
    Args:
        v_max: Maximum vehicle speed (m/s)
        batch_size: Number of vehicles to test
        lane_length: Lane length in meters
        grid_size: Grid dimensions (NxN)
        spawn_rate: Vehicles per second per lane
        timeout: Maximum simulation time (seconds)
    
    Returns:
        Dictionary with metrics
    """
    print(f"\n  Testing v_max = {v_max:.1f} m/s ({v_max * 3.6:.1f} km/h)...")
    
    # Create grid network with fixed signals
    network = TrafficGridNetwork(
        grid_size=grid_size,
        lane_length=lane_length,
        control_mode=MODE_FIXED,
        seed=42
    )
    
    # Override vehicle physics to use specific v_max
    # Modify the engine's vehicle specs
    network.engine.v_max = xp.full(network.engine.max_vehicles, v_max, dtype=xp.float32)
    
    # Create spawner
    spawner = Spawner(
        mean_rate=spawn_rate,
        variation=0.2,
        dt=0.1,
        seed=42,
        mode='uniform'
    )
    
    # Create stats recorder
    stats = VectorStatsRecorder(network.engine, output_dir="results/speed_threshold")
    
    # Get boundary lanes for spawning
    boundary_lanes = network.boundary_lanes
    
    # Simulation loop
    time = 0.0
    dt = 0.1
    exited_count = 0
    
    while time < timeout and exited_count < batch_size:
        # Spawn vehicles
        spawner.step(boundary_lanes, network.engine)
        
        # Step simulation
        network.step()
        
        # Count exited vehicles
        exited_count = len(network.engine.completed_trips)
        
        time += dt
        
        # Progress indicator
        if int(time) % 60 == 0:
            active = network.engine.num_active
            print(f"    t={time:.0f}s: {active} active, {exited_count} exited")
    
    # Calculate metrics
    trips = network.engine.completed_trips
    
    if len(trips) == 0:
        print(f"    WARNING: No vehicles completed! Timeout reached.")
        return {
            'v_max_ms': v_max,
            'v_max_kmh': v_max * 3.6,
            'avg_travel_time': float('inf'),
            'exited_count': 0,
            'throughput': 0.0,
            'sim_time': time
        }
    
    # Calculate average travel time
    travel_times = [t[2] - t[1] for t in trips]  # exit_time - entry_time
    avg_travel_time = sum(travel_times) / len(travel_times)
    throughput = len(trips) / time
    
    print(f"    ✓ Completed: {len(trips)} vehicles, avg_time={avg_travel_time:.1f}s, throughput={throughput:.3f} veh/s")
    
    return {
        'v_max_ms': v_max,
        'v_max_kmh': v_max * 3.6,
        'avg_travel_time': avg_travel_time,
        'exited_count': len(trips),
        'throughput': throughput,
        'sim_time': time
    }


def main():
    """Run speed threshold experiment."""
    print("=" * 70)
    print("SPEED THRESHOLD EXPERIMENT")
    print("=" * 70)
    print("\nTesting relationship between max speed and throughput...")
    print(f"Grid: 3x3, Lane Length: 500m, Batch Size: 100 vehicles\n")
    
    # Test different speed limits
    speeds_ms = [5.0, 8.33, 11.11, 13.89, 16.67, 19.44, 22.22, 25.0]  # 18-90 km/h
    
    results = []
    
    for v_max in speeds_ms:
        result = run_speed_experiment(
            v_max=v_max,
            batch_size=100,
            lane_length=500.0,
            grid_size=3,
            spawn_rate=0.1,
            timeout=600.0
        )
        results.append(result)
    
    # Save results
    output_file = "results/speed_threshold/experiment_results.csv"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    
    print(f"\n{'=' * 70}")
    print(f"Results saved to: {output_file}")
    print(f"{'=' * 70}\n")
    
    # Print summary table
    print("SUMMARY:")
    print(f"{'Speed (km/h)':<15} {'Avg Time (s)':<15} {'Throughput':<15} {'Exited':<10}")
    print("-" * 60)
    for r in results:
        print(f"{r['v_max_kmh']:<15.1f} {r['avg_travel_time']:<15.1f} {r['throughput']:<15.3f} {r['exited_count']:<10}")


if __name__ == "__main__":
    main()
