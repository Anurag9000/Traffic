
from core.gpu import xp as np
from typing import List, Tuple, Dict, Optional

class LaneMap:
    def __init__(self, num_lanes: int, max_connections: int = 4):
        self.num_lanes = num_lanes
        self.max_connections = max_connections
        
        # 1. Geometry (Float32) - Index = Lane ID
        self.lengths = np.zeros(num_lanes, dtype=np.float32)
        self.speed_limits = np.zeros(num_lanes, dtype=np.float32)
        
        # 2. Connectivity (Int32)
        #    adjacency[i] = [next_lane_1, next_lane_2, -1]
        #    We use -1 for "No Connection" / Dead End
        self.adjacency = np.full((num_lanes, max_connections), -1, dtype=np.int32)
        
        # 3. Turn Probabilities (Float32) - For stochastic routing if needed
        #    probs[i] = [0.2, 0.8, 0.0]
        self.turn_probs = np.zeros((num_lanes, max_connections), dtype=np.float32)
        
        # 4. Signal Info
        #    Lane ID maps to Signal Node ID & Signal Phase
        self.signal_node_idx = np.zeros(num_lanes, dtype=np.int32) # Which intersection?
        self.signal_phase_idx = np.zeros(num_lanes, dtype=np.int32) # Which phase controls? 0=None
        
        # 5. Geometry Endpoints (For Manhattan Routing)
        #    Stores (x, y) of the node this lane leads to.
        self.lane_endpoints = np.zeros((num_lanes, 2), dtype=np.float32)
    
    def set_lane(self, lane_id: int, length: float, speed_limit: float, 
                 next_lanes: Optional[List[int]] = None, 
                 signal_node: int = 0, signal_phase: int = 0,
                 endpoint: Tuple[float, float] = (0.0, 0.0)):
                 
        if lane_id >= self.num_lanes:
            raise IndexError(f"Lane ID {lane_id} out of bounds (max {self.num_lanes})")
            
        self.lengths[lane_id] = length
        self.speed_limits[lane_id] = speed_limit
        self.signal_node_idx[lane_id] = signal_node
        self.signal_phase_idx[lane_id] = signal_phase
        # FIX: Element-wise assignment for CuPy compatibility (CuPy doesn't accept tuples/lists)
        self.lane_endpoints[lane_id, 0] = endpoint[0]
        self.lane_endpoints[lane_id, 1] = endpoint[1]
        
        if next_lanes:
            # FIX: Convert list to array for CuPy compatibility
            next_lanes_arr = np.array(next_lanes, dtype=np.int32) if isinstance(next_lanes, list) else next_lanes
            # Fill adjacency, pad/truncate to max_connections
            n = min(len(next_lanes), self.max_connections)
            self.adjacency[lane_id, :n] = next_lanes_arr[:n]
            # Simple equal probability for now if choice exists
            if n > 0:
                self.turn_probs[lane_id, :n] = 1.0 / n
                
    def get_lane_lengths(self, lane_ids: np.ndarray) -> np.ndarray:
        """Vector lookup: Get lengths for a batch of lane IDs."""
        return self.lengths[lane_ids]
    
    def get_next_lanes(self, lane_ids: np.ndarray) -> np.ndarray:
        """Vector lookup: Get adjacency matrix rows for a batch."""
        return self.adjacency[lane_ids]
