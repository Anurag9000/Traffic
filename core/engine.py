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

        # Subset
        valid_indices = np.array(valid_indices, dtype=int)
        count = len(valid_indices)
        lane_ids = lane_ids[valid_indices]
        positions = positions[valid_indices]
        types = types[valid_indices]
        if has_targets:
            targets = targets[valid_indices]
            
        end_idx = start_idx + count
        indices = np.arange(start_idx, end_idx)
        
        self.vehicles[indices, IDX_ID] = np.arange(self.next_id, self.next_id + count)
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
        
        self.lengths[indices] = 5.0 
        self.max_speeds[indices] = 30.0 
        
        self.active_count += count
        self.next_id += count
        
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
        
        # 1. Sort Step
        lane_ids = active_vehicles[:, IDX_LANE_ID].astype(int)
        positions = active_vehicles[:, IDX_POS_ON_LANE]
        
        # CuPy requires array input for lexsort, not tuple
        sort_keys = np.vstack((-positions, lane_ids))
        sort_indices = np.lexsort(sort_keys)
        
        sorted_vehicles = active_vehicles[sort_indices]
        sorted_lengths = active_lengths[sort_indices]
        sorted_max_speeds = active_max_speeds[sort_indices]
        
        v = sorted_vehicles[:, IDX_VEL]
        pos = sorted_vehicles[:, IDX_POS_ON_LANE]
        lane = sorted_vehicles[:, IDX_LANE_ID].astype(int)
        
        # 2. Identify Leaders & Followers
        v_leader = np.roll(v, 1)
        pos_leader = np.roll(pos, 1)
        len_leader = np.roll(sorted_lengths, 1)
        lane_leader = np.roll(lane, 1)
        
        # 3. Gaps
        raw_gap = pos_leader - pos - len_leader
        valid_leader_mask = (lane == lane_leader)
        gaps = np.where(valid_leader_mask, raw_gap, 1000.0)
        actual_v_leader = np.where(valid_leader_mask, v_leader, 0.0)
        
        # 4. IDM
        # IDM parameters (standard values)
        a_max = 2.0  # max acceleration (m/s^2)
        b_comfort = 3.0  # comfortable deceleration (m/s^2)
        acc = calculate_idm_vectorized(v, actual_v_leader, gaps, sorted_max_speeds, a_max, b_comfort)
        
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
            
            # Reset the inactive part of the array
            self.vehicles[new_count:self.active_count] = 0
            self.lengths[new_count:self.active_count] = 0
            self.max_speeds[new_count:self.active_count] = 0
            
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
                
                # Vectorized search on ALL active vehicles
                # Note: This checks 'vehicles' which includes other crossers. 
                # If multiple cross to same lane same tick, they might overlap. 
                # Ideally we check 'updated' positions, but 'vehicles' is sorted copy.
                
                conflict_mask = (active_lane_ids == next_lane) & (active_positions < safe_buffer)
                if np.any(conflict_mask):
                    # BLOCKED! Spillback.
                    # Stop at end of current lane.
                    vehicles[idx, IDX_VEL] = 0.0
                    vehicles[idx, IDX_POS_ON_LANE] = lane_lengths[idx] - 0.5 # Park at end
                    continue # Do NOT change lane
            
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

    def get_snapshot(self):
        return self.vehicles[:self.active_count].copy()
