
import numpy as np
import networkx as nx
import random
import sys
import os
from typing import Dict, List, Tuple, Any

# Safe Import for OSMnx
try:
    import osmnx as ox
    HAS_OSMNX = True
except ImportError:
    HAS_OSMNX = False
    print("Warning: OSMnx not found/working. Falling back to NetworkX.")
except Exception:
    HAS_OSMNX = False
    print("Warning: OSMnx error. Falling back to NetworkX.")

# Vector Engine
from core.gpu import xp as np
# DT constant defined locally
DT = 0.1
from core.engine import TrafficEngine
from core.lanes import LaneMap
from core.graph import TrafficGraph
from core.signals import SignalControllerVector, MODE_FIXED, MODE_ADAPTIVE
from core.spawning import Spawner

# Robustly find root dir
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

class RealTrafficNetwork:
    def __init__(self, 
                 graphml_path: str = None, 
                 sim_duration: float = 3600.0, 
                 spawn_rate: float = 1.0, # Unified Default 
                 variation: float = 0.5,  # Unified Default
                 seed: int = 42,
                 map_filter: str = "backbone"):
        
        # Map Loading Logic
        if not graphml_path:
            # Try to find map
            map_dir = os.environ.get('TRAFFIC_REAL_MAP_DIR')
            if not map_dir:
                if os.path.exists('delhi_cp.graphml') or os.path.exists('delhi_full.graphml'):
                    map_dir = '.'
                else:
                    map_dir = os.path.dirname(os.path.abspath(__file__))
            
            if map_filter == "all":
                graphml_path = os.path.join(map_dir, "delhi_full.graphml")
            else:
                graphml_path = os.path.join(map_dir, "delhi_cp.graphml")

        print(f"Loading map: {graphml_path} (Filter: {map_filter})")
        
        try:
             # Load graph
             if os.path.exists(graphml_path):
                 if HAS_OSMNX:
                     self.G = ox.load_graphml(graphml_path)
                 else:
                     self.G = nx.read_graphml(graphml_path)
                     # OSMnx graphs are MultiDiGraph
                     if not isinstance(self.G, nx.MultiDiGraph):
                         self.G = nx.MultiDiGraph(self.G)
                     
                     # Fix node types (NetworkX reads attributes as strings)
                     for n, data in self.G.nodes(data=True):
                         if 'x' in data: data['x'] = float(data['x'])
                         if 'y' in data: data['y'] = float(data['y'])
                         
                     # Fix edge types
                     for u, v, k, data in self.G.edges(keys=True, data=True):
                         if 'length' in data: data['length'] = float(data['length'])
                         if 'speed_limit' in data: 
                             try:
                                 data['speed_limit'] = float(data['speed_limit'])
                             except:
                                 data['speed_limit'] = 30.0 # Default
             else:
                 print(f"Warning: {graphml_path} not found. Creating empty graph.")
                 self.G = nx.MultiDiGraph()
        except Exception as e:
             print(f"Error loading map: {e}")
             self.G = nx.MultiDiGraph()
             
        if not isinstance(self.G, nx.MultiDiGraph):
            self.G = nx.MultiDiGraph(self.G)

        # 1. Adapter: NetworkX -> LaneMap
        self.adapter = TrafficGraph()
        self.lane_map = self.adapter.from_networkx(self.G)
        self.source_lanes = self.adapter.get_source_lanes(self.G)
        
        # 2. Engine & Signals
        nodes = list(self.G.nodes())
        self.node_to_idx = {n: i for i, n in enumerate(nodes)}
        self.num_nodes = len(nodes)
        
        # Signals (Default Actuated/Adaptive for better flow, but compliant)
        self.vector_signals = SignalControllerVector(self.num_nodes, mode=control_mode)
        
        # Map Signals to LaneMap
        for u, v, k in self.G.edges(keys=True):
            lid = self.adapter.get_lane_id(u, v, k)
            if lid != -1:
                v_idx = self.node_to_idx[v]
                # Phase Assignment Heuristic: Random valid phase for compliance demo
                phase = (hash((u,v)) % 4) * 2 + 2 
                self.lane_map.signal_node_idx[lid] = v_idx
                self.lane_map.signal_phase_idx[lid] = phase
        
        self.engine = TrafficEngine(self.lane_map, self.vector_signals, max_vehicles=20000)
        
        # 3. Unified Spawner
        self.spawner = TrafficSpawner(mean_rate=spawn_rate, variation=variation, dt=DT, seed=seed)
        self.all_lane_ids = list(self.adapter.edge_to_id.values())
        
        self.time = 0.0
        self.dt = DT
        self.sim_duration = sim_duration

    def step(self):
        # 1. Spawn (Boundary Sources Only)
        self.spawner.step(self.source_lanes, self.engine)

        # 2. Physics
        self.engine.step()
        self.time += self.dt

    def run_simulation(self):
        steps = int(self.sim_duration / self.dt)
        print(f"Running Vector Simulation for {self.sim_duration}s ({steps} steps)...")
        
        import time
        t0 = time.time()
        for i in range(steps):
             self.step()
             if i % 1000 == 0:
                 active = self.engine.active_count
                 print(f"Step {i}/{steps} | Active Vehicles: {active} | T={self.time:.1f}s")
        
        dur = time.time() - t0
        print(f"Simulation Complete. Real-time: {dur:.2f}s")
