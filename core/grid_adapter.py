from core.gpu import xp as np
from typing import Dict, Tuple, List, Optional
from core.lanes import LaneMap

# Directions
NORTH = 0
EAST = 1
SOUTH = 2
WEST = 3

# Lane Indices
LEFT = 0
STRAIGHT = 1
RIGHT = 2

class GridAdapter:
    """
    Generates a LaneMap for an N x N grid.
    Maps (row, col, approach) -> Lane ID.
    """
    def __init__(self, size: int, lane_length: float = 100.0, speed_limit: float = 13.8):
        self.size = size
        self.lane_length = lane_length
        self.speed_limit = speed_limit
        
        # Mapping
        # Keys: (row, col, approach) -> Lane ID (Assuming single lane per approach for Vector MVP? 
        # GridNetwork has 3 lanes per approach (L, S, R). 
        # To match EXACTLY, we need 3 lanes per approach per intersection.
        # But wait, in Vector engine, lanes are Links.
        # In GridNetwork, 'lanes' are queues AT the intersection.
        # The 'Link' is the space between intersections.
        
        # Let's model Links.
        # Link (r, c, approach) means "The road segment ARRIVING at (r, c) from direction 'approach'".
        # E.g. Approach 0 (North) means arriving FROM North, going South.
        # So it originates at (r-1, c)? No, App 0 vectors (1, 0) -> South.
        # In GridNetwork:
        # App 0: North side of intersection. Cars moving South (vector 1, 0).
        # App 1: East side. Cars moving West (vector 0, -1).
        
        # So we have 4 Approaches * Size * Size * 3 Lanes/App?
        # 12 * Size^2 IDs?
        self.num_lanes = size * size * 4 * 3
        self.lane_map = LaneMap(self.num_lanes)
        
        # Map: (r, c, approach, lane_idx) -> ID
        self.grid_to_id: Dict[Tuple[int, int, int, int], int] = {}
        self.id_to_grid: Dict[int, Tuple[int, int, int, int]] = {}
        
    def get_boundary_lanes(self) -> List[int]:
        """
        Returns IDs of lanes that enter the grid from the outside.
        Criteria: (r, c, app) such that there is no neighbor at (r-dr, c-dc).
        """
        boundary_ids = []
        for lid in range(self.num_lanes):
            r, c, app, l_idx = self.id_to_grid[lid]
            
            # Origin vector (where does the car come FROM?)
            # App 0 arrived from North (r-1, c)
            dr, dc = 0, 0
            if app == 0: dr = -1
            elif app == 1: dc = 1
            elif app == 2: dr = 1
            elif app == 3: dc = -1
            
            prev_r = r + dr
            prev_c = c + dc
            
            # If previous step was outside the grid, this is a boundary entry lane.
            if prev_r < 0 or prev_r >= self.size or prev_c < 0 or prev_c >= self.size:
                boundary_ids.append(lid)
                
        return boundary_ids

    def generate(self) -> LaneMap:
        cnt = 0
        
        # 1. Assign IDs
        for r in range(self.size):
            for c in range(self.size):
                for app in range(4):
                    for l_idx in range(3): # L, S, R
                        self.grid_to_id[(r, c, app, l_idx)] = cnt
                        self.id_to_grid[cnt] = (r, c, app, l_idx)
                        cnt += 1
                        
        # 2. Build Connections and Geometry
        for lid in range(self.num_lanes):
            r, c, app, l_idx = self.id_to_grid[lid]
            
            # Geometry
            # Signal Info: This lane ENDS at intersection (r, c).
            # So Signal Node = (r * size + c).
            # Signal Phase? Depends on Approach.
            # App 0 (North) -> Ph 2 (Straight), Ph 1 (Right).
            # 0=Left(Free), 1=Straight, 2=Right
            
            phase = 0
            # From GridNetwork.PHASE_MAPPING
            # (0, "straight") -> 2, etc.
            turn_str = ["left", "straight", "right"][l_idx]
            
            # Simple manual map
            pmap = {
                (0, 1): 2, (0, 2): 1, # App 0 S/R
                (1, 1): 4, (1, 2): 3, # App 1 S/R
                (2, 1): 6, (2, 2): 5, # App 2 S/R
                (3, 1): 8, (3, 2): 7  # App 3 S/R
            }
            phase = pmap.get((app, l_idx), 0) # 0 for Left/Free
            
            signal_node = r * self.size + c
            
            # Connectivity (Where does it go?)
            # Cars traverse this lane (Link) and arrive at (r, c).
            # Then they Turn. 
            # After Turn, they enter a NEW Lane (Link) starting at (r,c) going to Neighbor.
            
            # destination (r', c') depends on Turn and Approach.
            # GridNetwork vectors:
            # 0 (N->S): (1, 0). Left -> (0, 1) [East]. Right -> (0, -1) [West].
            
            # Get exit vector
            # We need to find the 'Entering Approach' at the NEXT intersection.
            # If I go South from (r,c) to (r+1, c).
            # At (r+1, c), I am arriving from North (App 0).
            # ALL turns from App 0 map to *some* approach at *some* neighbor.
            
            next_lanes = []
            
            # Calculate Next Cell
            # Current Vector
            vec = (0, 0)
            if app == 0: vec = (1, 0)   # S
            elif app == 1: vec = (0, -1) # W
            elif app == 2: vec = (-1, 0) # N
            elif app == 3: vec = (0, 1)  # E
            
            # Apply Turn to Vector
            next_vec = vec # Straight
            if l_idx == 0: # Left
                # Rotate Left logic from grid_network
                # 0(1,0) -> L(0,1)
                # 1(0,-1) -> L(1,0)
                # 2(-1,0) -> L(0,-1)
                # 3(0,1) -> L(-1,0)
                dr, dc = vec
                next_vec = (-dc, dr)
            elif l_idx == 2: # Right
                dr, dc = vec
                next_vec = (dc, -dr)
            
            next_r = r + next_vec[0]
            next_c = c + next_vec[1]
            
            # Check Bounds
            if 0 <= next_r < self.size and 0 <= next_c < self.size:
                # Valid Neighbor.
                # Which Approach corresponds to arriving at (next_r, next_c) with next_vec?
                # If I move (0, 1) [East], I arrive at West side of next node? 
                # No, Approach is defined by origin direction usually?
                # GridNetwork:
                # App 0: North -> South.
                # If I move South (1, 0). Next node sees me coming from North.
                # So Next Approach is determined by vector.
                
                next_app = -1
                if next_vec == (1, 0): next_app = 0
                elif next_vec == (0, -1): next_app = 1
                elif next_vec == (-1, 0): next_app = 2
                elif next_vec == (0, 1): next_app = 3
                
                # And which lane at next intersection?
                # Usually we can pick ANY lane (L, S, R). 
                # This represents the choice for the Next Next turn.
                # So we connect to ALL 3 lanes of that approach.
                if next_app != -1:
                    ids = [
                        self.grid_to_id.get((next_r, next_c, next_app, 0), -1),
                        self.grid_to_id.get((next_r, next_c, next_app, 1), -1),
                        self.grid_to_id.get((next_r, next_c, next_app, 2), -1)
                    ]
                    next_lanes = [i for i in ids if i != -1]
            
            # ENDPOINT COORDINATES (For Manhattan Routing)
            # Center of node (r, c). Scale by lane_length? 
            # Or just use (r, c) as units?
            # Let's use physical units: x = c * length, y = r * length
            # Wait, usually X is Col, Y is Row (inverted y in image, but here map).
            
            end_x = float(c) * self.lane_length
            end_y = float(r) * self.lane_length
            
            # Set to Map
            self.lane_map.set_lane(lid, self.lane_length, self.speed_limit, 
                                   next_lanes, signal_node, phase,
                                   endpoint=(end_x, end_y))
                                   
        return self.lane_map
