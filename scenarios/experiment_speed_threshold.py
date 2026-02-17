"""
FIXED Speed Threshold Experiment

This version uses SCIENTIFICALLY CALIBRATED parameters instead of arbitrary values.

Key Improvements:
- Realistic physics timestep (0.1s instead of 0.5s)
- Proper spawn intervals based on vehicle length and speed
- Realistic lane lengths (500m - typical urban block)
- Larger batch size for statistical significance
- Reasonable timeout based on expected travel time
"""

import sys
import os
import random
from collections import deque

# Ensure parent directory (Repo Root) is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from traffic_grid.python_sim.grid_network import TrafficGridNetwork
from traffic_grid.python_sim.config import CONFIG

def run_batch_simulation(speed: float, batch_size: int = 100, lane_length: float = 500.0) -> tuple[float, float, float, int]:
    """
    Run a batch simulation with CALIBRATED parameters.
    
    Args:
        speed: Maximum vehicle speed in m/s
        batch_size: Number of vehicles to test (default: 100 for statistical significance)
        lane_length: Length of each lane segment in meters (default: 500m = typical urban block)
    
    Returns:
        (avg_travel_time, accel_fraction, cruise_fraction, exited_count)
    """
    # Patch Configuration
    original_lane_length = CONFIG["lane_length"]
    CONFIG["lane_length"] = lane_length
    
    # Create test vehicle with REALISTIC parameters
    original_specs = CONFIG["vehicle_types"].copy()
    test_spec = {
        "length": 4.5,          # Standard car length (meters)
        "accel": 2.5,           # Moderate acceleration (m/s²)
        "v_max": speed,         # Variable max speed (m/s)
        "color": [255, 0, 0]    # Red for visibility
    }
    CONFIG["vehicle_types"] = {"test_car": test_spec}
    CONFIG["spawn_probabilities"] = {"test_car": 1.0}
    
    # Force straight-line travel (no turns)
    original_turn_weights = CONFIG.get("turn_weights", [0.2, 0.6, 0.2]).copy()
    CONFIG["turn_weights"] = [0.0, 1.0, 0.0]  # [left, straight, right]

    try:
        # Create Network (Headless - no visualization)
        net = TrafficGridNetwork(
            size=5,                 # 5x5 grid = 5 intersections to cross
            spawn_rate=0.0,         # Manual spawning only
            seed=42,                # Reproducible results
            stats_interval=60,      # Log stats every 60s
            lane_length=lane_length
        )
        
        # Double-check vehicle specs
        for spec in net.vehicle_specs.values():
            if spec.name == "test_car":
                spec.accel = 2.5
                spec.v_max = speed

        # Simulation state
        cars_spawned = 0
        cars_exited = 0
        
        # Entry: Row 2, Col 0, Approach 3 (West side, traveling East)
        entry_pos = (2, 0, 3) 
        # Target: Row 2, Col 4 (East side)
        target = (2, 4)
        
        # Calculate REALISTIC spawn interval
        # Formula: time_gap = (vehicle_length + safety_gap) / speed
        # Safety gap: 2 seconds at current speed (standard traffic rule)
        vehicle_length = 4.5  # meters
        safety_gap = 2.0 * speed  # 2-second rule
        min_spawn_interval = (vehicle_length + safety_gap) / max(speed, 1.0)
        
        # Clamp to reasonable bounds
        min_spawn_interval = max(2.0, min(min_spawn_interval, 10.0))
        
        # Physics timestep - CRITICAL for accuracy
        dt = 0.1  # 100ms timestep (standard for traffic simulation)
        
        # Calculate realistic timeout
        # Expected travel time = (distance / speed) * safety_factor
        total_distance = 5 * lane_length  # 5 lanes to cross
        expected_time_per_car = (total_distance / max(speed, 1.0)) * 2.0  # 2x safety factor
        max_duration = expected_time_per_car * batch_size * 1.5  # 1.5x for spawning delays
        max_duration = min(max_duration, 3600.0)  # Cap at 1 hour
        
        print(f"  [Speed {speed:.1f} m/s] Spawn interval: {min_spawn_interval:.2f}s, "
              f"Expected time/car: {expected_time_per_car:.1f}s, Timeout: {max_duration:.0f}s")
        
        sim_time = 0.0
        spawn_queue = batch_size
        spawn_timer = 0.0
        
        while (cars_exited < batch_size) and (sim_time < max_duration):
            # 1. Spawn Logic
            spawn_timer -= dt
            if spawn_queue > 0 and spawn_timer <= 0:
                # Check if entry lane is free
                r, c, app = entry_pos
                lane_idx = 1  # Middle lane (straight)
                lane_obj = net.intersections[r][c].lanes[app][lane_idx]
                
                # Check if there's enough space (15m buffer)
                can_spawn = True
                if lane_obj:
                    last_car = lane_obj[-1]
                    if last_car.position < 15.0:
                        can_spawn = False
                
                if can_spawn:
                    # Spawn vehicle
                    car = net._build_vehicle(app, lane_idx, "straight", sim_time, target=target)
                    net._try_enqueue_vehicle(r, c, app, lane_idx, car)
                    spawn_queue -= 1
                    spawn_timer = min_spawn_interval
                    cars_spawned += 1
            
            # 2. Step Simulation
            net.step(dt)
            sim_time += dt
            
            # 3. Track exits
            cars_exited = net.exited_cars_count
            
        # Calculate statistics
        if cars_exited > 0:
            avg_travel = net.cumulative_travel_time / cars_exited
            avg_accel = net.cumulative_accel_time / cars_exited
            avg_cruise = net.cumulative_cruise_time / cars_exited
            
            # Calculate fractions
            total_motion_time = avg_accel + avg_cruise
            f_accel = avg_accel / total_motion_time if total_motion_time > 0 else 0
            f_cruise = avg_cruise / total_motion_time if total_motion_time > 0 else 0
            
            return avg_travel, f_accel, f_cruise, cars_exited
        else:
            print(f"  WARNING: Only {cars_exited}/{batch_size} cars exited (timeout after {sim_time:.1f}s)")
            return 0.0, 0.0, 0.0, 0

    finally:
        # Restore original config
        CONFIG["lane_length"] = original_lane_length
        CONFIG["vehicle_types"] = original_specs
        CONFIG["turn_weights"] = original_turn_weights

