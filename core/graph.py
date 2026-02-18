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
        self.force_uniform_lanes = True # User mandate: 3 lanes everywhere
        
    def from_networkx(self, G: nx.MultiDiGraph) -> LaneMap:
        """
        Convert a NetworkX graph (nodes, edges with 'length', 'speed') to LaneMap.
        """
        # Count Edges
        num_edges = len(G.edges)
        
        if self.force_uniform_lanes:
            # Force 3 Lanes per Edge (Left, Straight, Right)
            num_lanes = num_edges * 3
        else:
            # Future: Parse lanes from OSM
            num_lanes = num_edges # Fallback
            
        # Initialize LaneMap
        self.lane_map = LaneMap(num_lanes)
        
        # 1. Map Edges to IDs (Deterministic Ordering)
        # Use iterating over edges with keys
        edges = list(G.edges(keys=True, data=True))
        
        if self.force_uniform_lanes:
            # 3 Lanes Per Edge Logic
            for idx, (u, v, k, data) in enumerate(edges):
                self.edge_to_id[(u, v, k)] = idx * 3
                self.id_to_edge[idx * 3] = (u, v, k)
                
            for idx, (u, v, k, data) in enumerate(edges):
                base_id = idx * 3
                
                # Extract props
                length = float(data.get('length', 100.0))
                if length <= 0.1: length = 100.0 
                
                speed = float(data.get('speed_limit', 30.0))
                
                # Coords
                src_node_data = G.nodes[u]
                tgt_node_data = G.nodes[v]
                tgt_x = float(tgt_node_data.get('x', 0.0))
                tgt_y = float(tgt_node_data.get('y', 0.0))
                src_x = float(src_node_data.get('x', 0.0))
                src_y = float(src_node_data.get('y', 0.0))
                
                # Geometry Offset
                dx = tgt_x - src_x
                dy = tgt_y - src_y
                norm = np.hypot(dx, dy)
                if norm < 1e-6: norm = 1.0
                ux, uy = dx/norm, dy/norm
                px, py = uy, -ux 
                LANE_WIDTH = 3.5
                offsets = [-LANE_WIDTH, 0, LANE_WIDTH]
                
                # Connectivity
                next_edges_ids = []
                if v in G:
                    for target_node in G[v]:
                        for key in G[v][target_node]:
                            edge_tuple = (v, target_node, key)
                            if edge_tuple in self.edge_to_id:
                                next_base = self.edge_to_id[edge_tuple]
                                next_edges_ids.extend([next_base, next_base+1, next_base+2])
                
                # Create Lanes
                for i in range(3):
                    lid = base_id + i
                    off = offsets[i]
                    ex = tgt_x + px * off
                    ey = tgt_y + py * off
                    self.lane_map.set_lane(lid, length, speed, next_edges_ids, endpoint=(ex, ey))
        else:
            # Legacy/Raw 1-Lane Logic (Fallback for future refactor)
            for idx, (u, v, k, data) in enumerate(edges):
                self.edge_to_id[(u, v, k)] = idx
                self.id_to_edge[idx] = (u, v, k)
                
            for idx, (u, v, k, data) in enumerate(edges):
                length = float(data.get('length', 100.0))
                speed = float(data.get('speed_limit', 30.0))
                
                next_edges_ids = []
                if v in G:
                    for target_node in G[v]:
                        for key in G[v][target_node]:
                            edge_tuple = (v, target_node, key)
                            if edge_tuple in self.edge_to_id:
                                next_edges_ids.append(self.edge_to_id[edge_tuple])
                                
                tgt_node_data = G.nodes[v]
                tgt_x = float(tgt_node_data.get('x', 0.0))
                tgt_y = float(tgt_node_data.get('y', 0.0))
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
