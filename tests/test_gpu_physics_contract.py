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


def test_idm_promotes_numpy_origin_fields_to_selected_backend():
    pos = np.array([100.0, 90.0, 70.0], dtype=np.float32)
    vel = np.array([12.0, 11.0, 8.0], dtype=np.float32)
    lanes = np.array([0, 0, 0], dtype=np.int32)
    fields = (pos, vel, lanes, np.full(3, 5.0, np.float32),
              np.full(3, 25.0, np.float32), np.full(3, 2.0, np.float32),
              np.full(3, 3.0, np.float32))
    with mock.patch.object(physics, "xp", np):
        expected = physics.calculate_idm_vectorized(*fields)
    actual = physics.calculate_idm_vectorized(*fields)
    assert isinstance(actual, xp.ndarray)
    np.testing.assert_allclose(to_numpy(actual), expected, rtol=1e-5, atol=1e-5)


def test_kinematics_promotes_numpy_origin_fields_to_selected_backend():
    positions = np.array([0.0, 10.0])
    velocities = np.array([1.0, 2.0])
    accelerations = np.array([0.5, -1.0])
    position_out, velocity_out = physics.update_kinematics(
        positions, velocities, accelerations, 0.5
    )
    assert isinstance(position_out, xp.ndarray)
    assert isinstance(velocity_out, xp.ndarray)
    np.testing.assert_allclose(to_numpy(velocity_out), [1.25, 1.5])
    np.testing.assert_allclose(to_numpy(position_out), [0.625, 10.75])


def test_empty_idm_result_uses_selected_backend():
    result = physics.calculate_idm_vectorized(*([xp.asarray([])] * 7))
    assert isinstance(result, xp.ndarray)
    assert result.size == 0


def test_central_cpu_admission_disables_cupy_in_subprocess():
    import os
    from pathlib import Path
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, OPF_ADP_DISABLE_GPU_ACCELERATORS="1",
               CUDA_VISIBLE_DEVICES="0")
    child = subprocess.run(
        [sys.executable, "-c", "from core.gpu import USING_GPU, xp; print('BACKEND=' + ('cupy' if USING_GPU else xp.__name__))"],
        cwd=root, env=env, text=True, capture_output=True, check=False,
    )
    assert child.returncode == 0, child.stderr
    assert child.stdout.strip().endswith("BACKEND=numpy")


def test_all_cpu_admission_aliases_override_usable_cupy():
    """Even a usable GPU must not escape an independently selected CPU policy."""
    import os
    import runpy
    import sys
    import types
    from pathlib import Path

    fake_cupy = types.ModuleType("cupy")
    fake_cupy.zeros = np.zeros
    fake_cupy.asnumpy = np.asarray
    fake_cupy.cuda = types.SimpleNamespace(
        Device=lambda: types.SimpleNamespace(name="fixture CUDA", mem_info=(1024, 2048))
    )
    backend_path = Path(__file__).resolve().parents[1] / "core" / "gpu.py"
    cpu_policies = (
        {"CPU_ONLY": "1"},
        {"TRAINING_CONTROL_CPU_ONLY": "1"},
        {"OPF_ADP_DISABLE_GPU_ACCELERATORS": "1"},
        {"TRAFFIC_FORCE_CPU": "true"},
        {"CUDA_VISIBLE_DEVICES": ""},
        {"CUDA_VISIBLE_DEVICES": "-1"},
        {"CUDA_VISIBLE_DEVICES": "   "},
    )
    for policy in cpu_policies:
        with mock.patch.dict(os.environ, policy, clear=True), mock.patch.dict(
            sys.modules, {"cupy": fake_cupy}
        ):
            namespace = runpy.run_path(str(backend_path))
        assert namespace["FORCE_CPU"] is True, policy
        assert namespace["USING_GPU"] is False, policy
        assert namespace["xp"] is np, policy

    # A non-masked, CPU-unrestricted process must remain GPU-first.
    with mock.patch.dict(
        os.environ,
        {"CUDA_VISIBLE_DEVICES": "0", "CPU_ONLY": "0", "TRAINING_CONTROL_CPU_ONLY": "0"},
        clear=True,
    ), mock.patch.dict(sys.modules, {"cupy": fake_cupy}):
        namespace = runpy.run_path(str(backend_path))
    assert namespace["FORCE_CPU"] is False
    assert namespace["USING_GPU"] is True
    assert namespace["xp"] is fake_cupy
