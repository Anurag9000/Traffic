"""
Unified dynamic-k intersection controller.

Consolidated from:
- traffic_grid/python_sim/dynamic.py
- traffic_intersection/python_sim/dynamic.py

This module provides dynamic green time allocation based on queue length (k-factor).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional

# Default constants
DEFAULT_DT = 0.25
DEFAULT_MAX_CYCLES_MULTIPLIER = 100
DEFAULT_K = 0.85
DEFAULT_MIN_GREEN = 5.0


@dataclass
class DynamicIntersectionController:
    """
    Dynamic-k signal controller.
    
    Allocates green time proportional to queue length using k-factor:
    green_time = max(min_green, k * queue_length)
    """
    k: float = DEFAULT_K
    min_green: float = DEFAULT_MIN_GREEN
    dt: float = DEFAULT_DT
    max_cycles_multiplier: float = DEFAULT_MAX_CYCLES_MULTIPLIER
    rng: random.Random = field(default_factory=random.Random)
    
    # Vehicle/lane configuration (can be injected)
    vehicle_spec: Optional[object] = None
    go_gap: float = 2.0
    lane_length: float = 100.0
    
    def __post_init__(self):
        """Initialize simulation state."""
        self.lanes: List[List[List[object]]] = []
        self.lane_cleared_time: List[List[Optional[float]]] = []
        self.initial_counts: List[List[int]] = []
        self.total_initial: int = 0
        self.served_total: int = 0
        self.sim_time: float = 0.0
        self.approach_index: int = 0
        self.remaining_green: float = 0.0
        self.T_max: float = 0.0
        self.running: bool = False

    def initialize_lanes(self, lanes: List[List[List[object]]]) -> None:
        """
        Initialize with pre-spawned vehicle lanes.
        
        Args:
            lanes: 4 approaches x 3 sublanes x vehicles
        """
        self.lanes = lanes
        self.initial_counts = [
            [len(self.lanes[a][s]) for s in range(3)] for a in range(4)
        ]
        self.total_initial = sum(sum(row) for row in self.initial_counts)
        self.lane_cleared_time = [[None for _ in range(3)] for _ in range(4)]
        
        # Estimate max simulation time
        approx_cycle = sum(sum(len(self.lanes[a][s]) for s in range(3)) for a in range(4)) * self.k
        approx_cycle = max(approx_cycle, 1.0)
        self.T_max = approx_cycle * self.max_cycles_multiplier
        self.running = True

    def current_approach(self) -> int:
        """Get current active approach index."""
        return self.approach_index % 4

    def total_on_approach(self, a: int) -> int:
        """Get total vehicles on approach a."""
        return sum(len(self.lanes[a][s]) for s in range(3))

    def schedule_green(self) -> None:
        """Calculate green time for current approach based on queue length."""
        a = self.current_approach()
        q = self.total_on_approach(a)
        self.remaining_green = (
            self.min_green if q == 0 else max(self.min_green, self.k * float(q))
        )

    def step(self) -> bool:
        """
        Execute one simulation step.
        
        Returns:
            True if simulation should continue, False if complete
        """
        if self.served_total >= self.total_initial or self.sim_time >= self.T_max:
            self.running = False
            return False
        
        if self.remaining_green <= 0.0:
            self.schedule_green()
        
        a = self.current_approach()
        
        # Process each sublane
        for s in range(3):
            lane = self.lanes[a][s]
            if not lane:
                if self.lane_cleared_time[a][s] is None:
                    self.lane_cleared_time[a][s] = self.sim_time
                continue
            
            # Update vehicle positions (requires vehicle objects with step method)
            for idx, car in enumerate(lane):
                leader = lane[idx - 1] if idx > 0 else None
                front_x = leader.position if leader else None
                front_l = leader.spec.length if leader and hasattr(leader, 'spec') else 0.0
                
                # Call vehicle step method if available
                if hasattr(car, 'step'):
                    car.step(self.dt, front_x, front_l, self.go_gap, True, stop_pos=0.0)
            
            # Remove cleared vehicles
            popped = False
            while lane and hasattr(lane[0], 'is_cleared') and lane[0].is_cleared():
                lane.pop(0)
                self.served_total += 1
                popped = True
            
            if popped and not lane and self.lane_cleared_time[a][s] is None:
                self.lane_cleared_time[a][s] = self.sim_time
        
        self.sim_time += self.dt
        self.remaining_green -= self.dt
        
        if self.remaining_green <= 0.0:
            self.approach_index += 1
        
        return True

    def get_vehicle_positions(self) -> List[tuple[int, int, float]]:
        """Get all vehicle positions for visualization."""
        result = []
        for a in range(4):
            for s in range(3):
                for car in self.lanes[a][s]:
                    if hasattr(car, 'position'):
                        result.append((a, s, car.position))
        return result

    def get_stats(self) -> dict:
        """Return current simulation statistics."""
        return {
            "served_total": self.served_total,
            "total_initial": self.total_initial,
            "sim_time": self.sim_time,
            "current_approach": self.current_approach(),
            "remaining_green": self.remaining_green,
            "completion_rate": self.served_total / max(1, self.total_initial),
            "lane_cleared_times": self.lane_cleared_time
        }
