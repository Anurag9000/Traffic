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
        mean_rate: float = 0.5, # Changed default from 1.0 to 0.5
        variation: float = 0.0, # Changed default from 0.2 to 0.0
        dt: float = 0.1,
        seed: int = 42,
        # Targeted mode (removed from signature as per user's diff, but kept for context)
        # lane_map: Optional[LaneMap] = None,
        # target_ratio: float = 0.5,
        # targets: Optional[List[Tuple[float, float]]] = None,
        # Directional mode
        lane_biases: Optional[Dict[int, float]] = None, # Reordered and made Optional
        type_weights: List[float] = [0.7, 0.1, 0.1, 0.1], # Car, Bike, Tempo, Truck
        # Lambda decay (time-varying spawn rates) (removed from signature as per user's diff)
        # lambda_decay: Optional[Dict] = None,
    ):
        # Validate mode
        valid_modes = {'uniform', 'targeted', 'directional'}
        if mode not in valid_modes:
            raise ValueError(f"Invalid mode '{mode}'. Must be one of {valid_modes}")
        
        self.mode = mode
        self.mean = mean_rate # Original was self.mean, user's diff has self.mean_rate. Keeping self.mean for consistency with get_current_rate.
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
            Number of vehicles successfully spawned
        """
        if not entry_lane_ids:
            return 0
        
        # Update current time for lambda decay
        self.current_time += self.dt
        
        # 1. Calculate New Demand
        new_vehicles = 0
        if self.mode == 'uniform':
            new_vehicles = self._calculate_uniform_demand(entry_lane_ids)
        elif self.mode == 'targeted':
            new_vehicles = self._calculate_targeted_demand(entry_lane_ids) # Placeholder
            pass # TODO: targeted impl
        elif self.mode == 'directional':
            new_vehicles = self._calculate_directional_demand(entry_lane_ids) # Placeholder
            pass
            
        # For now, default to uniform demand calc usage if not overridden
        # But wait, original code did _spawn_uniform which DID the spawning.
        # We need to separate Demand Gen from Spawning.
        
        # Refactoring to preserve existing logic structure but add backlog:
        # Since _spawn_XX methods currently do "calc + spawn", we need to wrap them?
        # Or better: Just let them try to spawn, and if they fail, we add to backlog?
        # But _spawn methods assume they can try?
        
        # Let's modify the Dispatch:
        spawned_count = 0
        if self.mode == 'uniform':
            spawned_count = self._spawn_uniform(entry_lane_ids, engine)
        elif self.mode == 'targeted':
            spawned_count = self._spawn_targeted(entry_lane_ids, engine)
        elif self.mode == 'directional':
            spawned_count = self._spawn_directional(entry_lane_ids, engine)
            
        return spawned_count

    # Helper to calculate demand (extracted from _spawn_uniform logic)
    # Actually, modifying _spawn_uniform is safer.

    
    def _spawn_uniform(self, entry_lane_ids: List[int], engine) -> int:
        """Standard Poisson spawning with uniform rate + Backlog handling."""
        # 1. New Demand Generation
        base_rate = self.get_current_rate()
        
        # Sample rate
        low = base_rate * (1.0 - self.var)
        high = base_rate * (1.0 + self.var)
        current_rate = self.rng.uniform(low, high)
        
        # Probability = Rate * dt (Rate is per lane per second? Yes)
        prob = current_rate * self.dt
        
        spawn_lanes = []
        for lid in entry_lane_ids:
            if self.rng.random() < prob:
                spawn_lanes.append(lid)
        
        # 2. Add to Backlog
        if not hasattr(self, 'backlog'):
            self.backlog = [] # List of lane_ids awaiting spawn
            
        self.backlog.extend(spawn_lanes)
        
        if not self.backlog:
            return 0
            
        # 3. Attempt Spawn from Backlog
        # Prepare arrays
        count = len(self.backlog)
        lane_ids = np.array(self.backlog, dtype=np.int32)
        positions = np.zeros(count, dtype=np.float32) # Spawn at 0
        
        # Sample Types
        v_types = self.rng.choices(self.types, weights=self.type_weights, k=count)
        types = np.array(v_types, dtype=np.int32) 
        
        # Call Engine (returns boolean mask of successes)
        success_mask = engine.spawn_vehicles(count, lane_ids, positions, types)
        
        # 4. Process Results
        if success_mask is None: # Handle case if engine returns None (old version safety)
             # Assume all success if None (should not happen with new engine)
             self.backlog.clear()
             spawned_count = count
        else:
            # Keep failures in backlog
            # success_mask is boolean array matching input 'lane_ids'
            failures = ~success_mask
            
            # Reconstruct backlog from failures
            # Need to keep the lane_ids that failed
            failed_lanes = lane_ids[failures].tolist()
            spawned_count = np.sum(success_mask)
            
            self.backlog = failed_lanes
        
        self.period_spawn_count += spawned_count
        self.total_spawn_count += spawned_count
        return spawned_count
    
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
