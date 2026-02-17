"""
Unified adaptive intersection controller.

Consolidated from:
- traffic_grid/python_sim/adaptive.py
- traffic_intersection/python_sim/adaptive.py

This module provides queue-based adaptive signal control using weighted priorities.
"""

from __future__ import annotations

import csv
import random
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, List, Optional

# Constants (can be overridden via parameters)
DEFAULT_DT = 0.25
DEFAULT_MAX_CYCLES_MULTIPLIER = 100


def weighted_priority(p: int) -> float:
    """Return weight for priority level - ALL VEHICLES EQUAL PRIORITY."""
    # FIXED: Removed priority hierarchy - all vehicles treated equally
    return 1.0  # Equal priority for all vehicles regardless of type


@dataclass
class AdaptiveIntersectionController:
    """
    Adaptive signal controller using queue-based weighted priority.
    
    Dynamically adjusts green time based on weighted vehicle counts in each approach.
    """
    arrival_rate: List[float] = field(default_factory=lambda: [0.6, 0.8, 0.5, 0.7])
    sat_flow: float = 1.0
    total_cycle_base: float = 60.0
    min_green: float = 5.0
    max_green: float = 180.0
    print_interval: float = 10.0
    rng: random.Random = field(default_factory=random.Random)
    max_seconds: int = 3600
    dt: float = DEFAULT_DT

    def __post_init__(self):
        self.queues: List[Deque[tuple[float, int]]] = [deque() for _ in range(4)]
        self.next_arrival: List[float] = [
            self._sample_next(a) for a in range(4)
        ]
        self.stats_total_passed = 0
        self.stats_wait_by_prio = {1: 0.0, 2: 0.0, 3: 0.0}
        self.weighted_wait = 0.0
        self.time_sec = 0.0
        self.phase_rem = self.min_green
        self.phase = 0  # 0 -> NS, 1 -> EW
        self.ns_green = self.min_green
        self.ew_green = self.min_green
        self._flow_accum = [0.0 for _ in range(4)]

    def _sample_next(self, approach: int) -> float:
        """Sample next arrival time using exponential distribution."""
        rate = max(0.0, self.arrival_rate[approach])
        if rate <= 0.0:
            return float("inf")
        return self.rng.expovariate(rate)

    def _weighted_count(self, inds: List[int]) -> float:
        """Calculate weighted vehicle count for given approaches."""
        total = 0.0
        for idx in inds:
            for _, pr in self.queues[idx]:
                total += weighted_priority(pr)
        return total

    def _dequeue(self, approach: int) -> None:
        """Process vehicles leaving the queue based on saturation flow."""
        self._flow_accum[approach] += self.sat_flow * self.dt
        while self._flow_accum[approach] >= 1.0:
            if not self.queues[approach]:
                self._flow_accum[approach] = 0.0
                break
            t0, pr = self.queues[approach].popleft()
            self._flow_accum[approach] -= 1.0
            wait = self.time_sec - t0
            self.stats_total_passed += 1
            self.stats_wait_by_prio[pr] += wait
            self.weighted_wait += weighted_priority(pr) * wait

    def step(self) -> None:
        """Execute one simulation step."""
        # Process arrivals
        for approach in range(4):
            while self.time_sec >= self.next_arrival[approach]:
                pr = self.rng.choices([1, 2, 3], weights=[6, 3, 1], k=1)[0]
                self.queues[approach].append((self.time_sec, pr))
                self.next_arrival[approach] += self._sample_next(approach)
        
        # Process departures based on current phase
        if self.phase == 0:
            for a in (0, 2):  # North, South
                self._dequeue(a)
        else:
            for a in (1, 3):  # East, West
                self._dequeue(a)
        
        # Update time and phase
        self.time_sec += self.dt
        self.phase_rem -= self.dt
        if self.phase_rem <= 0:
            self._switch_phase()
            self.phase_rem = self.ns_green if self.phase == 0 else self.ew_green

    def _switch_phase(self) -> None:
        """Switch signal phase and recalculate green times based on demand."""
        self.phase = 1 - self.phase
        w_ns = self._weighted_count([0, 2])
        w_ew = self._weighted_count([1, 3])
        total = w_ns + w_ew
        
        if total > 1e-9:
            ns = max(self.min_green, round((w_ns / total) * self.total_cycle_base))
            ew = max(self.min_green, round((w_ew / total) * self.total_cycle_base))
        else:
            ns = ew = self.min_green
        
        self.ns_green = min(ns, self.max_green)
        self.ew_green = min(ew, self.max_green)
        self.phase_rem = self.ns_green if self.phase == 0 else self.ew_green

    def run(self, csv_path: Optional[str] = None) -> None:
        """
        Run simulation until max_seconds.
        
        Args:
            csv_path: Optional path to save CSV output
        """
        if csv_path:
            with open(csv_path, "w", newline="") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([
                    "time_sec", "phase", "ns_green", "ew_green",
                    "queueN", "queueE", "queueS", "queueW",
                    "total_passed", "weighted_wait"
                ])
                while self.time_sec < self.max_seconds:
                    writer.writerow([
                        self.time_sec,
                        "NS" if self.phase == 0 else "EW",
                        self.ns_green,
                        self.ew_green,
                        *(len(q) for q in self.queues),
                        self.stats_total_passed,
                        f"{self.weighted_wait:.2f}",
                    ])
                    self.step()
        else:
            while self.time_sec < self.max_seconds:
                self.step()

    def get_stats(self) -> dict:
        """Return current simulation statistics."""
        return {
            "total_passed": self.stats_total_passed,
            "weighted_wait": self.weighted_wait,
            "avg_wait_by_priority": {
                p: (self.stats_wait_by_prio[p] / max(1, self.stats_total_passed))
                for p in [1, 2, 3]
            },
            "queue_lengths": [len(q) for q in self.queues],
            "current_phase": "NS" if self.phase == 0 else "EW",
            "time_sec": self.time_sec
        }
