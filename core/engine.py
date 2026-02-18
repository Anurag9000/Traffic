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
        
        # Optimization: Pre-fetch all active vehicle locations for conflict check
        # This is expensive O(N) check inside boundary loop, but necessary for spillback
        active_lane_ids = vehicles[:, IDX_LANE_ID].astype(int)
        active_positions = vehicles[:, IDX_POS_ON_LANE]
        
        for idx in cross_indices:
            current_lane = int(lane_ids[idx])
            overrun = positions[idx] - lane_lengths[idx]
            
            # ROUTING LOGIC
            # 1. Check if vehicle has a target
            tgt_x = vehicles[idx, IDX_TARGET_X]
            tgt_y = vehicles[idx, IDX_TARGET_Y]
            has_target = (tgt_x != -1.0)
            
            # Convert CuPy scalar to Python int for indexing
            next_opts = self.map.adjacency[int(current_lane)]
            
            best_next_lane = -1
            
            if has_target:
                # Targeted Routing: Minimize Manhattan Distance to Target
                valid_opts = [l for l in next_opts if l != -1]
                
                if not valid_opts:
                    best_next_lane = -1 # Dead End
                else:
                    # Check if we reached the target?
                    # Current lane end is considered "current position"
                    # FIX: Convert CuPy scalar to Python int for indexing
                    curr_end_x, curr_end_y = self.map.lane_endpoints[int(current_lane)]
                    dist_to_target = abs(curr_end_x - tgt_x) + abs(curr_end_y - tgt_y)
                    
                    # Check if vehicle arrived at destination
                    if dist_to_target < ARRIVAL_THRESHOLD_M:
                         best_next_lane = LANE_ID_ARRIVED  # Vehicle arrived!
                    else:
                        # Pick best next lane by minimizing distance to target
                        candidates = []
                        min_d = 1e9
                        
                        for opt_lane in valid_opts:
                            # Heuristic: Distance from NEXT lane's end to target
                            # FIX: Convert CuPy scalar to Python int for indexing
                            opt_end_x, opt_end_y = self.map.lane_endpoints[int(opt_lane)]
                            d = abs(opt_end_x - tgt_x) + abs(opt_end_y - tgt_y)
                            
                            if d < min_d:
                                min_d = d
                                candidates = [opt_lane]
                            elif abs(d - min_d) < 1.0: # Identical distance
                                candidates.append(opt_lane)
                                
                        # Pick random from candidates to distribute flow
                        best_next_lane = random.choice(candidates)
            else:
                # Random Walk (Default)
                # Filter valid options manually (CuPy scalar -> Python int conversion happens implicitly in iteration?)
                # next_opts is a CuPy array if self.map.adjacency is on GPU?
                # core/engine.py imports xp as np.
                # If np is numpy, it works. If cupy, iterating is slow but works.
                # Note: next_opts = self.map.adjacency[int(current_lane)] was retrieved earlier.
                
                valid_opts = []
                for l in next_opts:
                    if l != -1:
                        valid_opts.append(l)
                    else:
                        break # Optimization: -1 are usually at the end
                
                if valid_opts:
                    best_next_lane = random.choice(valid_opts)
                else:
                    best_next_lane = -1
            
            next_lane = best_next_lane
            
            # FIX 1: Spillback / Ghosting Check
            if next_lane >= 0:
                # Check occupancy of next_lane at start (0.0 to 8.0 meters)
                # Overrun adds to position, so check 0 + overrun + buffer
                # Buffer ~ 6m (car length + gap)
                
                # Check if any vehicle is on next_lane with pos < SAFE_BUFFER
                entry_pos = overrun
                safe_buffer = 8.0
            if next_lane >= 0:
                # Fix 7: Length-Aware Spillback Check
                # Optimization: Only check if next_lane has ANY vehicles near start.
                mask = (lane_ids == next_lane) & (positions < 20.0)
                
                if np.any(mask):
                    # Potential conflict. check specifics.
                    my_len = self.lengths[idx]
                    
                    # Leaders on target lane
                    leaders_pos = positions[mask]
                    leaders_len = self.lengths[mask]
                    
                    # Effective rear of leader = pos - length.
                    rear_of_leader = leaders_pos - leaders_len
                    
                    # Minimum rear position
                    if len(rear_of_leader) > 0:
                        min_rear = np.min(rear_of_leader)
                        
                        if min_rear < (my_len + 2.0): # 2m buffer
                             # BLOCKED! Spillback.
                             vehicles[idx, IDX_VEL] = 0.0
                             vehicles[idx, IDX_POS_ON_LANE] = lane_lengths[idx] - 0.5 
                             continue 
            
            if next_lane >= 0:
                vehicles[idx, IDX_LANE_ID] = next_lane
                vehicles[idx, IDX_POS_ON_LANE] = overrun
            else:
                # Vehicle Exit (or Arrived)
                vehicles[idx, IDX_STATUS] = 0.0
                vehicles[idx, IDX_POS_ON_LANE] = -1000.0
                
                # Log Metric (Differentiate Arrival vs Exit?)
                # For now unified.
                
                # Log Metric
                v_id = int(vehicles[idx, IDX_ID])
                start_t = vehicles[idx, IDX_START_TIME]
                end_t = self.current_time
                self.completed_trips.append((v_id, start_t, end_t, 1))

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
