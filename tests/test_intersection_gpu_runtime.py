"""End-to-end intersection, demand and engine contracts on the selected array backend."""
from __future__ import annotations
import numpy as np
import pytest

from core.gpu import to_numpy
from core.engine import TrafficEngine, IDX_LANE_ID, IDX_POS_ON_LANE
from core.intersection import SingleIntersection, TrafficIntersection, OUTBOUND_ARM_FOR_TURN, OUTBOUND_BASE
from core.lanes import LaneMap
from core.spawning import Spawner
from core.signals import SignalControllerVector, MODE_FIXED, MODE_ADAPTIVE


@pytest.mark.parametrize("mode", [MODE_FIXED, MODE_ADAPTIVE])
def test_intersection_has_all_12_exact_turn_connections(mode):
    sim = SingleIntersection(spawn_rate=0, lane_length=100, control_mode=mode)
    assert isinstance(sim, TrafficIntersection)
    assert sim.num_lanes == 24
    assert sim.engine.map is sim.lane_map
    assert sim.engine.signals is sim.vector_signals
    assert sim.valid_lanes == list(range(12))
    adjacency = to_numpy(sim.lane_map.adjacency)
    phase = to_numpy(sim.lane_map.signal_phase_idx)
    for approach in range(4):
        for turn in range(3):
            incoming = approach * 3 + turn
            outbound = OUTBOUND_BASE[OUTBOUND_ARM_FOR_TURN[approach][turn]] + turn
            assert sim.inbound_to_outbound[incoming] == outbound
            assert adjacency[incoming, 0] == outbound
            assert np.all(adjacency[incoming, 1:] == -1)
            assert phase[incoming] == (0 if turn == 0 else 2 * approach + (2 if turn == 1 else 1))
    assert np.all(adjacency[12:] == -1)
    sim.step(0.1)
    with pytest.raises(ValueError, match="timestep"):
        sim.step(0.5)


def test_spawner_retains_blocked_requests_and_target_identity():
    class FakeEngine:
        def __init__(self):
            self.calls = []
        def spawn_vehicles(self, count, lane_ids, positions, types, targets=None):
            self.calls.append((to_numpy(lane_ids).copy(), to_numpy(types).copy(),
                               None if targets is None else to_numpy(targets).copy()))
            return np.zeros(count, dtype=bool) if len(self.calls) == 1 else np.ones(count, dtype=bool)
    engine = FakeEngine()
    spawner = Spawner(mode="targeted", lane_map=LaneMap(2), targets=[(8., 9.)],
                      target_ratio=1.0, mean_rate=10.0, variation=0, seed=2)
    assert spawner.step([0], engine) == 0
    assert len(spawner.backlog) == 1
    assert spawner.total_spawn_count == 0
    spawner.mean = 0.0
    assert spawner.step([], engine) == 1
    assert len(spawner.backlog) == 0
    assert spawner.total_spawn_count == 1
    np.testing.assert_array_equal(engine.calls[0][1], engine.calls[1][1])
    np.testing.assert_array_equal(engine.calls[0][2], engine.calls[1][2])


def test_uniform_and_directional_modes_instantiate_without_undefined_demand_methods():
    for mode in ("uniform", "directional"):
        sim = SingleIntersection(spawn_rate=0, lane_length=80)
        sim.spawner = Spawner(mode=mode, mean_rate=0, lane_biases={1: 2.0})
        sim.step()
        assert sim.engine.active_count == 0


def test_engine_spawn_mask_retains_capacity_and_collision_failures():
    lane_map = LaneMap(2)
    lane_map.set_lane(0, 100, 13.8, [])
    lane_map.set_lane(1, 100, 13.8, [])
    engine = TrafficEngine(lane_map, SignalControllerVector(1), max_vehicles=2)
    result = engine.spawn_vehicles(
        3, np.array([0, 0, 1]), np.zeros(3),
        np.array([0, 1, 3]),
    )
    np.testing.assert_array_equal(to_numpy(result), [True, False, True])
    assert engine.active_count == 2
    assert to_numpy(engine.lengths[:2]).tolist() == [5.0, 10.0]
    np.testing.assert_array_equal(
        to_numpy(engine.spawn_vehicles(1, np.array([0]), np.zeros(1), np.array([0]))),
        [False],
    )


def test_no_spawn_request_is_counted_as_success_when_engine_returns_none():
    class NoCapacity:
        def spawn_vehicles(self, *args, **kwargs):
            return None
    spawner = Spawner(mean_rate=10, variation=0, seed=1)
    assert spawner.step([0], NoCapacity()) == 0
    assert len(spawner.backlog) == 1
    assert spawner.total_spawn_count == 0
