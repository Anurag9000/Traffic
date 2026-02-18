"""
Vectorized Vehicle Physics Module

Implements the Intelligent Driver Model (IDM) for car-following behavior.
All operations are GPU-accelerated via the gpu module.
"""

from core.gpu import xp
import numpy as np


def calculate_idm_vectorized(
    pos: np.ndarray,
    v: np.ndarray,
    lane_ids: np.ndarray,
    lengths: np.ndarray,
    v0: np.ndarray,     # Desired Speed (vector)
    a: np.ndarray,      # Max Accel (vector)
    b: np.ndarray,      # Comfort Decel (vector)
    delta: float = 4.0,
    T: float = 1.5,
    dt: float = 0.1,
    s0: float = 2.0
) -> np.ndarray:
    """
    Vectorized Intelligent Driver Model (IDM) calculation.
    """
    n = len(pos)
    if n == 0:
        return np.array([])
        
    # 1. Identify Leaders (Assumes sorted by lane asc, pos desc)
    # leader of i is i-1 IF same lane
    # i=0 has no leader (in that sorted block) or we handle boundary.
    
    # Shift arrays to align leader with follower
    leader_pos = np.roll(pos, 1) # leader is at i-1? No, roll moves last to first.
    # If sorted descending pos:
    # 0: Pos 100
    # 1: Pos 90
    # Leader of 1 is 0.
    # So leader_pos[i] = pos[i-1].
    # But pos[i-1] corresponds to index i-1.
    # `np.roll(pos, 1)` moves [A, B, C] -> [C, A, B]. 
    # Index 1 (B) gets A. Correct.
    
    leader_v = np.roll(v, 1)
    leader_len = np.roll(lengths, 1)
    leader_lane = np.roll(lane_ids, 1)
    
    # Valid Leader Mask: Same Lane
    has_leader = (lane_ids == leader_lane)
    # Prevent wrap-around (index 0 should not match index -1)
    has_leader[0] = False
    
    # 2. Gap (s)
    # s = x_lead - x_own - l_lead
    gap = leader_pos - pos - leader_len
    gap = np.maximum(gap, 0.1) # Avoid zero/neg
    
    # 3. Approach Rate (delta_v)
    # dv = v_own - v_lead
    dv = v - leader_v
    
    # 4. Desired Gap (s_star)
    # s* = s0 + vT + (v * dv) / (2 * sqrt(ab))
    
    term1 = s0 + (v * T)
    term2 = (v * dv) / (2.0 * np.sqrt(a * b))
    
    s_star = term1 + term2
    
    # 5. Acceleration
    # a * [1 - (v/v0)^delta - (s*/s)^2]
    
    free_road = 1.0 - (v / v0) ** delta
    interaction = - (s_star / gap) ** 2
    
    # Only apply interaction if has_leader
    interaction[~has_leader] = 0.0
    
    acc = a * (free_road + interaction)
    
    return acc


def update_kinematics(
    positions: 'xp.ndarray',
    velocities: 'xp.ndarray',
    accelerations: 'xp.ndarray',
    dt: float
) -> tuple:
    """
    Update vehicle positions and velocities using Euler integration.
    
    Args:
        positions: Current positions (m)
        velocities: Current velocities (m/s)
        accelerations: Current accelerations (m/s²)
        dt: Time step (s)
    
    Returns:
        (new_positions, new_velocities)
    """
    # Update velocities
    new_velocities = velocities + accelerations * dt
    new_velocities = xp.maximum(new_velocities, 0.0)  # No negative speeds
    
    # Update positions
    new_positions = positions + new_velocities * dt
    
    return new_positions, new_velocities


__all__ = ['calculate_idm_vectorized', 'update_kinematics']
