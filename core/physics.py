"""
Vectorized Vehicle Physics Module

Implements the Intelligent Driver Model (IDM) for car-following behavior.
All operations are GPU-accelerated via the gpu module.
"""

from .gpu import xp


def calculate_idm_vectorized(
    v: 'xp.ndarray',
    v_lead: 'xp.ndarray',
    s: 'xp.ndarray',
    v_max: 'xp.ndarray',
    a_max: 'xp.ndarray',
    b_comfort: 'xp.ndarray',
    delta: float = 4.0,
    s0: float = 2.0,
    T: float = 1.5
) -> 'xp.ndarray':
    """
    Calculate IDM acceleration for all vehicles.
    
    Args:
        v: Current velocities (m/s)
        v_lead: Leader velocities (m/s)
        s: Gaps to leaders (m)
        v_max: Desired velocities (m/s)
        a_max: Maximum accelerations (m/s²)
        b_comfort: Comfortable decelerations (m/s²)
        delta: Acceleration exponent (default 4.0)
        s0: Minimum gap (m, default 2.0)
        T: Time headway (s, default 1.5)
    
    Returns:
        Accelerations (m/s²)
    """
    # Free-flow acceleration term
    v_ratio = v / xp.maximum(v_max, 1e-6)
    free_term = 1.0 - xp.power(v_ratio, delta)
    
    # Interaction term
    dv = v - v_lead
    s_star = s0 + xp.maximum(0.0, v * T + (v * dv) / (2.0 * xp.sqrt(a_max * b_comfort)))
    interaction_term = xp.power(s_star / xp.maximum(s, 1e-6), 2.0)
    
    # Combined acceleration
    accel = a_max * (free_term - interaction_term)
    
    return accel


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
