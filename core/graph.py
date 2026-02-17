from core.gpu import xp as np
import networkx as nx
from typing import Dict, Tuple, Any, List
from core.lanes import LaneMap

class TrafficGraph:
    """
    Adapter class to convert NetworkX/OSMnx graphs into Vectorized LaneMaps.
    """
    def __init__(self):
        self.lane_map: LaneMap = None
        self.edge_to_id: Dict[Tuple[int, int, int], int] = {}
        self.id_to_edge: Dict[int, Tuple[int, int, int]] = {}
        
    def from_networkx(self, G: nx.MultiDiGraph) -> LaneMap:
        """
        Convert a NetworkX graph (nodes, edges with 'length', 'speed') to LaneMap.
        """
        # Count Edges
        num_lanes = len(G.edges)
        
        # Initialize LaneMap
        self.lane_map = LaneMap(num_lanes)
        
        # 1. Map Edges to IDs (Deterministic Ordering)
        # Use iterating over edges with keys
        edges = list(G.edges(keys=True, data=True))
        
        for idx, (u, v, k, data) in enumerate(edges):
            self.edge_to_id[(u, v, k)] = idx
            self.id_to_edge[idx] = (u, v, k)
            
        # 2. Fill Geometry & Connectivity
        for idx, (u, v, k, data) in enumerate(edges):
            # Extract props
            # Default length 100m if missing (grid edges are usually unit length)
            length = float(data.get('length', 100.0))
            if length <= 0.1: length = 100.0 # Safety
            
            speed = float(data.get('speed_limit', 30.0)) # m/s or km/h? typically m/s here
            
            # Find Next Lanes (Connectivity)
            # Next lanes are edges starting from 'v'
            next_edges_ids = []
            
            # Use G[v] to find successors and their keys
            if v in G:
                for target_node in G[v]:
                    for key in G[v][target_node]:
                        # Edge (v, target_node, key)
                        edge_tuple = (v, target_node, key)
                        if edge_tuple in self.edge_to_id:
                            next_edges_ids.append(self.edge_to_id[edge_tuple])
            
            # Extract Coordinates from Target Node v
            # OSMnx graphs have 'x' (lon) and 'y' (lat) in nodes
            tgt_node_data = G.nodes[v]
            tgt_x = float(tgt_node_data.get('x', 0.0))
            tgt_y = float(tgt_node_data.get('y', 0.0))
            
            # Set Lane Data with Endpoint
            self.lane_map.set_lane(idx, length, speed, next_edges_ids, endpoint=(tgt_x, tgt_y))
            
        return self.lane_map
        
    def get_source_lanes(self, G: nx.MultiDiGraph) -> List[int]:
        """
        Returns IDs of lanes where the origin node has no incoming edges in the graph.
        """
        source_ids = []
        for (u, v, k), lid in self.edge_to_id.items():
            # If North node 'u' has 0 in-degree, it's a boundary entry.
            if G.in_degree(u) == 0:
                source_ids.append(lid)
        return source_ids

    def get_lane_id(self, u: int, v: int, k: int = 0) -> int:
        return self.edge_to_id.get((u, v, k), -1)
    
    def get_edge_tuple(self, lane_id: int) -> Tuple[int, int, int]:
        return self.id_to_edge.get(lane_id, None)
