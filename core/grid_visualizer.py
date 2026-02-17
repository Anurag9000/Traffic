"""
Grid network visualizer using the base visualizer.

Replaces traffic_grid/python_sim/visual.py with a cleaner implementation.
"""

from __future__ import annotations

import pygame
from typing import Any, Dict, Optional, Tuple

from core.base_visualizer import BaseTrafficVisualizer
from core.grid_network import TrafficGridNetwork
from core.dynamic import DynamicIntersectionController

# Constants
DT = 0.1  # Simulation timestep (seconds)
CAR_PIXEL = 8  # Vehicle size in pixels
STOP_LINE_PIXEL = 4  # Stop line thickness


class GridVisualizer(BaseTrafficVisualizer):
    """
    Visualizer for grid network simulations.
    
    Supports both single intersection (dynamic) and grid network modes.
    """
    
    SIGNAL_LIGHT_OFFSET_PX: float = 48.0
    
    def __init__(
        self,
        mode: str = "grid",
        grid_size: int = 3,
        speedup: float = 1.0,
        window_size: Optional[int] = None,
        window_title: Optional[str] = None,
        grid_controller_factory=None,
        target_coord: Optional[Tuple[int, int]] = None,
        target_fraction: float = 0.0,
        spawn_rate: float = 0.4,
        inflow_noise: float = 0.0,
        lane_length: Optional[float] = None,
        control_mode: int = 1, # MODE_ADAPTIVE
    ):
        """
        Initialize grid visualizer.
        
        Args:
            mode: "dynamic" for single intersection or "grid" for network
            grid_size: Size of grid (for grid mode)
            speedup: Simulation speed multiplier
            window_size: Window dimension (overrides defaults)
            window_title: Custom window title
            grid_controller_factory: Controller factory for grid mode
            target_coord: Target coordinate for targeted spawning
            target_fraction: Fraction of vehicles with targets
            spawn_rate: Vehicle spawn rate
            inflow_noise: Spawn rate noise
            lane_length: Custom lane length
            control_mode: Signal control mode (0=Fixed, 1=Adaptive)
        """
        if mode not in {"dynamic", "grid"}:
            raise ValueError("Mode must be 'dynamic' or 'grid'")
        
        self.mode = mode
        self.grid_size = grid_size
        
        # Determine window size
        if window_size is None:
            window_size = 1000 if mode == "dynamic" else 500
        
        title = window_title or f"Traffic Simulation ({mode})"
        
        super().__init__(
            width=window_size,
            height=window_size,
            title=title,
            speedup=speedup,
            dt=DT
        )
        
        # Create simulation
        self.spawn_rate = max(0.0, float(spawn_rate))
        self.inflow_noise = max(0.0, float(inflow_noise))
        
        if mode == "dynamic":
            self.sim = DynamicIntersectionController()
        else:
            self.sim = TrafficGridNetwork(
                size=grid_size,
                controller_factory=grid_controller_factory,
                target_coord=target_coord,
                target_fraction=target_fraction,
                spawn_rate=self.spawn_rate,
                inflow_noise=self.inflow_noise,
                lane_length=lane_length,
            )
            scenario_label = f"{title}_inflow{self.spawn_rate:.3f}"
            self.sim.enable_live_export(scenario_label)

    def step(self) -> None:
        """Execute one simulation step."""
        if self.mode == "dynamic":
            self.sim.step()
        else:
            self.sim.step(self.dt)

    def render(self) -> None:
        """Render the simulation."""
        if self.mode == "dynamic":
            self._render_dynamic()
        else:
            self._render_grid()

    def _render_dynamic(self) -> None:
        """Render single intersection view."""
        cx, cy = self.width / 2, self.height / 2
        box_half = 80
        
        # Draw intersection box
        self.draw_rect(
            pygame.Rect(cx - box_half, cy - box_half, 2 * box_half, 2 * box_half),
            color=(55, 55, 55)
        )
        
        # Draw approaches
        for approach in range(4):
            stop_orig = stop_line_pixel(approach)
            shift_x = cx - 500.0
            shift_y = cy - 500.0
            stop = (stop_orig[0] + shift_x, stop_orig[1] + shift_y)
            
            # Stop bar
            rect = pygame.Rect(stop[0] - 2, stop[1] - 30, 4, 60)
            self.draw_rect(rect, color=(200, 200, 200))
            
            # Signal light
            green_pos = (
                stop[0] - move_dir(approach)[0] * self.SIGNAL_LIGHT_OFFSET_PX,
                stop[1] - move_dir(approach)[1] * self.SIGNAL_LIGHT_OFFSET_PX,
            )
            state = "green" if approach == self.sim.current_approach() else "red"
            self.draw_signal_light((int(green_pos[0]), int(green_pos[1])), state)
        
        # Draw vehicles
        for approach, sublane, x in self.sim.get_vehicle_positions():
            pos_orig = car_pixel(approach, sublane, x)
            shift_x = cx - 500.0
            shift_y = cy - 500.0
            pos = (int(pos_orig[0] + shift_x), int(pos_orig[1] + shift_y))
            self.draw_vehicle(pos, radius=8)

    def _render_grid(self) -> None:
        """Render grid network view."""
        padding = 20
        size = self.sim.size
        cell = (self.width - 2 * padding) / size
        indicator_radius = max(3, int(cell * 0.08))
        lane_length_px = cell * 0.45
        lane_thickness = max(3, cell * 0.12)
        
        # Draw intersections
        for r in range(size):
            for c in range(size):
                x = padding + c * cell
                y = padding + r * cell
                intersection = self.sim.intersections[r][c]
                
                # Calculate queue size for shading
                total_queue = sum(len(lane) for approach in intersection.lanes for lane in approach)
                shade = int(min(110, total_queue * 4))
                base_color = (50 + shade, 50 + shade // 2, 50 + shade // 2)
                
                self.draw_rect(
                    pygame.Rect(x, y, cell - 2, cell - 2),
                    color=base_color,
                    border_radius=4
                )
                
                # Draw queue count
                controller = self.sim.controllers[r][c]
                if total_queue > 0 and self.font:
                    self.draw_text(str(total_queue), (x + cell / 2 - 5, y + cell / 2 - 6))
                
                # Draw signal indicators
                for approach in range(4):
                    px, py = self._signal_position(x, y, cell, approach)
                    state = "green" if controller.is_green(approach) else "red"
                    self.draw_signal_light((int(px), int(py)), state, radius=indicator_radius, border=False)
        
        # Draw vehicles
        for snap in self.sim.get_vehicle_snapshots():
            self._draw_vehicle_on_grid(padding, cell, lane_length_px, lane_thickness, snap)

    def _signal_position(self, x: float, y: float, cell: float, approach: int) -> Tuple[float, float]:
        """Calculate signal indicator position."""
        offset = cell * 0.2
        if approach == 0:  # north
            return x + cell / 2, y + offset
        if approach == 2:  # south
            return x + cell / 2, y + cell - offset
        if approach == 1:  # east
            return x + cell - offset, y + cell / 2
        return x + offset, y + cell / 2

    def _draw_vehicle_on_grid(
        self,
        padding: float,
        cell: float,
        lane_length_px: float,
        lane_thickness: float,
        snap: Dict[str, Any],
    ) -> None:
        """Draw a vehicle on the grid."""
        r = snap["row"]
        c = snap["col"]
        approach = snap["approach"]
        lane_idx = snap["lane"]
        position = snap["position"]
        color = snap["color"]
        
        center_x = padding + c * cell + cell / 2
        center_y = padding + r * cell + cell / 2
        
        dir_x, dir_y = move_dir(approach)
        perp_x, perp_y = -dir_y, dir_x
        
        stop_offset = cell * 0.15
        stop_x = center_x - dir_x * stop_offset
        stop_y = center_y - dir_y * stop_offset
        
        progress = min(1.0, max(0.0, position / self.sim.lane_length)) if self.sim.lane_length > 0 else 0.0
        px = stop_x + (-dir_x) * (progress * lane_length_px)
        py = stop_y + (-dir_y) * (progress * lane_length_px)
        
        lane_offsets = {0: -0.5, 1: 0.0, 2: 0.5}
        offset_scale = lane_offsets.get(lane_idx, 0.0)
        px += perp_x * offset_scale * lane_thickness * 2
        py += perp_y * offset_scale * lane_thickness * 2
        
        self.draw_vehicle((int(px), int(py)), color=color, radius=max(3, int(lane_thickness / 2)))

    def on_close(self) -> None:
        """Cleanup on close."""
        if self.mode == "grid":
            self.sim.finalize_exports()

    def draw_ui(self) -> None:
        """Draw UI overlay."""
        super().draw_ui()
        
        if self.mode == "grid" and self.font:
            stats = f"Grid: {self.sim.size}x{self.sim.size} | Spawn: {self.spawn_rate:.2f}"
            self.draw_text(stats, (10, 30))
