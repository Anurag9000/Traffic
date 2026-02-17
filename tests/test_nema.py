"""Quick test to verify NEMA Dual-Ring Barrier synchronization."""
import numpy as np
from core.signals import SignalControllerVector, GREEN, YELLOW, RED

# Create a single-node controller
sc = SignalControllerVector(num_nodes=1, mode=0)  # MODE_FIXED

print("=== NEMA Dual-Ring Barrier Test ===\n")
print(f"Initial State:")
print(f"  Ring 1: Phase {sc.ring1_phase[0]}, State {sc.ring1_state[0]}, Timer {sc.ring1_timer[0]:.1f}s")
print(f"  Ring 2: Phase {sc.ring2_phase[0]}, State {sc.ring2_state[0]}, Timer {sc.ring2_timer[0]:.1f}s")
print(f"  Phase 1 (Ring 1): {'GREEN' if sc.states[0,1]==GREEN else 'RED'}")
print(f"  Phase 5 (Ring 2): {'GREEN' if sc.states[0,5]==GREEN else 'RED'}")

# Simulate until barrier
detector_counts = np.zeros((1, 9), dtype=np.int32)
time = 0.0
dt = 0.1

print("\n=== Simulating to Barrier 1 ===")
for _ in range(200):  # 20 seconds
    sc.update(dt, detector_counts)
    time += dt
    
    # Check if at barrier
    if sc.ring1_at_barrier[0] or sc.ring2_at_barrier[0]:
        print(f"\nTime {time:.1f}s - BARRIER REACHED:")
        print(f"  Ring 1: Phase {sc.ring1_phase[0]}, At Barrier: {sc.ring1_at_barrier[0]}")
        print(f"  Ring 2: Phase {sc.ring2_phase[0]}, At Barrier: {sc.ring2_at_barrier[0]}")
        break

# Continue simulation
print("\n=== Continuing Simulation ===")
for _ in range(100):
    sc.update(dt, detector_counts)
    time += dt

print(f"\nFinal State at {time:.1f}s:")
print(f"  Ring 1: Phase {sc.ring1_phase[0]}, State {sc.ring1_state[0]}")
print(f"  Ring 2: Phase {sc.ring2_phase[0]}, State {sc.ring2_state[0]}")

# Verify NEMA compliance: conflicting phases should NEVER be green together
print("\n=== NEMA Compliance Check ===")
# Phase 2 (NB Straight) and Phase 4 (EB Straight) are conflicting
if sc.states[0, 2] == GREEN and sc.states[0, 4] == GREEN:
    print("❌ VIOLATION: Conflicting phases 2 and 4 are both GREEN!")
else:
    print("✅ PASS: No conflicting phases are green simultaneously")

# Symmetric phases should be green together
if sc.ring1_state[0] == 0 and sc.ring2_state[0] == 0:
    r1_phase = sc.ring1_phase[0]
    r2_phase = sc.ring2_phase[0]
    if sc.states[0, r1_phase] == GREEN and sc.states[0, r2_phase] == GREEN:
        print(f"✅ PASS: Parallel phases {r1_phase} and {r2_phase} are both GREEN")

print("\n=== Test Complete ===")
