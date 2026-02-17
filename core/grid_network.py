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
        subgrid_regions: Optional[List[Dict]] = None,  # NEW: Subgrid configuration
        seed: int = 42,
        lane_length: float = 100.0,
        control_mode: str = 'fixed',
    ):
        """
        Initialize Traffic Grid Network with optional subgrid support.
        
        Args:
            grid_size: Grid dimensions (NxN)
            spawn_rate: Base spawn rate (vehicles/lane/second)
            variation: Spawn rate variation
            stats_interval: Statistics recording interval
            subgrid_sizes: Legacy parameter (unused)
            subgrid_regions: List of subgrid configurations, each with:
                {
                    'bounds': (x1, y1, x2, y2),  # Grid coordinates
                    'control_mode': 'fixed' or 'adaptive',
                    'cycle_time': 90.0,  # For fixed mode
                    'min_green': 15.0,   # For adaptive mode
                    'max_green': 60.0    # For adaptive mode
                }
            seed: Random seed
            lane_length: Length of each lane segment (meters)
            control_mode: Default control mode for all intersections
        """
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
        
        # Apply subgrid regions if specified
        if subgrid_regions:
            self._apply_subgrid_regions(subgrid_regions, grid_size)
        
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
    
    def _apply_subgrid_regions(self, subgrid_regions: List[Dict], grid_size: int):
        """
        Apply different signal configurations to different grid regions.
        
        Args:
            subgrid_regions: List of region configurations
            grid_size: Grid dimensions
        """
        for region in subgrid_regions:
            bounds = region.get('bounds')
            if not bounds or len(bounds) != 4:
                continue
            
            x1, y1, x2, y2 = bounds
            region_mode = region.get('control_mode', 'fixed')
            cycle_time = region.get('cycle_time', 120.0)
            min_green = region.get('min_green', 10.0)
            max_green = region.get('max_green', 60.0)
            
            # Map region mode to signal mode
            mode = 1 if region_mode == 'adaptive' else 0
            
            # Apply to all intersections in the region
            for x in range(max(0, x1), min(grid_size, x2)):
                for y in range(max(0, y1), min(grid_size, y2)):
                    node_id = y * grid_size + x
                    
                    if node_id < self.vector_signals.num_nodes:
                        # Update signal parameters for this node
                        if mode == 0:  # Fixed mode
                            # Adjust cycle time by scaling phase durations
                            scale = cycle_time / self.vector_signals.cycle_time
                            for phase in range(1, 9):
                                self.vector_signals.phase_durations[node_id, phase] *= scale
                        else:  # Adaptive mode
                            # Update min/max green times
                            self.vector_signals.min_green = min_green
                            self.vector_signals.max_green = max_green

