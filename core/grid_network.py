"""Traffic grid simulator with Vector Physics Engine."""

from __future__ import annotations

import math
import random
import numpy as np
from typing import Callable, Dict, List, Optional, Tuple, Iterable, Sequence, Any

# Constants
DT = 0.1  # Timestep

# Vector Engine Imports
from core.engine import TrafficEngine, IDX_ID, IDX_X, IDX_Y
from core.lanes import LaneMap
from core.signals import SignalControllerVector
from core.grid_adapter import GridAdapter
from core.spawning import Spawner

class TrafficGridNetwork:
    def __init__(
        self,
        grid_size: int = 10,  # Changed from 'size' to 'grid_size'
        spawn_rate: float = 1.0, # Unified Default
        variation: float = 0.5,  # Unified Default
        stats_interval: float = 60.0,
        subgrid_sizes: Iterable[int] = (4, 5),
        subgrid_regions: Iterable[Tuple[int, int, int, int]] = (),
        seed: int = 42,
        lane_length: float = 100.0,
        control_mode: str = 'fixed',
    ):
        self.size = grid_size  # Store as 'size' internally
        self.lane_length = float(lane_length)
        
        # 1. Setup Vector Engine Components
        # Adapter
        self.adapter = GridAdapter(grid_size, self.lane_length)
        self.lane_map = self.adapter.generate()
        self.boundary_lanes = self.adapter.get_boundary_lanes()
        
        # Signals (One controller for all N*N nodes)
        mode = 1 if control_mode == 'adaptive' else 0  # MODE_ADAPTIVE=1, MODE_FIXED=0
        self.vector_signals = SignalControllerVector(grid_size * grid_size, mode=mode)
        
        # Engine
        self.engine = TrafficEngine(self.lane_map, self.vector_signals, max_vehicles=20000)
        
        # Unified Spawner
        self.spawner = Spawner(mean_rate=spawn_rate, variation=variation, dt=DT, seed=seed)
        
        # Valid Spawn Lanes (Outer Edges? Or Everywhere?)
        # Grid usually spawns everywhere or on boundary.
        # Let's spawn on ALL lanes for "Grid" traffic unless specified.
        # Actually, "GridNetwork" implies traffic generation on edges?
        # Original code spawned everywhere? 
        # Let's use all valid lanes 0..NumLanes-1
        self.valid_spawn_lanes = list(range(self.lane_map.num_lanes))
        
        # Props
        self.time = 0.0
        self.dt = DT

    def step(self):
        # 1. Unified Spawning (Boundary Only)
        self.spawner.step(self.boundary_lanes, self.engine)
        
        # 2. Physics
        self.engine.step()
        self.time += self.dt
