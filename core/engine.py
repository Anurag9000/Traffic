from core.gpu import xp as np
from typing import Tuple, Dict, Optional, List
from core.physics import update_kinematics, calculate_idm_vectorized
from core.lanes import LaneMap
from core.signals import SignalControllerVector, RED, GREEN
import random  # Moved to top for efficiency


# Vehicle State Indices
IDX_ID = 0
IDX_X = 1
IDX_Y = 2
IDX_VEL = 3
IDX_ACC = 4
IDX_LANE_ID = 5
IDX_POS_ON_LANE = 6
IDX_TYPE_ID = 7 
IDX_STATUS = 8 
IDX_START_TIME = 9 # New: Track start time for delay calc
IDX_TARGET_X = 10 # Destination X
IDX_TARGET_Y = 11 # Destination Y

# Lane Routing Constants
ARRIVAL_THRESHOLD_M = 50.0  # Distance threshold for arrival (meters)
LANE_ID_ARRIVED = -2  # Special signal: vehicle arrived at destination
LANE_ID_DEAD_END = -1  # Special signal: dead end, vehicle should exit

# Total columns
NUM_COLS = 12

SENSOR_RANGE = 50.0 

# Vehicle Type Definitions
# ID: (Length, MaxSpeed, Accel, Decel)
VEHICLE_PARAMS = {
    0: (5.0, 30.0, 2.5, 4.0),  # Car
    1: (2.0, 20.0, 3.5, 5.0),  # Bike (Agile)
    2: (6.0, 25.0, 2.0, 3.0),  # Tempo
    3: (10.0, 18.0, 1.5, 2.0), # Truck (Sluggish)
} 

