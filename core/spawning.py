"""
Unified Vehicle Spawning Module

Consolidates all spawning strategies into a single Spawner class.
Replaces: spawner.py, spawner_targeted.py, spawner_directional.py
"""

from core.gpu import xp as np
import random
import sys
from typing import List, Tuple, Dict, Optional
from core.lanes import LaneMap


class Spawner:
    """
    Unified vehicle spawner supporting multiple spawning strategies.
    
    Modes:
        - 'uniform': Standard Poisson spawning (default)
        - 'targeted': Spawn vehicles with destination targets
        - 'directional': Apply per-lane rate multipliers (rush hour simulation)
    
    Args:
        mode: Spawning strategy ('uniform', 'targeted', 'directional')
        mean_rate: Base spawn rate (vehicles per lane per second)
        variation: Rate variation (±20% default)
        dt: Simulation timestep (seconds)
        seed: Random seed for reproducibility
        
        # Targeted mode parameters
        lane_map: LaneMap for targeted spawning
        target_ratio: Fraction of vehicles with targets (0.0-1.0)
        targets: List of (x, y) target coordinates
        
        # Directional mode parameters
        lane_biases: Dict mapping lane_id -> rate multiplier
    """
    
    def __init__(
        self,
        mode: str = 'uniform',
        mean_rate: float = 1.0,
        variation: float = 0.2,
        dt: float = 0.1,
        seed: int = 42,
        # Targeted mode
        lane_map: Optional[LaneMap] = None,
        target_ratio: float = 0.5,
        targets: Optional[List[Tuple[float, float]]] = None,
        # Directional mode
        lane_biases: Optional[Dict[int, float]] = None,
        # Lambda decay (time-varying spawn rates)
        lambda_decay: Optional[Dict] = None,
    ):
        # Validate mode
        valid_modes = {'uniform', 'targeted', 'directional'}
        if mode not in valid_modes:
            raise ValueError(f"Invalid mode '{mode}'. Must be one of {valid_modes}")
        
        self.mode = mode
        self.mean = mean_rate
        self.var = variation
        self.dt = dt
        
        # Random number generators
        self.rng = random.Random(seed)
        self.np_rng = np.random.default_rng(seed)
        
        # Vehicle types & weights
        # 0: Car, 1: Bike, 2: Truck/Bus
        self.types = [0, 1, 2]
        # Equal spawn probability for all vehicle types (no priority)
        self.weights = [0.333, 0.333, 0.334]
        
        # Mode-specific parameters
        if mode == 'targeted':
            if lane_map is None:
                raise ValueError("lane_map required for targeted mode")
            self.lane_map = lane_map
            self.target_ratio = target_ratio
            self.targets = targets if targets else []
        
        if mode == 'directional':
            self.lane_biases = lane_biases if lane_biases is not None else {}
        
        # Lambda decay configuration
        self.lambda_decay = lambda_decay
        self.current_time = 0.0
        if lambda_decay:
            self.decay_type = lambda_decay.get('type', 'exponential')
            self.decay_rate = lambda_decay.get('decay_rate', 0.001)
            self.profile = lambda_decay.get('profile', [])
            # Sort profile by time
            if self.profile:
                self.profile = sorted(self.profile, key=lambda x: x[0])
    
    def get_current_rate(self) -> float:
        """
        Calculate current spawn rate based on lambda decay configuration.
        
        Returns:
            Current spawn rate (vehicles/lane/second)
        """
        if not self.lambda_decay:
            return self.mean
        
        if self.decay_type == 'exponential':
            # Exponential decay: rate(t) = mean * exp(-decay_rate * t)
            import math
            return self.mean * math.exp(-self.decay_rate * self.current_time)
        
        elif self.decay_type == 'linear':
            # Linear decay: rate(t) = mean - decay_rate * t
            rate = self.mean - self.decay_rate * self.current_time
            return max(0.0, rate)  # Don't go negative
        
        elif self.decay_type == 'profile':
            # Profile-based: interpolate between time points
            if not self.profile:
                return self.mean
            
            # Find surrounding time points
            if self.current_time <= self.profile[0][0]:
                return self.profile[0][1]
            if self.current_time >= self.profile[-1][0]:
                return self.profile[-1][1]
            
            # Linear interpolation
            for i in range(len(self.profile) - 1):
                t1, r1 = self.profile[i]
                t2, r2 = self.profile[i + 1]
                if t1 <= self.current_time <= t2:
                    # Interpolate
                    alpha = (self.current_time - t1) / (t2 - t1)
                    return r1 + alpha * (r2 - r1)
            
            return self.mean
        
        return self.mean
    
    def step(self, entry_lane_ids: List[int], engine) -> int:
        """
        Spawn vehicles for this timestep.
        
        Args:
            entry_lane_ids: List of lane IDs where vehicles can spawn
            engine: TrafficEngine instance
        
        Returns:
            Number of vehicles spawned
        """
        if not entry_lane_ids:
            return 0
        
        # Update current time for lambda decay
        self.current_time += self.dt
        
        # Dispatch to appropriate spawning strategy
        if self.mode == 'uniform':
            return self._spawn_uniform(entry_lane_ids, engine)
        elif self.mode == 'targeted':
            return self._spawn_targeted(entry_lane_ids, engine)
        elif self.mode == 'directional':
            return self._spawn_directional(entry_lane_ids, engine)
    
    def _spawn_uniform(self, entry_lane_ids: List[int], engine) -> int:
        """Standard Poisson spawning with uniform rate (supports lambda decay)."""
        # Get current rate (may vary with time if lambda decay is enabled)
        base_rate = self.get_current_rate()
        
        # Sample rate for this step with ±variation
        low = base_rate * (1.0 - self.var)
        high = base_rate * (1.0 + self.var)
        current_rate = self.rng.uniform(low, high)
        
        # Probability = Rate * dt
        prob = current_rate * self.dt
        
        # Determine which lanes spawn vehicles
        spawn_lanes = []
        for lid in entry_lane_ids:
            if self.rng.random() < prob:
                spawn_lanes.append(lid)
        
        count = len(spawn_lanes)
        if count == 0:
            return 0
        
        # Create spawn data
        pos = np.zeros(count, dtype=np.float32)
        v_types = self.rng.choices(self.types, weights=self.weights, k=count)
        
        # Spawn vehicles
        try:
            engine.spawn_vehicles(
                count=count,
                lane_ids=np.array(spawn_lanes, dtype=np.int32),
                positions=pos,
                types=np.array(v_types, dtype=np.int32)
            )
            return count
        except Exception as e:
            print(f"WARNING: Spawn failed: {e}", file=sys.stderr)
            return 0
    
    def _spawn_targeted(self, entry_lane_ids: List[int], engine) -> int:
        """Spawn vehicles with destination targets."""
        # Sample rate for this step
        low = self.mean * (1.0 - self.var)
        high = self.mean * (1.0 + self.var)
        current_rate = self.rng.uniform(low, high)
        
        prob = current_rate * self.dt
        
        # Determine spawns and assign targets
        spawn_lanes = []
        target_coords = []
        
        for lid in entry_lane_ids:
            if self.rng.random() < prob:
                spawn_lanes.append(lid)
                
                # Assign target?
                if self.targets and self.rng.random() < self.target_ratio:
                    tgt = self.rng.choice(self.targets)
                    target_coords.append(tgt)
                else:
                    target_coords.append((-1.0, -1.0))  # No target
        
        count = len(spawn_lanes)
        if count == 0:
            return 0
        
        # Create spawn data
        pos = np.zeros(count, dtype=np.float32)
        v_types = self.rng.choices(self.types, weights=self.weights, k=count)
        t_arr = np.array(target_coords, dtype=np.float32)
        
        # Spawn vehicles with targets
        try:
            engine.spawn_vehicles(
                count=count,
                lane_ids=np.array(spawn_lanes, dtype=np.int32),
                positions=pos,
                types=np.array(v_types, dtype=np.int32),
                targets=t_arr
            )
            return count
        except Exception as e:
            print(f"WARNING: Targeted spawn failed: {e}", file=sys.stderr)
            return 0
    
    def _spawn_directional(self, entry_lane_ids: List[int], engine) -> int:
        """Spawn with per-lane rate multipliers (rush hour simulation)."""
        # Sample base rate for this step
        low = self.mean * (1.0 - self.var)
        high = self.mean * (1.0 + self.var)
        base_rate = self.rng.uniform(low, high)
        
        # Apply lane-specific biases
        spawn_lanes = []
        for lid in entry_lane_ids:
            # Get bias multiplier for this lane (default 1.0)
            multiplier = self.lane_biases.get(lid, 1.0)
            lane_rate = base_rate * multiplier
            
            prob = lane_rate * self.dt
            if self.rng.random() < prob:
                spawn_lanes.append(lid)
        
        count = len(spawn_lanes)
        if count == 0:
            return 0
        
        # Create spawn data
        pos = np.zeros(count, dtype=np.float32)
        v_types = self.rng.choices(self.types, weights=self.weights, k=count)
        
        # Spawn vehicles
        try:
            engine.spawn_vehicles(
                count=count,
                lane_ids=np.array(spawn_lanes, dtype=np.int32),
                positions=pos,
                types=np.array(v_types, dtype=np.int32)
            )
            return count
        except Exception as e:
            print(f"WARNING: Directional spawn failed: {e}", file=sys.stderr)
            return 0


# Backward compatibility aliases
TrafficSpawner = Spawner
TargetedSpawner = lambda **kwargs: Spawner(mode='targeted', **kwargs)
DirectionalSpawner = lambda **kwargs: Spawner(mode='directional', **kwargs)