def main():
    """
    Run speed threshold experiment with CALIBRATED parameters.
    
    Tests speeds from 5 m/s to 50 m/s (18 km/h to 180 km/h)
    """
    # CALIBRATED PARAMETERS
    lane_length = 500.0     # 500m per lane (realistic urban block)
    batch_size = 100        # 100 cars for statistical significance
    
    print("=" * 80)
    print("SPEED THRESHOLD EXPERIMENT (CALIBRATED)")
    print("=" * 80)
    print(f"Configuration:")
    print(f"  - Lane length: {lane_length}m (5 lanes = {5*lane_length}m total)")
    print(f"  - Batch size: {batch_size} vehicles")
    print(f"  - Acceleration: 2.5 m/s²")
    print(f"  - Route: Straight line (no turns)")
    print(f"  - Physics timestep: 0.1s")
    print("=" * 80)
    
    csv_path = os.path.join(os.path.dirname(__file__), "results_calibrated.csv")
    with open(csv_path, "w") as f:
        f.write("Speed_ms,Speed_kmh,Travel_Time_s,Accel_Fraction,Cruise_Fraction,Exited_Cars\n")
        
        print(f"\n{'Speed (m/s)':<12} | {'Speed (km/h)':<12} | {'Travel Time':<12} | {'Exited':<8}")
        print("-" * 60)
        
        # Test speeds from 5 m/s to 50 m/s in 5 m/s increments
        for speed_ms in range(5, 55, 5):
            speed_kmh = speed_ms * 3.6  # Convert to km/h for display
            
            time_val, f_accel, f_cruise, exited = run_batch_simulation(
                float(speed_ms), 
                batch_size, 
                lane_length
            )
            
            print(f"{speed_ms:<12.1f} | {speed_kmh:<12.1f} | {time_val:<12.2f} | {exited:<8}")
            sys.stdout.flush()
            
            f.write(f"{speed_ms:.1f},{speed_kmh:.1f},{time_val:.2f},{f_accel:.4f},{f_cruise:.4f},{exited}\n")
            f.flush()
    
    print("=" * 80)
    print(f"✓ Results saved to: {csv_path}")
    print("=" * 80)

if __name__ == "__main__":
    main()