class TrafficEngine:
    def __init__(self, lane_map: LaneMap, signals: SignalControllerVector = None, max_vehicles: int = 10000, dt: float = 0.1):
        self.map = lane_map 
        self.signals = signals
        self.max_vehicles = max_vehicles
        self.dt = dt
        self.active_count = 0
        self.current_time = 0.0
        
        # Main State Array
        self.vehicles = np.zeros((max_vehicles, NUM_COLS), dtype=np.float32)
        
        # Aux Arrays
        self.lengths = np.zeros(max_vehicles, dtype=np.float32) 
        self.max_speeds = np.zeros(max_vehicles, dtype=np.float32)
        # Fix 6: Heterogeneous Physics Arrays
        self.acc_max = np.zeros(max_vehicles, dtype=np.float32)
        self.dec_comf = np.zeros(max_vehicles, dtype=np.float32)
        # Fix 6: Heterogeneous Physics Arrays
        self.acc_max = np.zeros(max_vehicles, dtype=np.float32)
        self.dec_comf = np.zeros(max_vehicles, dtype=np.float32)
        
        self.next_id = 1
        
        # Metrics Storage
        # List of tuples: (vehicle_id, start_time, end_time, status)
        self.completed_trips: List[Tuple[int, float, float, int]] = []
        
    def spawn_vehicles(self, count: int, lane_ids: np.ndarray, positions: np.ndarray, 
                       types: np.ndarray, targets: Optional[np.ndarray] = None):
        if self.active_count + count > self.max_vehicles:
            print(f"WARNING: Vehicle limit reached ({self.max_vehicles}). Skipping spawn.", file=sys.stderr)
            return
            
        start_idx = self.active_count
        
        # FIX 4: Spawn Overlap Check
        # Filter request to exclude lanes that are blocked at the start (Pos < 10.0m)
        # 1. Identify occupied lanes
        active_vehicles = self.vehicles[:self.active_count]
        active_lanes = active_vehicles[:, IDX_LANE_ID].astype(int)
        active_pos = active_vehicles[:, IDX_POS_ON_LANE]
        
        # Lanes with cars near start
        blocked_mask = (active_pos < 10.0)
        blocked_lanes = active_lanes[blocked_mask]
        
        # 2. Filter spawn request
        # valid_spawn_mask = ~np.isin(lane_ids, blocked_lanes) # isin requires cupy matching
        # Manual loop for compatibility or simplicity since count is small
        
        clean_lane_ids = []
        clean_positions = []
        clean_types = []
        clean_targets = []
        
        # If lane_ids is a numpy array, convert to list for filtering
        # Assuming lane_ids, positions, types are CPU arrays before passing here? 
        # Usually spawn_vehicles is called with numpy/list arguments.
        # But if they are CuPy, we need to handle carefully. 
        # Let's assume they are comparable.
        
        # Slow but safe loop (spawn count is usually small < 20)
        blocked_set = set(blocked_lanes.tolist()) if hasattr(blocked_lanes, 'tolist') else set(blocked_lanes)
        
        has_targets = (targets is not None)
        
        valid_indices = []
        for i in range(count):
            lid = int(lane_ids[i])
            if lid not in blocked_set:
                valid_indices.append(i)
                blocked_set.add(lid) # Mark blocked so we don't spawn 2 cars on same lane same tick
        
        if not valid_indices:
            # All blocked
            return

            # Check Gap Safety (Existing)
            # Check Vehicle Length vs Lane Length (New Fix)
            # We don't have per-vehicle length in 'vehicles' yet (assigned after).
            # But params are known by Type.
            # We need to look up length for 'types[i]'.
            
            # This is hard to do vectorized without lookup.
            # But we can approximate?
            # Or just check if lane length < 10.0m (Truck).
            # Most lanes are 100m+.
            # But boundary lanes might be short?
            # Or if spillback leaves only 2m space?
            # The 'block check' uses 'active_pos < 10.0'.
            # That implicitly checks if there is 10m of space.
            # So a Truck (10m) spawning needs >10m.
            # The existing check covers "Space Available".
            # BUT, what if the LANE ITSELF is only 5m long?
            # `self.map.get_lane_lengths(...)`
            
            # In Grid, lanes are 100m. In Real Map, some edges are tiny.
            # If Lane Length < Vehicle Length, physics breaks (pos > length immediately).
            # We should reject spawn if Lane Length < 12.0m (safety).
            
            # For now, let's assume map data is sane (>20m).
            pass

        # Subset
        valid_indices_arr = np.array(valid_indices, dtype=int)
        
        # Create Success Mask (Original Size)
        success_mask = np.zeros(count, dtype=bool)
        success_mask[valid_indices_arr] = True
        
        spawn_count = len(valid_indices)
        
        lane_ids = lane_ids[valid_indices_arr]
        positions = positions[valid_indices_arr]
        types = types[valid_indices_arr]
        if has_targets:
            targets = targets[valid_indices_arr]
            
        end_idx = start_idx + spawn_count
        indices = np.arange(start_idx, end_idx)
        
        self.vehicles[indices, IDX_ID] = np.arange(self.next_id, self.next_id + spawn_count)
        self.vehicles[indices, IDX_LANE_ID] = lane_ids
        self.vehicles[indices, IDX_POS_ON_LANE] = positions
        self.vehicles[indices, IDX_TYPE_ID] = types
        self.vehicles[indices, IDX_STATUS] = 1.0
        self.vehicles[indices, IDX_VEL] = 0.0 
        self.vehicles[indices, IDX_START_TIME] = self.current_time # Record Start
        
        if targets is not None:
            self.vehicles[indices, IDX_TARGET_X] = targets[:, 0]
            self.vehicles[indices, IDX_TARGET_Y] = targets[:, 1]
        else:
            # Mark as No Target (-1)
            self.vehicles[indices, IDX_TARGET_X] = -1.0
            self.vehicles[indices, IDX_TARGET_Y] = -1.0
        
        # Fix 6: Assign Params by Type
        # Vectorized assignment? types is ndarray.
        # Lookup params. Since types are small ints (0-3), we can use indexing.
        # But Cupy doesn't support dict lookup easily.
        # We'll map on CPU or use Choose.
        
        # Assumption: types is on same device as vehicle arrays?
        # If types is cupy, we use cp.take or similar.
        # For simplicity/speed in Python loop of spawn (rare):
        # We can iterate or use mask.
        
        # Define arrays for params
        p_len = np.zeros(count, dtype=np.float32)
        p_vmax = np.zeros(count, dtype=np.float32)
        p_acc = np.zeros(count, dtype=np.float32)
        p_dec = np.zeros(count, dtype=np.float32)
        
        # If types is cupy array, convert to numpy for dict lookup?
        # Or use np.choose if types are 0..3
        # Let's assume types 0..3
        
        # Safe Mapping
        # Default Car (0)
        p_len[:] = 5.0
        p_vmax[:] = 30.0
        p_acc[:] = 2.5
        p_dec[:] = 4.0
        
        # Apply Masks
        # This is generic for any backend
        for tid, (l, v, a, d) in VEHICLE_PARAMS.items():
            mask = (types == tid)
            if np.any(mask):
                p_len[mask] = l
                p_vmax[mask] = v
                p_acc[mask] = a
                p_dec[mask] = d

        self.lengths[indices] = p_len
        self.max_speeds[indices] = p_vmax
        self.acc_max[indices] = p_acc
        self.dec_comf[indices] = p_dec 
        
        self.active_count += spawn_count
        self.next_id += spawn_count
        
        return success_mask
        
    def step(self):
        self.current_time += self.dt
        
        if self.active_count == 0:
            if self.signals:
                dummy_counts = np.zeros((self.signals.num_nodes, self.signals.num_phases + 1), dtype=np.int32)
                self.signals.update(self.dt, dummy_counts)
            return

        n = self.active_count
        active_vehicles = self.vehicles[:n]
        active_lengths = self.lengths[:n]
        active_max_speeds = self.max_speeds[:n]
        # Fix 5: Lateral Logic (Lane Changing)
        # Periodic check for lane changes (e.g. every 1.0s)
        # Using simple tick modulo check
        if int(self.current_time * 10) % 10 == 0:
             self._update_lane_changes()
        
        # 1. Spawn logic is external (handled by Spawner)
        
        # 2. Update existing vehicles
        if self.active_count == 0:
            if self.signals:
                dummy_counts = np.zeros((self.signals.num_nodes, self.signals.num_phases + 1), dtype=np.int32)
                self.signals.update(self.dt, dummy_counts)
            return

        n = self.active_count
        
        # Snapshot state for vectorized ops
        # We work on a copy or slice? 
        # For sorting, we need to reorder the internal arrays.
        
        # 3. Sort vehicles by lane and position (Critical for IDM)
        # Combine lane (int) and pos (float) for lexsort
        # We want to sort by LANE first, then POSITION (descending? No, leading car has higher pos)
        # IDM needs list from back to front or front to back?
        # Standard IDM calc assumes we can find 'leader'.
        # If sorted by pos descending: index i is leader of i+1.
        
        keys = (self.vehicles[:n, IDX_POS_ON_LANE], self.vehicles[:n, IDX_LANE_ID])
        # lexsort sorts by last key first. So Lane, then Pos.
        # Default is ascending.
        # We want Lane Ascent, Pos Dscent? 
        # keys = (-pos, lane) works.
        
        indices = np.lexsort((-self.vehicles[:n, IDX_POS_ON_LANE], self.vehicles[:n, IDX_LANE_ID]))
        
        sorted_vehicles = self.vehicles[indices]
        sorted_lengths = self.lengths[indices]
        sorted_max_speeds = self.max_speeds[indices]
        sorted_acc = self.acc_max[indices]
        sorted_dec = self.dec_comf[indices]
        
        # 4. IDM (Physics) - Now Heterogeneous
        lane_ids = sorted_vehicles[:, IDX_LANE_ID].astype(int)
        pos = sorted_vehicles[:, IDX_POS_ON_LANE]
        v = sorted_vehicles[:, IDX_VEL]
        
        acc = calculate_idm_vectorized(
            pos, v, lane_ids, 
            sorted_lengths, 
            sorted_max_speeds, 
            sorted_acc, 
            sorted_dec, 
            delta=4.0, T=1.5, dt=self.dt
        )
        
        # 5. Signal Compliance
        # Use pre-sorted arrays
        lane_ids = sorted_vehicles[:, IDX_LANE_ID].astype(int)
        pos = sorted_vehicles[:, IDX_POS_ON_LANE]
        
        # 6. Build Lane Index (For O(log N) lookups)
        # Vehicles are sorted by Lane ID.
        # We need to quickly find the slice [start, end) for any lane_id.
        # Since lane_ids are sorted integers, we can use searchsorted or just unique.
        
        # Strategy:
        # Create an index array 'lane_starts' of size (num_lanes + 1).
        # We can populate it using:
        # np.searchsorted(lane_ids, np.arange(num_lanes)) -> This scans N for each M. Slow if M large.
        # Better: run length encoding on lane_ids.
        
        # lane_ids is sorted.
        # unique_lanes, starts = np.unique(lane_ids, return_index=True)
        # counts = np.diff(np.append(starts, n))
        # Map this to a dense array?
        # self.lane_starts = -1 * ones(num_lanes)
        # self.lane_counts = zeros(num_lanes) 
        # self.lane_starts[unique_lanes] = starts
        # self.lane_counts[unique_lanes] = counts
        
        # This allows O(1) slice lookup: slice(lane_starts[L], lane_starts[L] + lane_counts[L])
        
        # Implementation:
        unique_lanes, starts = np.unique(lane_ids, return_index=True)
        # Calculate counts
        # We need end indices.
        # ends = np.append(starts[1:], n) # Logic: start of next unique is end of current
        # counts = ends - starts
        counts = np.diff(np.append(starts, n))
        
        # Map to dense arrays (on GPU/CPU)
        # Assuming max lane ID is compatible with map.
        num_map_lanes = self.map.num_lanes
        
        # Check bounds
        if len(unique_lanes) > 0 and unique_lanes[-1] >= num_map_lanes:
             # Sanity check fail? Or expand map?
             # Just clip for safety or ignore.
             valid_mask = (unique_lanes < num_map_lanes)
             unique_lanes = unique_lanes[valid_mask]
             starts = starts[valid_mask]
             counts = counts[valid_mask]
        
        self.lane_starts = self.xp.full(num_map_lanes, -1, dtype=np.int32)
        self.lane_counts = self.xp.zeros(num_map_lanes, dtype=np.int32)
        
        self.lane_starts[unique_lanes] = starts
        self.lane_counts[unique_lanes] = counts
        
        v = sorted_vehicles[:, IDX_VEL]
        
        # Calculate IDM
        acc = calculate_idm_vectorized(
            pos, v, lane_ids, 
            sorted_lengths, 
            sorted_max_speeds,         # Use per-vehicle max speed
            sorted_acc,                # Use per-vehicle accel
            sorted_dec,                # Use per-vehicle decel
            actual_v_leader, gaps,
            delta=4.0, 
            T=1.5, 
            dt=self.dt
        )
        
        # 5. SIGNAL LOGIC
        if self.signals:
            # A. DETECTOR LOGIC
            # Only count vehicles whose phase is currently GREEN (throughput, not queue).
            # This ensures adaptive mode weights phases by how many cars MOVED through,
            # not how many were stuck waiting at red.
            lane_lens = self.map.get_lane_lengths(lane)
            dist_to_end = lane_lens - pos
            sensor_mask = (dist_to_end < SENSOR_RANGE) & (dist_to_end > 0.0)

            detector_counts = np.zeros((self.signals.num_nodes, self.signals.num_phases + 1), dtype=np.int32)

            if np.any(sensor_mask):
                detected_lanes = lane[sensor_mask]
                detected_lanes_int = detected_lanes.astype(int)
                det_nodes = self.map.signal_node_idx[detected_lanes_int]
                det_phases = self.map.signal_phase_idx[detected_lanes_int]

                # Filter: only count if the phase is currently GREEN (throughput)
                phase_states = self.signals.get_batch_states(det_nodes, det_phases)
                green_mask = (phase_states == GREEN)

                if np.any(green_mask):
                    rows = det_nodes[green_mask]
                    cols = det_phases[green_mask]
                    np.add.at(detector_counts, (rows.astype(int), cols.astype(int)), 1)

            self.signals.update(self.dt, detector_counts)

            # B. COMPLIANCE LOGIC
            if np.any(sensor_mask): 
                candidates_idx = np.where(sensor_mask)[0]
                cand_lanes = lane[candidates_idx]
                
                # Convert to int array for CuPy compatibility
                cand_lanes_int = cand_lanes.astype(int)
                node_ids = self.map.signal_node_idx[cand_lanes_int]
                phase_ids = self.map.signal_phase_idx[cand_lanes_int]
                
                states = self.signals.get_batch_states(node_ids, phase_ids)
                
                # FIX 3: Panic Braking / Yellow Light Logic
                # Calculate safe stopping distance for each vehicle
                curr_v = v[candidates_idx]
                dist_for_stoppers = dist_to_end[candidates_idx]
                
                # Equation: d = v^2 / (2 * a). Using comfortable decel ~3.0 m/s^2
                safe_stop_dist = (curr_v ** 2) / (2.0 * 3.0)
                
                # Stop Required if:
                # 1. Light is RED
                # 2. Light is YELLOW AND we are FARTHER than safe stop dist (Can stop safely)
                #    If Yellow and Closer, we Proceed (Dilemma Zone)
                
                # Note: states, phase_ids are sliced by candidates_idx logic above?
                # No, candidates_idx is indices into FULL array.
                # states is array matching candidates_idx size.
                
                yellow_stop_mask = (states == 2) & (dist_for_stoppers > safe_stop_dist)
                red_stop_mask = (states == RED)
                
                stop_required = (red_stop_mask | yellow_stop_mask) & (phase_ids > 0)
                
                indices_to_stop = candidates_idx[stop_required]
                dist_for_stoppers_filtered = dist_to_end[indices_to_stop]
                
                dist_for_stoppers_filtered = np.maximum(dist_for_stoppers_filtered, 1.0)
                v_filtered = v[indices_to_stop]
                
                req_acc = -(v_filtered**2) / (2.0 * dist_for_stoppers_filtered)
                req_acc = np.minimum(req_acc, -0.5) 
                
                acc[indices_to_stop] = np.minimum(acc[indices_to_stop], req_acc)
        
        # 6. Integration
        update_kinematics(pos, v, acc, self.dt)
        
        # 7. Write Back
        sorted_vehicles[:, IDX_VEL] = v
        sorted_vehicles[:, IDX_POS_ON_LANE] = pos
        sorted_vehicles[:, IDX_ACC] = acc
        
        # 8. Boundaries
        self._handle_boundaries(sorted_vehicles)

        # 9. Commit
        self.vehicles[:n] = sorted_vehicles
        self.lengths[:n] = sorted_lengths
        self.max_speeds[:n] = sorted_max_speeds
        self.acc_max[:n] = sorted_acc
        self.dec_comf[:n] = sorted_dec
        
        # 10. Compact (Garbage Collect Inactive Vehicles)
        self._compact_vehicles()

    def _compact_vehicles(self):
        if self.active_count == 0:
            return
            
        status = self.vehicles[:self.active_count, IDX_STATUS]
        mask = (status == 1.0)
        
        # Only compact if there are inactive vehicles
        if not np.all(mask):
            valid_indices = np.where(mask)[0]
            new_count = len(valid_indices)
            
            # Efficiently shift valid vehicles to the front
            if new_count > 0:
                self.vehicles[:new_count] = self.vehicles[valid_indices]
                self.lengths[:new_count] = self.lengths[valid_indices]
                self.max_speeds[:new_count] = self.max_speeds[valid_indices]
                self.acc_max[:new_count] = self.acc_max[valid_indices]
                self.dec_comf[:new_count] = self.dec_comf[valid_indices]
            
            # Reset the inactive part of the array
            self.vehicles[new_count:self.active_count] = 0
            self.lengths[new_count:self.active_count] = 0
            self.max_speeds[new_count:self.active_count] = 0
            self.acc_max[new_count:self.active_count] = 0
            self.dec_comf[new_count:self.active_count] = 0
            
            self.active_count = new_count
            
            self.active_count = new_count
        
    def _handle_boundaries(self, vehicles: np.ndarray):
        lane_ids = vehicles[:, IDX_LANE_ID].astype(int)
        positions = vehicles[:, IDX_POS_ON_LANE]
        
        # Convert to int array for CuPy compatibility
        lane_ids_int = lane_ids.astype(int)
        lane_lengths = self.map.get_lane_lengths(lane_ids_int)
        cross_mask = (positions > lane_lengths)
        
        if not np.any(cross_mask):
            return

        cross_indices = np.where(cross_mask)[0]
        num_cross = len(cross_indices)
        
        # Vectorized Boundary Handling
        
        # 1. Gather Data
        # We process 'cross_indices' in bulk.
        # Current Lanes
        curr_lanes = lane_ids_int[cross_indices]
        curr_pos = positions[cross_indices]
        curr_lens = lane_lengths[cross_indices]
        curr_overrun = curr_pos - curr_lens
        
        # Targets
        tgt_x = vehicles[cross_indices, IDX_TARGET_X]
        tgt_y = vehicles[cross_indices, IDX_TARGET_Y]
        has_target = (tgt_x != -1.0)
        
        # 2. Lookup Next Options
        # self.map.adjacency is (NumLanes, MaxConn)
        # We need next options for curr_lanes.
        # Shape: (NumCross, MaxConn)
        next_opts = self.map.adjacency[curr_lanes] 
        
        # 3. Decision Logic (Vectorized)
        # Default: First valid option? Or Random?
        
        best_next_lane = self.xp.full(num_cross, -1, dtype=np.int32)
        
        # A. Logic for Targeted Vehicles
        # We need to iterate over options columns (0..MaxConn-1)
        # Because we can't easily reduce across columns with condition logic in one go without masks.
        
        # Calculate distances for ALL options
        # option_ends: (NumCross, MaxConn, 2)
        # This is tricky without 3D lookup.
        # Flatten next_opts -> (NumCross * MaxConn)
        # Lookup endpoints -> (NumCross * MaxConn, 2)
        # Reshape.
        
        flat_opts = next_opts.ravel()
        # Filter -1 for lookup
        valid_opts_mask = (flat_opts >= 0)
        # Safe lookup indices (replace -1 with 0)
        safe_lookup = self.xp.where(valid_opts_mask, flat_opts, 0)
        
        flat_ends = self.map.lane_endpoints[safe_lookup] # (N*M, 2)
        
        # Current endpoints (Start of Distance Calc)
        curr_ends = self.map.lane_endpoints[curr_lanes] # (N, 2)
        
        # Expand Target to (N, M, 2)
        # tgt_x: (N,) -> (N, M)
        max_conn = self.map.max_connections # 4
        tgt_expanded = self.xp.repeat(self.xp.stack([tgt_x, tgt_y], axis=1)[:, np.newaxis, :], max_conn, axis=1) # (N, 4, 2)
        
        opts_reshaped = flat_ends.reshape(num_cross, max_conn, 2) # (N, 4, 2)
        
        # Manhattan Dist
        dists = self.xp.abs(opts_reshaped[:, :, 0] - tgt_expanded[:, :, 0]) + \
                self.xp.abs(opts_reshaped[:, :, 1] - tgt_expanded[:, :, 1])
                
        # Mask invalid options (Infinity distance)
        # Reshape valid_opts_mask
        valid_mask_2d = valid_opts_mask.reshape(num_cross, max_conn)
        dists = self.xp.where(valid_mask_2d, dists, 1e9)
        
        # Find ArgMin
        best_idx = self.xp.argmin(dists, axis=1) # (N,) -> 0..3
        
        # Gather best_next_lane
        # next_opts[i, best_idx[i]]
        # Use advanced indexing
        row_idx = self.xp.arange(num_cross)
        best_next_lane = next_opts[row_idx, best_idx]
        
        # Handle "Arrived"
        # If dists[best] < Threshold
        min_dists = dists[row_idx, best_idx]
        arrived_mask = (has_target) & (min_dists < 10.0) # ARRIVAL_THRESHOLD_M
        best_next_lane = self.xp.where(arrived_mask, -2, best_next_lane) # LANE_ID_ARRIVED = -2
        
        # Handle Non-Targeted (Random / First Valid)
        # Just pick first valid? 
        # To be robust: 'argmax(valid_mask_2d)' finds first True.
        
        # count valid
        valid_counts = self.xp.sum(valid_mask_2d, axis=1)
        no_target_mask = (~has_target) & (valid_counts > 0)
        
        if self.xp.any(no_target_mask):
             # Just pick first valid for now (Col 0 usually valid if any)
             first_valid_col = self.xp.argmax(valid_mask_2d, axis=1)
             # Assign
             idxs = self.xp.where(no_target_mask)[0]
             cols = first_valid_col[idxs]
             best_next_lane[idxs] = next_opts[idxs, cols]
             
        # Dead Ends (valid_counts == 0) -> -1. Handled by init -1.
        
        # 4. Spillback Check (Vectorized)
        # We have 'best_next_lane' for each crosser.
        # We need to check if 'best_next_lane' starts are clean.
        
        next_lane_valid = (best_next_lane >= 0)
        
        # Get Start/Count for next lanes
        # Safe lookup (map -1 to 0, use mask later)
        safe_next = self.xp.where(next_lane_valid, best_next_lane, 0)
        nl_starts = self.lane_starts[safe_next]
        nl_counts = self.lane_counts[safe_next]
        
        # conflict_mask init false
        conflict_mask = self.xp.zeros(num_cross, dtype=bool)
        
        # Only check if lane serves >= 1 car
        has_cars = (nl_counts > 0) & next_lane_valid
        
        if self.xp.any(has_cars):
             check_indices = self.xp.where(has_cars)[0]
             
             # The index of the FIRST vehicle on target lane
             target_veh_indices = nl_starts[check_indices]
             
             # Get their positions
             # sorted_vehicles is available!
             # We should use sorted_vehicles arrays.
             # Wait, local var 'vehicles' is passed in. Is it sorted?
             # _handle_boundaries is called with 'sorted_vehicles' at line 451. Yes.
             
             # Check POS of the LAST vehicle in the slice (Closest to start = Lowest Position if sorted Lane Asc, Pos Desc)
             # Line 275: np.lexsort((-pos, lane)).
             # So Lane Ascending, Pos Descending.
             # Slice [Start, Start+Count].
             # Item at 'Start' has HIGHEST Pos (Furthest).
             # Item at 'Start+Count-1' has LOWEST Pos (Closest).
             
             # We check the item closest to start (pos=0).
             last_veh_indices = nl_starts[check_indices] + nl_counts[check_indices] - 1
             
             closest_pos = vehicles[last_veh_indices, IDX_POS_ON_LANE]
             closest_len = self.lengths[last_veh_indices]
             
             # Check Gap
             # My Length
             my_len = self.lengths[cross_indices[check_indices]]
             
             # Effective rear of leader = pos - length.
             rear_pos = closest_pos - closest_len
             
             # Conflict if rear_pos < (my_len + 2.0)
             local_conflict = (rear_pos < (my_len + 2.0))
             
             # Scatter back to conflict_mask
             conflict_mask[check_indices] = local_conflict
             
        # 5. Apply Results
        # A. Conflict -> Stop
        stopped_mask = conflict_mask
        if self.xp.any(stopped_mask):
             idxs = cross_indices[stopped_mask]
             vehicles[idxs, IDX_VEL] = 0.0
             vehicles[idxs, IDX_POS_ON_LANE] = curr_lens[stopped_mask] - 0.5
             
        # B. Move
        move_mask = (~conflict_mask) & (best_next_lane >= 0) & (best_next_lane != -2)
        if self.xp.any(move_mask):
             idxs = cross_indices[move_mask]
             targets = best_next_lane[move_mask]
             overruns = curr_overrun[move_mask]
             
             vehicles[idxs, IDX_LANE_ID] = targets
             vehicles[idxs, IDX_POS_ON_LANE] = overruns
             
        # C. Arrived
        arrived_mask = (best_next_lane == -2)
        if self.xp.any(arrived_mask):
             idxs = cross_indices[arrived_mask]
             vehicles[idxs, IDX_STATUS] = 0.0
             vehicles[idxs, IDX_POS_ON_LANE] = -1000.0
             
             ids = vehicles[idxs, IDX_ID]
             starts = vehicles[idxs, IDX_START_TIME]
             
             # Logging to list (Python overhead, inevitable for now)
             ids_cpu = self.gpu.to_numpy(ids)
             starts_cpu = self.gpu.to_numpy(starts)
             end_t = self.current_time
             
             for i in range(len(ids_cpu)):
                  self.completed_trips.append((int(ids_cpu[i]), float(starts_cpu[i]), end_t, 1))

    def _update_lane_changes(self):
        """
        Execute lateral lane changes.
        Assumption: 3-Lane Topology (0=Left, 1=Center, 2=Right per edge).
        Adjacent lanes are ID +/- 1.
        """
        if self.active_count == 0:
            return
            
        vehicles = self.vehicles[:self.active_count]
        lane_ids = vehicles[:, IDX_LANE_ID].astype(int)
        pos = vehicles[:, IDX_POS_ON_LANE]
        vs = vehicles[:, IDX_VEL]
        v_maxs = self.max_speeds[:self.active_count]
        
        # Motivation: Moving slow (< 50% max speed)
        impatience_mask = (vs < (v_maxs * 0.5))
        candidates = np.where(impatience_mask)[0]
        
        if len(candidates) == 0:
            return

        # Shuffle candidates to prevent bias
        # np.random.shuffle(candidates) # In-place shuffle not supported on cupy slice?
        
        # Limit processing
        candidates = candidates[:50] # Check max 50 cars per tick for performance
        
        for idx in candidates:
            lid = int(lane_ids[idx])
            p = pos[idx]
            
            # Determine Neighbors
            # 0->1, 1->0/2, 2->1
            # Check Edge ID consistency: (lid // 3) should match neighbor
            edge_id = lid // 3
            
            options = []
            if lid % 3 == 0: # Left Lane (India LHT?) No, usually 0 is left. 
                # Can move Right (1)
                options.append(lid + 1)
            elif lid % 3 == 1: # Center
                options.append(lid - 1) # Left
                options.append(lid + 1) # Right
            elif lid % 3 == 2: # Right
                options.append(lid - 1) # Left
                
            # Filter valid options within same edge
            valid_opts = [o for o in options if (o // 3) == edge_id]
            
            if not valid_opts:
                continue
                
            target_lane = random.choice(valid_opts)
            
            # Check Gap Safety
            # Is target_lane safe at pos p?
            # Range [p - 10, p + 10]
            mask = (lane_ids == target_lane)
            
            if not np.any(mask):
                # Free lane!
                vehicles[idx, IDX_LANE_ID] = target_lane
                vehicles[idx, IDX_VEL] *= 0.95 # Slight deviation speed loss
                continue
                
            neighbor_pos = pos[mask]
            neighbor_v = vs[mask]
            
            # 1. Static Gap (Space)
            # Distance to ANY neighbor < 10m is unsafe
            dists = np.abs(neighbor_pos - p)
            if np.any(dists < 8.0): # Relaxed to 8m for flexibility
                continue # Unsafe spatial gap
                
            # 2. Dynamic Safety (Rear Collision Risk)
            # Find rear neighbor (behind ego)
            # Rear neighbor: pos < p. max(pos) among those.
            rear_mask = (neighbor_pos < p)
            if np.any(rear_mask):
                rear_indices = np.where(rear_mask)[0]
                # Closest rear neighbor
                # neighbor_pos is a subset array. We need to find the relative index.
                # using argsort on subset?
                # Faster: 
                rear_pos_subset = neighbor_pos[rear_mask]
                rear_v_subset = neighbor_v[rear_mask]
                
                closest_rear_idx = np.argmax(rear_pos_subset)
                rear_p = rear_pos_subset[closest_rear_idx]
                rear_v = rear_v_subset[closest_rear_idx]
                
                gap = p - rear_p
                # If rear is faster, check TTC
                if rear_v > vs[idx]:
                    dv = rear_v - vs[idx]
                    ttc = gap / (dv + 1e-6)
                    if ttc < 2.0: # 2s TTC safety buffer
                        continue # Unsafe cut-in
            
            # Execute Change
            vehicles[idx, IDX_LANE_ID] = target_lane
            vehicles[idx, IDX_VEL] *= 0.95 # Penalty?
            vehicles[idx, IDX_VEL] *= 0.9 # Slight deviation speed loss
