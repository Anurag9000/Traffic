"""
Traffic Simulator Core Module

Clean, modular traffic simulation with GPU acceleration and NEMA signal control.
"""

# GPU and Physics
from core.gpu import xp, USING_GPU, to_numpy, to_gpu, synchronize, get_device_info
from core.physics import calculate_idm_vectorized, update_kinematics

# Core Components
from core.engine import TrafficEngine
from core.signals import SignalControllerVector, MODE_FIXED, MODE_ADAPTIVE, RED, GREEN
from core.spawning import Spawner
from core.stats import VectorStatsRecorder

# Geometry
from core.lanes import LaneMap
from core.grid_adapter import GridAdapter
from core.graph import TrafficGraph

# Networks
from core.grid_network import TrafficGridNetwork
from core.intersection import SingleIntersection
from core.real_network import RealTrafficNetwork

__version__ = '2.0.0'
__all__ = [
    # GPU
    'xp', 'USING_GPU', 'to_numpy', 'to_gpu', 'synchronize', 'get_device_info',
    # Physics
    'calculate_idm_vectorized', 'update_kinematics',
    # Core
    'TrafficEngine', 'SignalControllerVector', 'Spawner', 'VectorStatsRecorder',
    # Modes
    'MODE_FIXED', 'MODE_ADAPTIVE', 'RED', 'GREEN',
    # Geometry
    'LaneMap', 'GridAdapter', 'TrafficGraph',
    # Networks
    'TrafficGridNetwork', 'SingleIntersection', 'RealTrafficNetwork',
]
