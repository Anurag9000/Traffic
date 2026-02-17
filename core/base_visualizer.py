"""
Base visualizer class for traffic simulations using Pygame.

Consolidated from:
- traffic_grid/python_sim/visual.py
- traffic_real/visual_real.py

This module provides shared pygame initialization, event handling, and rendering utilities.
"""

from __future__ import annotations

import pygame
from abc import ABC, abstractmethod
from typing import Optional, Tuple


class BaseTrafficVisualizer(ABC):
    """
    Abstract base class for traffic simulation visualization.
    
    Handles common pygame setup, event loop, and simulation stepping.
    Subclasses implement specific rendering logic.
    """
    
    def __init__(
        self,
        width: int = 800,
        height: int = 800,
        title: str = "Traffic Simulation",
        speedup: float = 1.0,
        target_fps: int = 30,
        dt: float = 0.25,
    ):
        """
        Initialize the visualizer.
        
        Args:
            width: Window width in pixels
            height: Window height in pixels
            title: Window title
            speedup: Simulation speed multiplier
            target_fps: Target frames per second
            dt: Simulation timestep in seconds
        """
        self.width = width
        self.height = height
        self.title = title
        self.speedup = max(speedup, 0.01)
        self.target_fps = target_fps
        self.dt = dt
        
        # Pygame initialization
        try:
            pygame.init()
            pygame.font.init()
        except Exception as e:
            raise RuntimeError(f"Failed to initialize pygame: {e}")
        
        # Create window
        try:
            self.screen = pygame.display.set_mode((width, height))
            pygame.display.set_caption(title)
        except Exception as e:
            raise RuntimeError(f"Failed to create display window: {e}")
        
        # Initialize font (optional)
        try:
            self.font = pygame.font.SysFont("Arial", 12)
            self.font_large = pygame.font.SysFont("Arial", 24)
        except Exception as e:
            print(f"WARNING: Font initialization failed: {e}. UI text will not be displayed.")
            self.font = None
            self.font_large = None
        
        # State
        self.clock = pygame.time.Clock()
        self.running = True
        self.paused = False
        self.accumulator = 0.0
        
        # Colors (can be overridden by subclasses)
        self.COLOR_BG = (30, 30, 30)
        self.COLOR_ROAD = (100, 100, 100)
        self.COLOR_CAR = (255, 205, 0)
        self.COLOR_SIGNAL_RED = (220, 60, 60)
        self.COLOR_SIGNAL_GREEN = (100, 220, 100)
        self.COLOR_SIGNAL_YELLOW = (255, 255, 0)
        self.COLOR_TEXT = (255, 255, 255)

    def run(self) -> None:
        """Main visualization loop."""
        while self.running:
            real_dt = self.clock.tick(self.target_fps) / 1000.0
            self.handle_events()
            
            if not self.paused:
                sim_dt = real_dt * self.speedup
                self.step_simulation(sim_dt)
            
            self.draw_frame()
        
        pygame.quit()
        self.on_close()

    def handle_events(self) -> None:
        """Handle pygame events (keyboard, mouse, window)."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_SPACE:
                    self.paused = not self.paused
                else:
                    self.on_keypress(event.key)

    def on_keypress(self, key: int) -> None:
        """
        Handle additional keypresses.
        
        Override in subclasses for custom key handling.
        """
        pass

    def step_simulation(self, sim_dt: float) -> None:
        """
        Step the simulation forward.
        
        Uses accumulator pattern to ensure fixed timesteps.
        """
        self.accumulator += sim_dt
        while self.accumulator >= self.dt:
            self.step()
            self.accumulator -= self.dt

    @abstractmethod
    def step(self) -> None:
        """
        Execute one simulation step.
        
        Must be implemented by subclasses.
        """
        pass

    def draw_frame(self) -> None:
        """Draw one frame."""
        self.screen.fill(self.COLOR_BG)
        self.render()
        self.draw_ui()
        pygame.display.flip()

    @abstractmethod
    def render(self) -> None:
        """
        Render the simulation state.
        
        Must be implemented by subclasses.
        """
        pass

    def draw_ui(self) -> None:
        """
        Draw UI overlay (stats, controls, etc.).
        
        Override in subclasses for custom UI.
        """
        if self.font:
            status = "PAUSED" if self.paused else "RUNNING"
            text = self.font.render(f"Status: {status} | Speed: {self.speedup:.1f}x", True, self.COLOR_TEXT)
            self.screen.blit(text, (10, 10))

    def on_close(self) -> None:
        """
        Called when visualization closes.
        
        Override for cleanup (e.g., export stats).
        """
        pass

    # Utility rendering methods
    
    def draw_vehicle(self, pos: Tuple[int, int], color: Optional[Tuple[int, int, int]] = None, radius: int = 5) -> None:
        """Draw a vehicle as a circle."""
        color = color or self.COLOR_CAR
        pygame.draw.circle(self.screen, color, pos, radius)

    def draw_signal_light(
        self, 
        pos: Tuple[int, int], 
        state: str, 
        radius: int = 10,
        border: bool = True
    ) -> None:
        """
        Draw a traffic signal light.
        
        Args:
            pos: Center position (x, y)
            state: "green", "yellow", or "red"
            radius: Light radius
            border: Whether to draw border
        """
        color_map = {
            "green": self.COLOR_SIGNAL_GREEN,
            "yellow": self.COLOR_SIGNAL_YELLOW,
            "red": self.COLOR_SIGNAL_RED,
        }
        color = color_map.get(state, self.COLOR_SIGNAL_RED)
        
        if border:
            pygame.draw.circle(self.screen, (30, 30, 30), pos, radius + 4)
        pygame.draw.circle(self.screen, color, pos, radius)

    def draw_text(
        self, 
        text: str, 
        pos: Tuple[int, int], 
        color: Optional[Tuple[int, int, int]] = None,
        large: bool = False
    ) -> None:
        """Draw text at position."""
        if not self.font:
            return
        
        color = color or self.COLOR_TEXT
        font = self.font_large if large else self.font
        surface = font.render(text, True, color)
        self.screen.blit(surface, pos)

    def draw_line(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int],
        color: Optional[Tuple[int, int, int]] = None,
        width: int = 2
    ) -> None:
        """Draw a line."""
        color = color or self.COLOR_ROAD
        pygame.draw.line(self.screen, color, start, end, width)

    def draw_rect(
        self,
        rect: pygame.Rect,
        color: Optional[Tuple[int, int, int]] = None,
        border_radius: int = 0
    ) -> None:
        """Draw a rectangle."""
        color = color or self.COLOR_ROAD
        pygame.draw.rect(self.screen, color, rect, border_radius=border_radius)
