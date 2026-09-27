"""GPU-first IDM physics retains the selected array backend and CPU parity."""
from unittest import mock

import numpy as np

from core import physics
from core.gpu import xp, to_numpy


def test_idm_cpu_gpu_backend_parity():
    pos = np.array([100.0, 90.0, 70.0], dtype=np.float32)
    vel = np.array([12.0, 11.0, 8.0], dtype=np.float32)
    lanes = np.array([0, 0, 0], dtype=np.int32)
    lengths = np.full(3, 5.0, dtype=np.float32)
    desired = np.full(3, 25.0, dtype=np.float32)
    accel = np.full(3, 2.0, dtype=np.float32)
    decel = np.full(3, 3.0, dtype=np.float32)
    fields = (pos, vel, lanes, lengths, desired, accel, decel)
    with mock.patch.object(physics, "xp", np):
        expected = physics.calculate_idm_vectorized(*fields)
    actual = physics.calculate_idm_vectorized(*(xp.asarray(field) for field in fields))
    assert isinstance(actual, xp.ndarray)
    np.testing.assert_allclose(to_numpy(actual), expected, rtol=1e-5, atol=1e-5)


def test_empty_idm_result_uses_selected_backend():
    result = physics.calculate_idm_vectorized(*([xp.asarray([])] * 7))
    assert isinstance(result, xp.ndarray)
    assert result.size == 0
