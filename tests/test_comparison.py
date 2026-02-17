
import sys
import os
import time
import argparse

# Ensure root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.intersection import SingleIntersection
from core.signals import MODE_FIXED, MODE_ADAPTIVE
from core.stats import VectorStatsRecorder

def run_test(mode_name, mode_val, rate, duration=3600):
    # Unified output structure
    base_dir = "results"
    sub_dir = "fixed" if mode_val == MODE_FIXED else "dynamic"
    out_dir = os.path.join(base_dir, sub_dir)
    
    prefix = f"rate_{rate}"
    print(f"\n--- Running {mode_name} Control | Rate={rate} | Duration={duration}s ---")
    print(f"Output: {out_dir}/{prefix}_*")
    
    sim = SingleIntersection(spawn_rate=rate, variation=0.5, seed=42, control_mode=mode_val)
    recorder = VectorStatsRecorder(sim.engine, output_dir=out_dir, prefix=prefix)
    
    steps = int(duration / 0.1)
    t0 = time.time()
    
    for i in range(steps):
        sim.step()
        if i % 10 == 0:
            recorder.log_step(sim.engine.current_time)
        if i % 5000 == 0:
            print(f"Step {i}/{steps} | Active: {sim.engine.active_count}")
            
    dur = time.time() - t0
    stats = recorder.compute_summary()
    
    print(f"Completed {mode_name} in {dur:.2f}s")
    return stats

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rate", type=float, default=0.5, help="Spawn Rate")
    args = parser.parse_args()
    
    print(f"=== INTERSECTION CONTROL COMPARISON [ADAPTIVE MAX] (Rate={args.rate}) ===")
    
    # 1. FIXED
    fixed_stats = run_test("FIXED", MODE_FIXED, args.rate)
    
    # 2. DYNAMIC (Adaptive Max)
    # Using MODE_ADAPTIVE (1) which implements the 5-cycle MA
    dyn_stats = run_test("DYNAMIC_MA", MODE_ADAPTIVE, args.rate)
    
    # ... (Print logic handled by separate analyzer)

if __name__ == "__main__":
    main()
