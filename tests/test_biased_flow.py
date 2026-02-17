
import os
import sys
import numpy as np
import pandas as pd

# Ensure root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.intersection import SingleIntersection
from core.signals import MODE_FIXED, MODE_ADAPTIVE
from core.stats import VectorStatsRecorder
from core.spawning import Spawner
from core.paths import get_results_dir

def run_biased_test(rate: float, duration: int, mode: int, prefix: str):
    # Setup Biases
    # South (0,1,2) and North (6,7,8) are MAJOR (Rush Hour N-S)
    # 0 = Left (Free), 1 = Straight (Ph 2), 2 = Right (Ph 1)
    # 6 = Left (Free), 7 = Straight (Ph 2), 8 = Right (Ph 1)
    # West (3,4,5), East (9,10,11) are MINOR
    biases = {
        1: 4.0, 7: 4.0, # N/S Straight (MAJOR)
        2: 2.0, 8: 2.0, # N/S Right (MAJOR)
        # E/W get very little (MINOR)
        4: 0.2, 10: 0.2, # E/W Straight 
        5: 0.2, 11: 0.2, # E/W Right
    }

    sim = SingleIntersection(spawn_rate=rate, control_mode=mode)
    # Swap Spawner
    sim.spawner = Spawner(mode='directional', mean_rate=rate, variation=0.2, dt=0.1, lane_biases=biases)
    
    output_dir = get_results_dir("biased")
    recorder = VectorStatsRecorder(sim.engine, output_dir=output_dir, prefix=prefix)
    
    steps = int(duration / 0.1)
    print(f"--- Running {prefix} (Duration={duration}s) ---")
    
    for i in range(steps):
        sim.step()
        recorder.log_step(sim.engine.current_time)
        
        if i % 1000 == 0:
            print(f"  Step {i}/{steps} | Active: {sim.engine.active_count}")

    print(f"Completed {prefix}")

if __name__ == "__main__":
    duration = 3600
    base_rate = 0.05 # Moderate Base
    
    # Results directory created automatically by get_results_dir()
        
    print("=== BIASED FLOW TEST (N-S RUSH HOUR) ===")
    print(f"Running FIXED and DYNAMIC tests in PARALLEL using multiprocessing...")
    
    # Use multiprocessing to run both tests in parallel
    from concurrent.futures import ProcessPoolExecutor
    import time
    
    start_time = time.time()
    
    with ProcessPoolExecutor(max_workers=2) as executor:
        # Submit both tests to run in parallel
        future_fixed = executor.submit(run_biased_test, base_rate, duration, MODE_FIXED, "fixed_biased")
        future_dynamic = executor.submit(run_biased_test, base_rate, duration, MODE_ADAPTIVE, "dynamic_biased")
        
        # Wait for both to complete
        future_fixed.result()
        future_dynamic.result()
    
    elapsed = time.time() - start_time
    print(f"\n✓ Both tests completed in {elapsed:.1f}s (parallel execution)")
    
    # 3. ANALYSIS
    results_dir = get_results_dir("biased")
    f = pd.read_csv(os.path.join(results_dir, "fixed_biased_trips.csv"))
    d = pd.read_csv(os.path.join(results_dir, "dynamic_biased_trips.csv"))
    
    print("\n=== FINAL RESULTS (BIASED FLOW) ===")
    print(f"FIXED:   Trips={len(f)}, Avg Duration={f.duration.mean():.2f}s")
    print(f"DYNAMIC: Trips={len(d)}, Avg Duration={d.duration.mean():.2f}s")
    
    improvement = (f.duration.mean() - d.duration.mean()) / f.duration.mean() * 100
    print(f"IMPROVEMENT: {improvement:.2f}%")
