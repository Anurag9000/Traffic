"""
Real-world map visualizer using the base visualizer.

Replaces traffic_real/visual_real.py with a cleaner implementation.
"""

from __future__ import annotations

import math
from typing import Tuple

from core.base_visualizer import BaseTrafficVisualizer
from traffic_real.real_network import RealTrafficNetwork
from traffic_grid.python_sim.core import DT


class RealMapVisualizer(BaseTrafficVisualizer):
    """
    Visualizer for real-world map simulations.
    
    Handles coordinate transformation from UTM/OSM to screen space.
    """
    
    def __init__(
        self,
        map_file: str,
        width: int = 1200,
        height: int = 800,
        title: str = "Real Map Traffic Simulation",
        speedup: float = 1.0,
    ):
        """
        Initialize real map visualizer.
        
        Args:
            map_file: Path to graphml map file
            width: Window width
            height: Window height
            title: Window title
            speedup: Simulation speed multiplier
        """
        super().__init__(
            width=width,
            height=height,
            title=title,
            speedup=speedup,
            dt=DT,
            target_fps=30
        )
        
        # Load simulation
        self.sim = RealTrafficNetwork(map_file)
        
        # Calculate map bounds and scaling
        self._setup_coordinate_transform()
        
        # Cache background (roads don't move)
        self._create_background()
        
        # Pre-cache incoming edges for signal rendering
        self._cache_incoming_edges()

    def _setup_coordinate_transform(self) -> None:
        """Calculate coordinate transformation from world to screen."""
        self.nodes = {}
        xs, ys = [], []
        
        for node, data in self.sim.G.nodes(data=True):
            self.nodes[node] = (data['x'], data['y'])
            xs.append(data['x'])
            ys.append(data['y'])
        
        self.min_x, self.max_x = min(xs), max(xs)
        self.min_y, self.max_y = min(ys), max(ys)
        
        self.map_w = self.max_x - self.min_x
        self.map_h = self.max_y - self.min_y
        
        # Calculate scale with padding
        padding = 50
        scale_x = (self.width - 2 * padding) / self.map_w
        scale_y = (self.height - 2 * padding) / self.map_h
        self.scale = min(scale_x, scale_y)
        
        self.pad = padding

    def world_to_screen(self, x: float, y: float) -> Tuple[int, int]:
        """Convert world coordinates to screen coordinates."""
        sx = self.pad + (x - self.min_x) * self.scale
        sy = self.pad + (self.max_y - y) * self.scale  # Invert Y
        return int(sx), int(sy)

    def _create_background(self) -> None:
        """Create cached background surface with roads."""
        import pygame
        self.bg_surface = pygame.Surface((self.width, self.height))
        self.bg_surface.fill(self.COLOR_BG)
        
        # Draw roads
        for u, v, data in self.sim.G.edges(data=True):
            if u not in self.nodes or v not in self.nodes:
                continue
            
            x1, y1 = self.nodes[u]
            x2, y2 = self.nodes[v]
            
            sx1, sy1 = self.world_to_screen(x1, y1)
            sx2, sy2 = self.world_to_screen(x2, y2)
            
            pygame.draw.line(self.bg_surface, self.COLOR_ROAD, (sx1, sy1), (sx2, sy2), 2)

    def _cache_incoming_edges(self) -> None:
        """Pre-cache incoming edges for each node."""
        self.incoming_map = {}
        for u, v, k, data in self.sim.G.edges(keys=True, data=True):
            if v not in self.incoming_map:
                self.incoming_map[v] = []
            self.incoming_map[v].append((u, v, k))

    def step(self) -> None:
        """Execute one simulation step."""
        self.sim.step()

    def render(self) -> None:
        """Render the simulation."""
        # Draw cached background
        self.screen.blit(self.bg_surface, (0, 0))
        
        # Draw signals
        self._render_signals()
        
        # Draw vehicles
        self._render_vehicles()

    def _render_signals(self) -> None:
        """Render traffic signals."""
        for node, signal in self.sim.signals.items():
            if node not in self.nodes:
                continue
            
            cx, cy = self.world_to_screen(*self.nodes[node])
            
            # Draw central hub
            import pygame
            pygame.draw.circle(self.screen, (40, 40, 40), (cx, cy), 4)
            
            if signal:
                # Draw status for each incoming edge
                incoming = self.incoming_map.get(node, [])
                for u, v, k in incoming:
                    if u not in self.nodes:
                        continue
                    
                    # Determine phase color
                    phase = self.sim.edge_phase_map.get((u, v, k))
                    if phase:
                        state = signal.get_phase_state(phase)
                        
                        # Draw indicator towards incoming node
                        ux, uy = self.world_to_screen(*self.nodes[u])
                        dx, dy = ux - cx, uy - cy
                        dist = math.hypot(dx, dy)
                        
                        if dist > 0:
                            dx, dy = dx / dist, dy / dist
                            sx, sy = cx + dx * 6, cy + dy * 6
                            ex, ey = cx + dx * 14, cy + dy * 14
                            
                            color_map = {
                                "green": self.COLOR_SIGNAL_GREEN,
                                "yellow": self.COLOR_SIGNAL_YELLOW,
                                "red": self.COLOR_SIGNAL_RED,
                            }
                            color = color_map.get(state, self.COLOR_SIGNAL_RED)
                            
                            self.draw_line((int(sx), int(sy)), (int(ex), int(ey)), color=color, width=3)

    def _render_vehicles(self) -> None:
        """Render vehicles on the map."""
        for (u, v, k), lane in self.sim.lanes.items():
            if not lane.vehicles:
                continue
            
            if u not in self.nodes or v not in self.nodes:
                continue
            
            x1, y1 = self.nodes[u]
            x2, y2 = self.nodes[v]
            
            for car in lane.vehicles:
                # Calculate position along edge
                t = car.position / lane.length if lane.length > 0 else 0
                t = max(0.0, min(1.0, t))
                
                # Interpolate position
                cur_x = x1 + (x2 - x1) * t
                cur_y = y1 + (y2 - y1) * t
                
                sx, sy = self.world_to_screen(cur_x, cur_y)
                self.draw_vehicle((sx, sy), radius=3)

    def draw_ui(self) -> None:
        """Draw UI overlay with simulation stats."""
        super().draw_ui()
        
        if self.font_large:
            # Format wall time
            sim_time = self.sim.time
            wall_time_sec = self.sim.start_time_seconds + sim_time
            wall_h = int((wall_time_sec % 86400) // 3600)
            wall_m = int((wall_time_sec % 3600) // 60)
            time_str = f"{wall_h:02d}:{wall_m:02d}"
            
            stats = f"Time: {time_str} (+{sim_time:.1f}s) | Cars: {self.sim.car_id_counter} | Exited: {self.sim.exited_cars}"
            self.draw_text(stats, (10, 10), large=True)
