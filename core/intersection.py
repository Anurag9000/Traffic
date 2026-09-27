"""Single four-approach NEMA intersection built on the vector traffic engine.

Lane IDs 0..11 are inbound, grouped South/West/North/East with left,
straight and right lanes in that order. 12..23 are outbound links. Vehicles
cross the stop line into their corresponding outbound link and exit at its end,
so observed trips include traversal rather than disappearing at the stop line.
"""
from __future__ import annotations

import math
from typing import Dict, Optional

from core.engine import TrafficEngine
from core.lanes import LaneMap
from core.signals import MODE_ADAPTIVE, SignalControllerVector
from core.spawning import Spawner

DT = 0.1
# Outbound approaches: South, East, North, West.
OUTBOUND_BASE = (12, 15, 18, 21)
OUTBOUND_ENDPOINTS = ((0.0, -1.0), (1.0, 0.0), (0.0, 1.0), (-1.0, 0.0))
# Inbound: South -> N; West -> E; North -> S; East -> W.
# Per turn (left, straight, right), select the outbound compass arm.
OUTBOUND_ARM_FOR_TURN = (
    (3, 2, 1),  # from South: West, North, East
    (2, 1, 0),  # from West: North, East, South
    (1, 0, 3),  # from North: East, South, West
    (0, 3, 2),  # from East: South, West, North
)
# Mirror the existing GridAdapter's single-NEMA-controller mapping.
PHASE_BY_TURN = (
    (0, 2, 1),
    (0, 4, 3),
    (0, 6, 5),
    (0, 8, 7),
)


class TrafficIntersection:
    def __init__(
        self, spawn_rate: float = 1.0, variation: float = 0.5,
        seed: int = 42, lane_length: float = 400.0,
        control_mode: int = MODE_ADAPTIVE,
        lane_biases: Optional[Dict[int, float]] = None,
    ):
        if not math.isfinite(lane_length) or lane_length <= 0:
            raise ValueError("lane_length must be positive and finite")
        self.lane_length = float(lane_length)
        self.dt = DT
        self.num_lanes = 24
        self.lane_map = LaneMap(self.num_lanes)
        self.outbound_length = max(20.0, min(50.0, self.lane_length / 4.0))
        self.inbound_to_outbound: dict[int, int] = {}

        for arm, base in enumerate(OUTBOUND_BASE):
            direction = OUTBOUND_ENDPOINTS[arm]
            endpoint = (direction[0] * self.outbound_length,
                        direction[1] * self.outbound_length)
            for turn in range(3):
                self.lane_map.set_lane(
                    base + turn, self.outbound_length, 13.8, [],
                    signal_node=0, signal_phase=0, endpoint=endpoint,
                )

        for approach in range(4):
            for turn in range(3):
                inbound = approach * 3 + turn
                target_arm = OUTBOUND_ARM_FOR_TURN[approach][turn]
                outbound = OUTBOUND_BASE[target_arm] + turn
                self.inbound_to_outbound[inbound] = outbound
                self.lane_map.set_lane(
                    inbound, self.lane_length, 13.8, [outbound],
                    signal_node=0, signal_phase=PHASE_BY_TURN[approach][turn],
                    endpoint=(0.0, 0.0),
                )

        self.vector_signals = SignalControllerVector(1, mode=control_mode)
        self.engine = TrafficEngine(
            self.lane_map, self.vector_signals, max_vehicles=5000, dt=self.dt,
        )
        self.spawner = Spawner(
            mode="directional" if lane_biases else "uniform",
            mean_rate=spawn_rate, variation=variation, dt=self.dt,
            seed=seed, lane_biases=lane_biases,
        )
        self.valid_lanes = list(range(12))

    def step(self, dt: float | None = None) -> None:
        if dt is not None and not math.isclose(float(dt), self.dt, abs_tol=1e-12):
            raise ValueError("intersection timestep must match its vector engine")
        self.spawner.step(self.valid_lanes, self.engine)
        self.engine.step()

    def run(self, steps: int = 1000) -> None:
        if steps < 0:
            raise ValueError("steps must be nonnegative")
        for _ in range(steps):
            self.step()


# Preserve historic scenario entrypoints; both names are the same implementation.
SingleIntersection = TrafficIntersection
