
import random
import numpy as np
from typing import Dict, List, Tuple, Optional
# DT constant defined locally
DT = 0.1

# Vector Engine
from core.engine import TrafficEngine
from core.lanes import LaneMap
from core.signals import SignalControllerVector, MODE_FIXED, MODE_ADAPTIVE
from core.spawning import Spawner

class TrafficIntersection:
    def __init__(
        self,
        spawn_rate: float = 1.0,
        variation: float = 0.5,
        seed: int = 42,
        lane_length: float = 400.0,
        control_mode: int = MODE_ADAPTIVE,
        lane_biases: Optional[Dict[int, float]] = None
    ):
        self.lane_length = lane_length
        self.dt = DT
        
        # 1. Setup Vector Engine
        self.num_lanes = 12
        self.lane_map = LaneMap(self.num_lanes)
        
        # Configure Lanes (4 Approaches x 3 Lanes)
        # 0,1,2: South App
        # 3,4,5: West App
        # 6,7,8: North App
        # 9,10,11: East App
        
        # Phases: 2,6 (Str), 4,8 (Str)
        # 1,5 (Left?), 3,7 (Left?) - Wait LHT: 
        # LHT Turns: Left is Free/Filter? Right is signalized.
        # Let's map strict IRC phases.
        
        for app in range(4):
            for l_idx in range(3):
                lid = app * 3 + l_idx
                
                # Signal Phase Mapping (Same as Grid)
                # (0, straight) -> 2 ?? No L_idx 1 is straight usually.
                # Let's standard: 0=Left, 1=Straight, 2=Right
                
                # South App (0):
                # 0 (Left -> West) -> Free (Phase 0)
                # 1 (Straight -> North) -> Phase 2
                # 2 (Right -> East) -> Phase 1
                
                phase = 0
                if l_idx == 1: # Straight
                    if app == 0: phase = 2    # NB Straight
                    elif app == 1: phase = 4  # EB Straight
                    elif app == 2: phase = 6  # SB Straight
                    elif app == 3: phase = 8  # WB Straight
                elif l_idx == 2: # Right
                    if app == 0: phase = 1    # NB Right
                    elif app == 1: phase = 3  # EB Right
                    elif app == 2: phase = 5  # SB Right
                    elif app == 3: phase = 7  # WB Right
                
                # Next Lanes: Empty (Sink)
                self.lane_map.set_lane(lid, self.lane_length, 13.8, [], 0, phase)
        
        # Signals
        self.vector_signals = SignalControllerVector(1, mode=control_mode) 
        
        # Engine
        self.engine = TrafficEngine(self.lane_map, self.vector_signals, max_vehicles=5000)
        
        # Spawner
        if lane_biases:
            self.spawner = Spawner(mode='directional', mean_rate=spawn_rate, variation=variation, dt=self.dt, seed=seed, lane_biases=lane_biases)
        else:
            self.spawner = Spawner(mode='uniform', mean_rate=spawn_rate, variation=variation, dt=self.dt, seed=seed)
            
        self.valid_lanes = list(range(12))

    def step(self):
        # In a single intersection, all 12 lanes are boundary entries
        self.spawner.step(self.valid_lanes, self.engine)
        self.engine.step()

    def run(self, steps=1000):
        for _ in range(steps):
            self.step()
