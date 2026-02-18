
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
        self.num_lanes = 24 # 12 Inbound, 12 Outbound
        self.lane_map = LaneMap(self.num_lanes)
        
        # Outbound Lanes (12-23)
        # Just sinks. Length 400m.
        for lid in range(12, 24):
            self.lane_map.set_lane(lid, self.lane_length, 13.8, [], 0, 0)
            
        # Inbound Lanes (0-11)
        # 4 Approaches x 3 Lanes
        # Map: South=0, East=1, North=2, West=3
        # Lanes: 0=Left, 1=Straight, 2=Right
        
        # Outbound mapping (Target App x Lanes)
        # S_Out = 12-14
        # E_Out = 15-17
        # N_Out = 18-20
        # W_Out = 21-23
        
        out_base = [12, 15, 18, 21] 
        
        for app in range(4): # 0=S, 1=E, 2=N, 3=W
            for l_idx in range(3): # 0=L, 1=S, 2=R
                lid = app * 3 + l_idx
                
                # Signal Phase
                phase = 0
                if l_idx == 1: # Straight
                # Connection to "-1" is Sink.
                # The issue was existing code set `next_lanes=[]` which implies Sink.
                # So vehicles vanish. This IS correct for a single intersection test.
                # But the user called it a "Trap".
                # If the goal is to test flow, vanishing at the end is fine.
                # EXCEPT: The "Spillback" logic in engine requires `next_lane >= 0` to check occupancy.
                # If next_lane is None, vehicle just exits.
                # This means we NEVER test spillback in `TrafficIntersection`.
                # To test Spillback, we need a bottleneck.
                # FIX: Create short "Exit Lanes" (12, 13, 14, 15...) and make them narrow/slow?
                # Or just acknowledge that for `TrafficIntersection` (Unit Test), Sink is O.K.
                
                # However, user said "Fix 2".
                # "Fix 2: The Straight-Only Trap" - "Vehicles spawn, travel to end, and vanish".
                # "Fails to simulate network behavior".
                # I will add a 400m "Exit Lane" for each approach to capture the outflow.
                # This allows us to measure "Completed Trips" properly?
                # `TrafficEngine` counts completed trips when they exit.
                # So "Vanishing" IS "Completed Trip".
                
                # Maybe the "Trap" was that they couldn't turn? 
                # "Logic says next_lanes=[]".
                # Engine 'boundary' logic: If next_lanes is empty, remove vehicle.
                # So turning logic (Signal Phase) is applied, but vehicle just goes straight geometry-wise?
                # No, `engine` doesn't move lateral.
                # If I am in Lane 0 (Left Turn Lane) and I reach end:
                # If I have no next_lanes, I vanish. I "Completed Left Turn".
                # If I am in Lane 1 (Straight), I vanish.
                # It seems behaviorally correct for a single node.
                
                # Wait, the audit finding said: 
                # "Vehicles never cross the intersection or turn."
                # They just disappear AT THE STOP LINE (End of lane).
                # Ah! `lane_length` is the *Incoming* lane.
                # If they disappear at the Stop Line, they don't cross the box.
                # Visually, they vanish before the intersection.
                # That IS a "Trap". They should cross the intersection and vanish *after*.
                
                # FIX: Add "Exit Lanes" (Outbound).
                # Total Lanes = 12 (In) + 12 (Out).
                # Connect In -> Out based on turn logic.
                
                # Expand LaneMap to 24 lanes.
                # S: 0,1,2 (In) -> N: 13 (Str), E: 22 (Left?), W: ...
                
                # Let's simple: Each App has 3 In, 3 Out.
                # App 0 (South): In=0-2, Out=12-14.
                # App 1 (East): In=3-5, Out=15-17.
                # App 2 (North): In=6-8, Out=18-20.
                # App 3 (West): In=9-11, Out=21-23.
                
                # Connections:
                # S-Left (0) -> W-Out-2 (23)? (Standard lane mapping)
                # S-Str (1) -> N-Out-1 (19)
                # S-Right (2) -> E-Out-0 (15)
                
                # Map needs 24 lanes.
                pass 
                
        # Update self.num_lanes and LaneMap init (in __init__)
        self.num_lanes = 24 
        self.lane_map = LaneMap(self.num_lanes)
        
        # ... logic to setup Inbound (0-11) ...
        # ... logic to setup Outbound (12-23) ...
        # ... Connect In -> Out ...
        self.lane_map.set_lane(lid, self.lane_length, 13.8, [next_lane], 0, phase)
        
        # I need to rewrite the loop completely.
        pass
 
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
