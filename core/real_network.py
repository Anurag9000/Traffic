
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
                 map_filter: str = "backbone",
                 control_mode: int = MODE_ADAPTIVE,  # ADD: control mode parameter
                 enforce_speed_limit: bool = False,  # NEW: Enforce road speed limits
                 enforce_lanes: bool = False,        # NEW: Enforce lane counts
                 enforce_oneway: bool = False):      # NEW: Enforce one-way restrictions
        
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
        
        # Map Signals to LaneMap - Handle 3 Lanes per Edge
        for u, v, k in self.G.edges(keys=True):
            base_lid = self.adapter.get_lane_id(u, v, k)
            if base_lid != -1:
                v_idx = self.node_to_idx[v]
                # Phase Assignment Heuristic: Random valid phase for compliance demo
                phase = (hash((u,v)) % 4) * 2 + 2 
                
                # Apply Phase
                if self.adapter.force_uniform_lanes:
                    # Apply to all 3 lanes (Left, Straight, Right)
                    for i in range(3):
                        self.lane_map.signal_node_idx[base_lid + i] = v_idx
                        self.lane_map.signal_phase_idx[base_lid + i] = phase
                else:
                    # Legacy 1-Lane
                    self.lane_map.signal_node_idx[base_lid] = v_idx
                    self.lane_map.signal_phase_idx[base_lid] = phase
        
        self.engine = TrafficEngine(self.lane_map, self.vector_signals, max_vehicles=20000)
        
        # 4. Map Enforcement Features
        if enforce_speed_limit or enforce_lanes or enforce_oneway:
            print(f"Applying map enforcement: speed_limit={enforce_speed_limit}, lanes={enforce_lanes}, oneway={enforce_oneway}")
            self._apply_map_enforcement(enforce_speed_limit, enforce_lanes, enforce_oneway)
        
        # 5. Unified Spawner
        self.spawner = Spawner(mean_rate=spawn_rate, variation=variation, dt=DT, seed=seed)
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

    def _apply_map_enforcement(self, enforce_speed: bool, enforce_lanes: bool, enforce_oneway: bool):
        """Apply map enforcement features to the engine."""
        
        # Speed Limit Enforcement
        if enforce_speed:
            print("  Enforcing speed limits from OSM data...")
            for u, v, k, data in self.G.edges(keys=True, data=True):
                lid = self.adapter.get_lane_id(u, v, k)
                if lid != -1:
                    speed_limit = data.get('speed_limit', data.get('maxspeed', 30.0))
                    # Convert km/h to m/s if needed
                    if isinstance(speed_limit, str):
                        try:
                            speed_limit = float(speed_limit.replace(' km/h', '').replace(' mph', ''))
                        except:
                            speed_limit = 30.0
                    
                    # Assume km/h, convert to m/s
                    speed_limit_ms = speed_limit / 3.6 if speed_limit > 10 else speed_limit
                    
                    # Apply to all vehicles on this lane (future vehicles will inherit)
                    # For now, store in lane_map for future use
                    # TODO: Add lane-specific speed limits to engine
                    lane_map_id = self.node_to_idx.get(u) # Wait, need lane ID not node
                    # lid is already retrieved above: lid = self.adapter.get_lane_id(u, v, k)
                    
                    if speed_limit_ms > 0:
                        if self.adapter.force_uniform_lanes:
                            # Apply to all 3 lanes
                            for i in range(3):
                                 self.lane_map.speed_limits[lid + i] = speed_limit_ms
                        else:
                            self.lane_map.speed_limits[lid] = speed_limit_ms
        
                    # For now, this is a placeholder for future implementation
                    pass
        
        # One-Way Enforcement
        if enforce_oneway:
            print("  Enforcing one-way restrictions from OSM data...")
            # Remove reverse edges for one-way streets
            edges_to_remove = []
            for u, v, k, data in self.G.edges(keys=True, data=True):
                oneway = data.get('oneway', False)
                if isinstance(oneway, str):
                    oneway = oneway.lower() in ['yes', 'true', '1']
                
                if oneway:
                    # Check if reverse edge exists and remove it
                    if self.G.has_edge(v, u):
                        for key in list(self.G[v][u].keys()):
                            edges_to_remove.append((v, u, key))
            
            # Remove reverse edges
            for u, v, k in edges_to_remove:
                lid = self.adapter.get_lane_id(u, v, k)
                if lid != -1:
                    # Mark lane as removed (set adjacency to empty)
                    self.lane_map.adjacency[lid, :] = -1
            
            if edges_to_remove:
                print(f"    Removed {len(edges_to_remove)} reverse edges for one-way streets")

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
