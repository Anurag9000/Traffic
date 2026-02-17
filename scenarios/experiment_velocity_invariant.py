"""
Velocity Invariance Experiment - Rewritten for Current Core APIs

Tests whether travel time remains constant when both lane length and 
vehicle speed are scaled proportionally.

Hypothesis: If we scale both lane_length and v_max by the same factor,
travel time should remain approximately constant (velocity invariance).

Example:
- Scenario A: lane_length=100m, v_max=30 km/h
- Scenario B: lane_length=133m, v_max=40 km/h
- Expected: Similar travel times (invariance holds)
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


def run_invariance_test(
    lane_length: float,
    v_max: float,
    duration: float = 300.0,
    grid_size: int = 3,
    spawn_rate: float = 0.2,
    seed: int = 42
) -> dict:
    """
    Run simulation with specific lane length and max speed.
    
    Args:
        lane_length: Lane length in meters
        v_max: Maximum vehicle speed (m/s)
        duration: Simulation duration (seconds)
        grid_size: Grid dimensions (NxN)
        spawn_rate: Vehicles per second per lane
        seed: Random seed
    
    Returns:
        Dictionary with metrics
    """
    print(f"\n  Testing: lane_length={lane_length:.1f}m, v_max={v_max:.2f} m/s ({v_max * 3.6:.1f} km/h)...")
    
    # Create grid network with fixed signals for determinism
    network = TrafficGridNetwork(
        grid_size=grid_size,
        lane_length=lane_length,
        control_mode=MODE_FIXED,
        seed=seed
    )
    
    # Override vehicle physics to use specific v_max
    network.engine.v_max = xp.full(network.engine.max_vehicles, v_max, dtype=xp.float32)
    
    # Create spawner with fixed seed for reproducibility
    spawner = Spawner(
        mean_rate=spawn_rate,
        variation=0.1,
        dt=0.1,
        seed=seed,
        mode='uniform'
    )
    
    # Get boundary lanes
    boundary_lanes = network.boundary_lanes
    
    # Simulation loop
    time = 0.0
    dt = 0.1
    
    while time < duration:
        # Spawn vehicles
        spawner.step(boundary_lanes, network.engine)
        
        # Step simulation
        network.step()
        
        time += dt
        
        # Progress indicator
        if int(time) % 60 == 0:
            active = network.engine.num_active
            exited = len(network.engine.completed_trips)
            print(f"    t={time:.0f}s: {active} active, {exited} exited")
    
    # Calculate metrics
    trips = network.engine.completed_trips
    
    if len(trips) == 0:
        print(f"    WARNING: No vehicles completed!")
        return {
            'lane_length': lane_length,
            'v_max_ms': v_max,
            'v_max_kmh': v_max * 3.6,
            'avg_travel_time': float('inf'),
            'exited_count': 0,
            'throughput': 0.0
        }
    
    # Calculate average travel time
    travel_times = [t[2] - t[1] for t in trips]  # exit_time - entry_time
    avg_travel_time = sum(travel_times) / len(travel_times)
    throughput = len(trips) / duration
    
    print(f"    ✓ Completed: {len(trips)} vehicles, avg_time={avg_travel_time:.1f}s, throughput={throughput:.3f} veh/s")
    
    return {
        'lane_length': lane_length,
        'v_max_ms': v_max,
        'v_max_kmh': v_max * 3.6,
        'avg_travel_time': avg_travel_time,
        'exited_count': len(trips),
        'throughput': throughput
    }


def main():
    """Run velocity invariance experiment."""
    print("=" * 70)
    print("VELOCITY INVARIANCE EXPERIMENT")
    print("=" * 70)
    print("\nTesting whether travel time remains constant when lane_length")
    print("and v_max are scaled proportionally...\n")
    
    # Base scenario: 100m lanes, 30 km/h (8.33 m/s)
    base_length = 100.0
    base_speed_kmh = 30.0
    base_speed_ms = base_speed_kmh / 3.6
    
    # Scaled scenario: 40 km/h (1.33x faster)
    scale_factor = 40.0 / 30.0
    scaled_length = base_length * scale_factor
    scaled_speed_kmh = 40.0
    scaled_speed_ms = scaled_speed_kmh / 3.6
    
    print(f"Scenario A (Base):")
    print(f"  Lane Length: {base_length:.1f}m")
    print(f"  Max Speed: {base_speed_kmh:.1f} km/h ({base_speed_ms:.2f} m/s)")
    print(f"\nScenario B (Scaled {scale_factor:.2f}x):")
    print(f"  Lane Length: {scaled_length:.1f}m")
    print(f"  Max Speed: {scaled_speed_kmh:.1f} km/h ({scaled_speed_ms:.2f} m/s)")
    print(f"\nExpected: Similar travel times (velocity invariance)\n")
    
    # Run both scenarios
    results = []
    
    # Scenario A
    result_a = run_invariance_test(
        lane_length=base_length,
        v_max=base_speed_ms,
        duration=300.0,
        grid_size=3,
        spawn_rate=0.2,
        seed=42
    )
    results.append(result_a)
    
    # Scenario B
    result_b = run_invariance_test(
        lane_length=scaled_length,
        v_max=scaled_speed_ms,
        duration=300.0,
        grid_size=3,
        spawn_rate=0.2,
        seed=42
    )
    results.append(result_b)
    
    # Save results
    output_file = "results/velocity_invariance/experiment_results.csv"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    
    print(f"\n{'=' * 70}")
    print(f"Results saved to: {output_file}")
    print(f"{'=' * 70}\n")
    
    # Analysis
    print("ANALYSIS:")
    print(f"{'Scenario':<15} {'Lane (m)':<12} {'Speed (km/h)':<15} {'Avg Time (s)':<15} {'Exited':<10}")
    print("-" * 70)
    print(f"{'A (Base)':<15} {result_a['lane_length']:<12.1f} {result_a['v_max_kmh']:<15.1f} {result_a['avg_travel_time']:<15.1f} {result_a['exited_count']:<10}")
    print(f"{'B (Scaled)':<15} {result_b['lane_length']:<12.1f} {result_b['v_max_kmh']:<15.1f} {result_b['avg_travel_time']:<15.1f} {result_b['exited_count']:<10}")
    
    # Calculate difference
    if result_a['avg_travel_time'] != float('inf') and result_b['avg_travel_time'] != float('inf'):
        diff = abs(result_a['avg_travel_time'] - result_b['avg_travel_time'])
        diff_pct = (diff / result_a['avg_travel_time']) * 100
        print(f"\nTime Difference: {diff:.1f}s ({diff_pct:.1f}%)")
        
        if diff_pct < 10:
            print("✓ INVARIANCE HOLDS: Travel times are similar (< 10% difference)")
        else:
            print("✗ INVARIANCE VIOLATED: Travel times differ significantly (> 10%)")
    else:
        print("\n✗ EXPERIMENT FAILED: Insufficient data")


if __name__ == "__main__":
    main()
