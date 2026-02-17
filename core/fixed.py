"""
Unified fixed/constant green time controller.

Consolidated from:
- traffic_grid/python_sim/constant_green.py
- traffic_intersection/python_sim/constant_green.py

This module provides fixed green time allocation for each approach.
"""

from __future__ import annotations

import csv
import random
from dataclasses import dataclass, field
from typing import List, Optional

DEFAULT_DT = 0.25
DEFAULT_MAX_CYCLES_MULTIPLIER = 100
DEFAULT_FIXED_GREEN = 30.0


@dataclass
class FixedGreenController:
    """
    Fixed/constant green time signal controller.
    
    Each approach receives the same fixed green time duration.
    """
    fixed_green: float = DEFAULT_FIXED_GREEN
    dt: float = DEFAULT_DT
    max_cycles_multiplier: float = DEFAULT_MAX_CYCLES_MULTIPLIER
    trials: int = 10
    rng: random.Random = field(default_factory=random.Random)
    
    # Vehicle/lane configuration
    go_gap: float = 2.0
    lane_length: float = 100.0
    
    def run_trial(self, lanes: List[List[List[object]]], trial_num: int = 1) -> dict:
        """
        Run a single trial with fixed green times.
        
        Args:
            lanes: 4 approaches x 3 sublanes x vehicles
            trial_num: Trial number for tracking
            
        Returns:
            Dictionary with trial results
        """
        initial_counts = [
            [len(lanes[a][s]) for s in range(3)] for a in range(4)
        ]
        lane_sum_wait = [[0.0 for _ in range(3)] for _ in range(4)]
        served_total = 0
        sim_time = 0.0
        approach_index = 0
        remaining_green = 0.0
        
        # Estimate max time
        total_vehicles = sum(sum(len(lane) for lane in approach) for approach in lanes)
        approx_cycle = total_vehicles * 0.85  # Assume k=0.85
        approx_cycle = max(approx_cycle, 1.0)
        T_max = approx_cycle * self.max_cycles_multiplier
        
        # Run simulation
        while approach_index < 4 and sim_time < T_max:
            if remaining_green <= 0.0:
                remaining_green = self.fixed_green
            
            a = approach_index % 4
            
            for s in range(3):
                lane = lanes[a][s]
                for idx, car in enumerate(lane):
                    leader = lane[idx - 1] if idx > 0 else None
                    front_x = leader.position if leader and hasattr(leader, 'position') else None
                    front_l = leader.spec.length if leader and hasattr(leader, 'spec') else 0.0
                    
                    if hasattr(car, 'step'):
                        car.step(self.dt, front_x, front_l, self.go_gap, 
                                can_proceed=True, reverse_dir=True, stop_pos=0.0)
                
                # Clear vehicles
                cleared = 0
                while lane and hasattr(lane[0], 'is_cleared') and lane[0].is_cleared():
                    cleared += 1
                    car = lane.pop(0)
                    if hasattr(car, 'entry_time'):
                        wait = sim_time - car.entry_time
                        lane_sum_wait[a][s] += max(0.0, wait)
                served_total += cleared
            
            sim_time += self.dt
            remaining_green -= self.dt
            
            if remaining_green <= 0.0:
                approach_index += 1
        
        # Compile results
        results = []
        for a in range(4):
            for s in range(3):
                init = initial_counts[a][s]
                left = len(lanes[a][s])
                cleared = init - left
                sum_wait = lane_sum_wait[a][s] + left * sim_time
                avg_wait = sum_wait / cleared if cleared > 0 else 0.0
                results.append({
                    'trial': trial_num,
                    'approach': a,
                    'sublane': s,
                    'initial': init,
                    'remaining': left,
                    'green_time': self.fixed_green,
                    'sum_wait': sum_wait,
                    'avg_wait': avg_wait
                })
        
        return {
            'trial': trial_num,
            'sim_time': sim_time,
            'served_total': served_total,
            'lane_results': results
        }

    def run_multiple_trials(self, lane_generator_fn, csv_path: Optional[str] = None) -> List[dict]:
        """
        Run multiple trials with fresh vehicle spawns each time.
        
        Args:
            lane_generator_fn: Function that returns fresh lanes for each trial
            csv_path: Optional path to save CSV output
            
        Returns:
            List of trial result dictionaries
        """
        all_results = []
        
        if csv_path:
            with open(csv_path, "w", newline="") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([
                    "trial", "approach", "sublane", "initial", "remaining",
                    "green_time", "sum_wait", "avg_wait"
                ])
                
                for trial in range(1, self.trials + 1):
                    lanes = lane_generator_fn()
                    result = self.run_trial(lanes, trial)
                    all_results.append(result)
                    
                    for lane_result in result['lane_results']:
                        writer.writerow([
                            lane_result['trial'],
                            lane_result['approach'],
                            lane_result['sublane'],
                            lane_result['initial'],
                            lane_result['remaining'],
                            f"{lane_result['green_time']:.2f}",
                            f"{lane_result['sum_wait']:.3f}",
                            f"{lane_result['avg_wait']:.3f}"
                        ])
        else:
            for trial in range(1, self.trials + 1):
                lanes = lane_generator_fn()
                result = self.run_trial(lanes, trial)
                all_results.append(result)
        
        return all_results

    def get_stats(self) -> dict:
        """Return controller configuration."""
        return {
            "fixed_green": self.fixed_green,
            "trials": self.trials,
            "dt": self.dt
        }
