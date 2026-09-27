"""Deterministic vehicle demand, backlog and GPU/CPU-safe spawn dispatch.

The engine owns vehicle state and traffic physics; the spawner owns demand and
retries. A rejected spawn is never counted as completed or dropped on the floor.
The per-lane Bernoulli demand matches the retained single-step model.
"""
from __future__ import annotations

import math
import random
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as _host_np
from core.gpu import xp as np, to_numpy
from core.lanes import LaneMap

# One request remains stable across a blocked/retried spawn.
SpawnRequest = Tuple[int, int, Tuple[float, float]]


class Spawner:
    def __init__(
        self, mode: str = "uniform", mean_rate: float = 0.5,
        variation: float = 0.0, dt: float = 0.1, seed: int = 42,
        lane_map: Optional[LaneMap] = None, target_ratio: float = 0.5,
        targets: Optional[Sequence[Tuple[float, float]]] = None,
        lane_biases: Optional[Dict[int, float]] = None,
        type_weights: Optional[Sequence[float]] = None,
        lambda_decay: Optional[Dict] = None,
    ):
        if mode not in {"uniform", "targeted", "directional"}:
            raise ValueError(f"invalid spawning mode: {mode!r}")
        if not math.isfinite(mean_rate) or mean_rate < 0:
            raise ValueError("mean_rate must be finite and nonnegative")
        if not math.isfinite(variation) or not 0 <= variation <= 1:
            raise ValueError("variation must be between 0 and 1")
        if not math.isfinite(dt) or dt <= 0:
            raise ValueError("dt must be finite and positive")
        if not 0 <= target_ratio <= 1:
            raise ValueError("target_ratio must be between 0 and 1")
        if mode == "targeted" and lane_map is None:
            raise ValueError("targeted spawning requires lane_map")
        if lambda_decay is not None and lambda_decay.get("type", "exponential") not in {
            "exponential", "linear", "profile",
        }:
            raise ValueError("unsupported lambda_decay profile")

        self.mode = mode
        self.mean = float(mean_rate)
        self.var = float(variation)
        self.dt = float(dt)
        self.rng = random.Random(seed)
        self.np_rng = np.random.default_rng(seed)
        weights = list(type_weights) if type_weights is not None else [0.7, 0.1, 0.1, 0.1]
        if len(weights) not in (3, 4) or any(not math.isfinite(v) or v < 0 for v in weights) or sum(weights) <= 0:
            raise ValueError("type_weights must have three/four finite nonnegative values with positive sum")
        self.types = list(range(len(weights)))
        self.type_weights = weights
        self.weights = weights  # compatibility with existing caller expectations
        self.lane_map = lane_map
        self.target_ratio = float(target_ratio)
        self.targets = tuple(tuple(map(float, point)) for point in (targets or ()))
        if any(len(point) != 2 or not all(math.isfinite(v) for v in point) for point in self.targets):
            raise ValueError("targets must be finite (x, y) pairs")
        self.lane_biases = dict(lane_biases or {})
        if any(not math.isfinite(v) or v < 0 for v in self.lane_biases.values()):
            raise ValueError("lane_biases must be finite nonnegative multipliers")
        self.lambda_decay = dict(lambda_decay or {})
        self.decay_type = self.lambda_decay.get("type", "exponential")
        self.decay_rate = float(self.lambda_decay.get("decay_rate", 0.001))
        self.profile = sorted((float(t), float(v)) for t, v in self.lambda_decay.get("profile", ()))
        if self.profile and (any(t < 0 or v < 0 or not math.isfinite(t + v) for t, v in self.profile)
                             or any(right[0] <= left[0] for left, right in zip(self.profile, self.profile[1:]))):
            raise ValueError("lambda_decay profile times must increase and rates must be finite nonnegative")
        if not math.isfinite(self.decay_rate) or self.decay_rate < 0:
            raise ValueError("decay_rate must be finite and nonnegative")
        self.current_time = 0.0
        self.backlog: List[SpawnRequest] = []
        self.period_spawn_count = 0
        self.total_spawn_count = 0

    def get_current_rate(self) -> float:
        if not self.lambda_decay:
            return self.mean
        if self.decay_type == "exponential":
            return self.mean * math.exp(-self.decay_rate * self.current_time)
        if self.decay_type == "linear":
            return max(0.0, self.mean - self.decay_rate * self.current_time)
        if not self.profile:
            return self.mean
        if self.current_time <= self.profile[0][0]:
            return self.profile[0][1]
        if self.current_time >= self.profile[-1][0]:
            return self.profile[-1][1]
        for (t0, r0), (t1, r1) in zip(self.profile, self.profile[1:]):
            if t0 <= self.current_time <= t1:
                return r0 + (r1 - r0) * (self.current_time - t0) / (t1 - t0)
        raise AssertionError("validated lambda_decay profile has no interval")

    def _new_requests(self, entry_lane_ids: Sequence[int]) -> None:
        base_rate = self.get_current_rate()
        sampled_rate = self.rng.uniform(
            max(0.0, base_rate * (1 - self.var)), base_rate * (1 + self.var),
        )
        for lane_id in entry_lane_ids:
            bias = self.lane_biases.get(int(lane_id), 1.0) if self.mode == "directional" else 1.0
            probability = min(1.0, sampled_rate * bias * self.dt)
            if self.rng.random() >= probability:
                continue
            vehicle_type = self.rng.choices(self.types, weights=self.weights, k=1)[0]
            target = (-1.0, -1.0)
            if self.mode == "targeted" and self.targets and self.rng.random() < self.target_ratio:
                target = self.rng.choice(self.targets)
            self.backlog.append((int(lane_id), int(vehicle_type), target))

    def _flush(self, engine) -> int:
        if not self.backlog:
            return 0
        requests = self.backlog
        count = len(requests)
        lane_ids = np.asarray([item[0] for item in requests], dtype=np.int32)
        positions = np.zeros(count, dtype=np.float32)
        types = np.asarray([item[1] for item in requests], dtype=np.int32)
        targets = None
        if any(item[2] != (-1.0, -1.0) for item in requests):
            targets = np.asarray([item[2] for item in requests], dtype=np.float32)
        success_mask = engine.spawn_vehicles(count, lane_ids, positions, types, targets=targets)
        # Current engine returns a mask. None means no confirmed successes (full
        # capacity / occupied starts); do not silently count requests as spawned.
        mask = (_host_np.zeros(count, dtype=bool) if success_mask is None
                else _host_np.asarray(to_numpy(success_mask), dtype=bool))
        if mask.shape != (count,):
            raise RuntimeError("vehicle engine returned an invalid spawn success mask")
        self.backlog = [item for item, accepted in zip(requests, mask) if not accepted]
        spawned = int(mask.sum())
        self.period_spawn_count += spawned
        self.total_spawn_count += spawned
        return spawned

    def step(self, entry_lane_ids: Sequence[int], engine) -> int:
        if not entry_lane_ids and not self.backlog:
            return 0
        self.current_time += self.dt
        self._new_requests(entry_lane_ids)
        return self._flush(engine)

    def _spawn_uniform(self, entry_lane_ids: Sequence[int], engine) -> int:
        return self.step(entry_lane_ids, engine)

    def _spawn_targeted(self, entry_lane_ids: Sequence[int], engine) -> int:
        return self.step(entry_lane_ids, engine)

    def _spawn_directional(self, entry_lane_ids: Sequence[int], engine) -> int:
        return self.step(entry_lane_ids, engine)


TrafficSpawner = Spawner


def TargetedSpawner(**kwargs):
    return Spawner(mode="targeted", **kwargs)
