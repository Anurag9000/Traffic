from core.gpu import xp as np
from collections import deque
from typing import Dict, List

# Signal States
RED = 0
GREEN = 1
YELLOW = 2

# Control Modes
MODE_FIXED = 0
MODE_ADAPTIVE = 1 # 5-Cycle Moving Average Split Recalculation (The Plan)
MODE_GAP_OUT = 2   # Traditional Actuated (Optional)

class SignalControllerVector:
    """
    THE ONLY Signal Controller in this repository - NEMA Dual-Ring Barrier logic.
    
    ⚠️ MANDATORY: This is the SOLE signal control mechanism. There are NO alternatives.
    ALL simulations (grid, intersection, real-world) MUST use this NEMA controller.
    
    NEMA Phase Mapping (Indian LHT Standards):
    Ring 1: Phases 1 (NB Right), 2 (NB Straight), 3 (SB Right), 4 (SB Straight)
    Ring 2: Phases 5 (EB Right), 6 (EB Straight), 7 (WB Right), 8 (WB Straight)
    
    Barrier 1: Between phases (1,5) and (2,6) - After right turns
    Barrier 2: Between phases (3,7) and (4,8) - After straights
    
    Both rings must reach a barrier before either can cross it (synchronized).
    
    Control Modes (ALL use NEMA Dual-Ring):
    - MODE_FIXED (0): Pre-set phase durations, NEMA dual-ring structure
    - MODE_ADAPTIVE (1): Recalculated durations, NEMA dual-ring structure
    - MODE_GAP_OUT (2): Actuated control, NEMA dual-ring structure
    
    The mode parameter only affects HOW durations are determined, NOT the underlying
    NEMA Dual-Ring Barrier architecture which is ALWAYS enforced.
    """
    def __init__(self, num_nodes: int, num_phases: int = 8, mode: int = MODE_ADAPTIVE):
        """
        Initialize NEMA Dual-Ring Signal Controller.
        
        Initialize NEMA Dual-Ring 8-Phase Signal Controller.
        
        Args:
            num_nodes: Number of intersections to control (must be > 0)
            num_phases: Number of phases (must be 8 for NEMA)
            mode: Control mode (MODE_FIXED=0 or MODE_ADAPTIVE=1)
        
        Raises:
            ValueError: If num_phases != 8 or num_nodes <= 0
        """
        # FIXED: Added validation for num_nodes
        if num_nodes <= 0:
            raise ValueError(f"num_nodes must be positive, got {num_nodes}")
        
        if num_phases != 8:
            raise ValueError(
                f"NEMA requires exactly 8 phases. Got {num_phases}. "
                "This is a MANDATORY requirement for NEMA Dual-Ring control."
            )
        
        self.num_nodes = num_nodes
        self.num_phases = num_phases
        self.mode = mode
        
        # State Array: [node_id, phase_id] -> State (0=Red, 1=Green, 2=Yellow)
        self.states = np.zeros((num_nodes, num_phases + 1), dtype=np.int32)
        
        # NEMA Dual-Ring State Tracking
        # Ring 1: Phases 1-4 (North/South movements)
        # Ring 2: Phases 5-8 (East/West movements)
        self.ring1_phase = np.zeros(num_nodes, dtype=np.int32)  # Current phase in ring 1 (1-4)
        self.ring2_phase = np.zeros(num_nodes, dtype=np.int32)  # Current phase in ring 2 (5-8)
        
        # Ring state: 0=Green, 1=Yellow, 2=Red Clearance
        self.ring1_state = np.zeros(num_nodes, dtype=np.int32)
        self.ring2_state = np.zeros(num_nodes, dtype=np.int32)
        
        # Independent timers for each ring
        self.ring1_timer = np.zeros(num_nodes, dtype=np.float32)
        self.ring2_timer = np.zeros(num_nodes, dtype=np.float32)
        
        # Accumulated Green Time per ring
        self.ring1_green_elapsed = np.zeros(num_nodes, dtype=np.float32)
        self.ring2_green_elapsed = np.zeros(num_nodes, dtype=np.float32)
        
        # Barrier waiting flags: True if ring is waiting at barrier
        self.ring1_at_barrier = np.zeros(num_nodes, dtype=np.bool_)
        self.ring2_at_barrier = np.zeros(num_nodes, dtype=np.bool_)
        
        # Configuration
        self.min_green = 10.0
        self.max_green = 60.0 
        self.yellow_time = 3.0
        self.red_clearance = 2.0
        self.extension_time = 2.0 
        
        # Phase durations: [Node, Phase 1-8]
        # In Adaptive mode, these are RECALCULATED every cycle
        self.phase_durations = np.zeros((num_nodes, num_phases + 1), dtype=np.float32)
        # Default starting durations (symmetric for NEMA compliance)
        self.phase_durations[:, 1] = 15.0  # Phase 1 (NB Right)
        self.phase_durations[:, 2] = 45.0  # Phase 2 (NB Straight)
        self.phase_durations[:, 3] = 15.0  # Phase 3 (SB Right)
        self.phase_durations[:, 4] = 45.0  # Phase 4 (SB Straight)
        self.phase_durations[:, 5] = 15.0  # Phase 5 (EB Right) - symmetric with 1
        self.phase_durations[:, 6] = 45.0  # Phase 6 (EB Straight) - symmetric with 2
        self.phase_durations[:, 7] = 15.0  # Phase 7 (WB Right) - symmetric with 3
        self.phase_durations[:, 8] = 45.0  # Phase 8 (WB Straight) - symmetric with 4
        
        self.cycle_time = 120.0 # Total cycle time target
        
        # History for Adaptive Max
        # Store counts for last 5 cycles: [Node, Phase, CycleIdx]
        # CycleIdx 0 is current accumulator. 1..5 are history.
        self.history_len = 5
        self.history_counts = np.zeros((num_nodes, num_phases + 1, self.history_len + 1), dtype=np.int32)
        
        # Initialize
        self.reset()
        
    def reset(self):
        """Initialize both rings to starting phases with synchronized timers."""
        # Ring 1 starts at Phase 1 (NB Right)
        # Ring 2 starts at Phase 5 (EB Right)
        self.ring1_phase[:] = 1
        self.ring2_phase[:] = 5
        
        # Both rings start in Green state
        self.ring1_state[:] = 0  # Green
        self.ring2_state[:] = 0  # Green
        
        # Initialize timers based on phase durations
        for n in range(self.num_nodes):
            self.ring1_timer[n] = self.phase_durations[n, 1]  # Phase 1 duration
            self.ring2_timer[n] = self.phase_durations[n, 5]  # Phase 5 duration
              
        self.ring1_green_elapsed[:] = 0.0
        self.ring2_green_elapsed[:] = 0.0
        
        self.ring1_at_barrier[:] = False
        self.ring2_at_barrier[:] = False
        
        self._apply_states()

    def update(self, dt: float, detector_counts: np.ndarray):
        """Update both rings independently with barrier synchronization."""
        # Decrement timers for both rings
        self.ring1_timer -= dt
        self.ring2_timer -= dt
        
        # Update Green Elapsed for rings in green state
        ring1_green_mask = (self.ring1_state == 0)
        ring2_green_mask = (self.ring2_state == 0)
        self.ring1_green_elapsed[ring1_green_mask] += dt
        self.ring2_green_elapsed[ring2_green_mask] += dt
        
        # ADAPTIVE MAX: Accumulate counts into current cycle buffer (Index 0)
        if self.mode == MODE_ADAPTIVE:
            self.history_counts[:, :, 0] += detector_counts
        
        # Process Ring 1 transitions
        ring1_finished = (self.ring1_timer <= 0)
        if np.any(ring1_finished):
            nodes = np.where(ring1_finished)[0]
            for node in nodes:
                self._process_ring1_transition(node, detector_counts)
        
        # Process Ring 2 transitions
        ring2_finished = (self.ring2_timer <= 0)
        if np.any(ring2_finished):
            nodes = np.where(ring2_finished)[0]
            for node in nodes:
                self._process_ring2_transition(node, detector_counts)

    def _process_ring1_transition(self, node: int, counts: np.ndarray):
        """Process Ring 1 phase transitions with barrier synchronization."""
        state = self.ring1_state[node]
        phase = self.ring1_phase[node]
        
        if state == 0:  # GREEN EXPIRED
            if self.mode == MODE_GAP_OUT:
                # GAP-OUT LOGIC: Extend if demand exists and under max_green
                demand = counts[node, phase] if phase > 0 else 0
                if demand > 0 and self.ring1_green_elapsed[node] < self.max_green:
                    self.ring1_timer[node] = self.extension_time
                    return  # Extend, don't transition
            
            # Transition to Yellow
            self.ring1_state[node] = 1  # Yellow
            self.ring1_timer[node] = self.yellow_time
            self._apply_states_node(node)
                
        elif state == 1:  # YELLOW EXPIRED
            self.ring1_state[node] = 2  # Red Clearance
            self.ring1_timer[node] = self.red_clearance
            self._apply_states_node(node)
            
        elif state == 2:  # RED CLEARANCE EXPIRED -> NEXT PHASE
            # Check if at barrier
            at_barrier = self._is_ring1_at_barrier(phase)
            
            if at_barrier:
                # Mark as waiting at barrier
                self.ring1_at_barrier[node] = True
                
                # Check if Ring 2 is also at barrier
                if self.ring2_at_barrier[node]:
                    # Both rings ready to cross barrier - proceed together
                    self._cross_barrier(node)
                else:
                    # Wait for Ring 2 - hold in red clearance
                    self.ring1_timer[node] = 0.1  # Small wait interval
                    return
            else:
                # Not at barrier - advance to next phase in ring
                self._advance_ring1_phase(node)
    
    def _process_ring2_transition(self, node: int, counts: np.ndarray):
        """Process Ring 2 phase transitions with barrier synchronization."""
        state = self.ring2_state[node]
        phase = self.ring2_phase[node]
        
        if state == 0:  # GREEN EXPIRED
            if self.mode == MODE_GAP_OUT:
                # GAP-OUT LOGIC
                demand = counts[node, phase] if phase > 0 else 0
                if demand > 0 and self.ring2_green_elapsed[node] < self.max_green:
                    self.ring2_timer[node] = self.extension_time
                    return
            
            # Transition to Yellow
            self.ring2_state[node] = 1
            self.ring2_timer[node] = self.yellow_time
            self._apply_states_node(node)
                
        elif state == 1:  # YELLOW EXPIRED
            self.ring2_state[node] = 2
            self.ring2_timer[node] = self.red_clearance
            self._apply_states_node(node)
            
        elif state == 2:  # RED CLEARANCE EXPIRED -> NEXT PHASE
            # Check if at barrier
            at_barrier = self._is_ring2_at_barrier(phase)
            
            if at_barrier:
                # Mark as waiting at barrier
                self.ring2_at_barrier[node] = True
                
                # Check if Ring 1 is also at barrier
                if self.ring1_at_barrier[node]:
                    # Both rings ready - cross together
                    self._cross_barrier(node)
                else:
                    # Wait for Ring 1
                    self.ring2_timer[node] = 0.1
                    return
            else:
                # Not at barrier - advance to next phase
                self._advance_ring2_phase(node)
    
    def _is_ring1_at_barrier(self, phase: int) -> bool:
        """Check if Ring 1 phase is at a barrier point."""
        # Barrier 1: After Phase 1 (before Phase 2)
        # Barrier 2: After Phase 3 (before Phase 4)
        return phase in [1, 3]
    
    def _is_ring2_at_barrier(self, phase: int) -> bool:
        """Check if Ring 2 phase is at a barrier point."""
        # Barrier 1: After Phase 5 (before Phase 6)
        # Barrier 2: After Phase 7 (before Phase 8)
        return phase in [5, 7]
    
    def _cross_barrier(self, node: int):
        """Both rings cross the barrier together (synchronized)."""
        # Clear barrier flags
        self.ring1_at_barrier[node] = False
        self.ring2_at_barrier[node] = False
        
        # Check if completing full cycle (both at Barrier 2)
        if self.ring1_phase[node] == 3 and self.ring2_phase[node] == 7:
            # Cycle complete - recalculate splits if adaptive
            if self.mode == MODE_ADAPTIVE:
                self._recalculate_phase_durations(node)
                # Shift history
                node_hist = self.history_counts[node]
                node_hist[:, 1:] = node_hist[:, :-1]
                node_hist[:, 0] = 0
        
        # Advance both rings to next phase
        self._advance_ring1_phase(node)
        self._advance_ring2_phase(node)
    
    def _advance_ring1_phase(self, node: int):
        """Advance Ring 1 to next phase."""
        current = self.ring1_phase[node]
        
        # Ring 1 sequence: 1 -> 2 -> 3 -> 4 -> 1
        next_phase = (current % 4) + 1
        
        self.ring1_phase[node] = next_phase
        self.ring1_state[node] = 0  # Green
        self.ring1_timer[node] = self.phase_durations[node, next_phase]
        self.ring1_green_elapsed[node] = 0.0
        
        self._apply_states_node(node)
    
    def _advance_ring2_phase(self, node: int):
        """Advance Ring 2 to next phase."""
        current = self.ring2_phase[node]
        
        # Ring 2 sequence: 5 -> 6 -> 7 -> 8 -> 5
        next_phase = ((current - 5) % 4) + 5
        
        self.ring2_phase[node] = next_phase
        self.ring2_state[node] = 0  # Green
        self.ring2_timer[node] = self.phase_durations[node, next_phase]
        self.ring2_green_elapsed[node] = 0.0
        
        self._apply_states_node(node)

    def _recalculate_phase_durations(self, node: int):
        """Recalculate phase durations based on demand (Adaptive mode)."""
        # Calculate moving average of last 5 cycles
        hist = self.history_counts[node, :, 1:]  # Shape (NumPhases, 5)
        avg_counts = np.mean(hist, axis=1)  # Shape (NumPhases,)
        
        # Calculate demand for each phase
        # NEMA requires symmetric phases to have same duration
        # Phase 1 & 5 must match (NB Right & EB Right)
        # Phase 2 & 6 must match (NB Straight & EB Straight)
        # Phase 3 & 7 must match (SB Right & WB Right)
        # Phase 4 & 8 must match (SB Straight & WB Straight)
        
        p1_5_dem = max(avg_counts[1], avg_counts[5])
        p2_6_dem = max(avg_counts[2], avg_counts[6])
        p3_7_dem = max(avg_counts[3], avg_counts[7])
        p4_8_dem = max(avg_counts[4], avg_counts[8])
        
        total_dem = p1_5_dem + p2_6_dem + p3_7_dem + p4_8_dem
        
        if total_dem < 1.0:
            # Default if no traffic
            self.phase_durations[node, 1] = self.phase_durations[node, 5] = 15.0
            self.phase_durations[node, 2] = self.phase_durations[node, 6] = 45.0
            self.phase_durations[node, 3] = self.phase_durations[node, 7] = 15.0
            self.phase_durations[node, 4] = self.phase_durations[node, 8] = 45.0
            return
        
        # Allocate cycle time (minus lost time)
        # Lost time = 4 phases * (yellow + red) * 2 rings = 8 * 5 = 40s
        total_green = self.cycle_time - 40.0
        
        # Proportional allocation with minimum green enforcement
        raw_demands = np.array([p1_5_dem, p2_6_dem, p3_7_dem, p4_8_dem])
        raw_demands += 0.1  # Avoid starvation
        
        ratios = raw_demands / np.sum(raw_demands)
        greens = ratios * total_green
        
        # Enforce min green
        greens = np.maximum(greens, self.min_green)
        
        # Re-normalize if needed
        if np.sum(greens) > total_green:
            greens = greens * (total_green / np.sum(greens))
        
        # Apply symmetric durations
        self.phase_durations[node, 1] = self.phase_durations[node, 5] = greens[0]
        self.phase_durations[node, 2] = self.phase_durations[node, 6] = greens[1]
        self.phase_durations[node, 3] = self.phase_durations[node, 7] = greens[2]
        self.phase_durations[node, 4] = self.phase_durations[node, 8] = greens[3]

    def _apply_states(self):
        """Apply signal states for all nodes."""
        for n in range(self.num_nodes):
            self._apply_states_node(n)
            
    def _apply_states_node(self, node: int):
        """Apply signal states for a single node based on dual-ring states."""
        # All phases start as RED
        self.states[node, :] = RED
        
        # Ring 1 active phase
        r1_phase = self.ring1_phase[node]
        r1_state = self.ring1_state[node]
        if r1_state == 0:  # Green
            self.states[node, r1_phase] = GREEN
        elif r1_state == 1:  # Yellow
            self.states[node, r1_phase] = YELLOW
        # else: Red clearance - stays RED
        
        # Ring 2 active phase (parallel)
        r2_phase = self.ring2_phase[node]
        r2_state = self.ring2_state[node]
        if r2_state == 0:  # Green
            self.states[node, r2_phase] = GREEN
        elif r2_state == 1:  # Yellow
            self.states[node, r2_phase] = YELLOW
        # else: Red clearance - stays RED
        
        # Free Turn Phase (0) is always GREEN
        self.states[node, 0] = GREEN

    def get_batch_states(self, node_ids: np.ndarray, phase_ids: np.ndarray) -> np.ndarray:
        """Get signal states for batch of (node, phase) pairs."""
        # Convert to int arrays for CuPy compatibility
        return self.states[node_ids.astype(int), phase_ids.astype(int)]
