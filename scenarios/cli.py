"""
Unified Command-Line Interface for Traffic Simulator

Single entry point for all simulation scenarios.
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core import (
    TrafficGridNetwork, SingleIntersection, RealTrafficNetwork,
    VectorStatsRecorder, MODE_FIXED, MODE_ADAPTIVE
)


def run_grid(args):
    """Run grid simulation."""
    print(f"🚦 Grid Simulation: {args.size}x{args.size}, Rate={args.rate}, Duration={args.duration}s")
    
    network = TrafficGridNetwork(
        grid_size=args.size,
        spawn_rate=args.rate,
        control_mode='adaptive' if args.adaptive else 'fixed'
    )
    
    recorder = VectorStatsRecorder(network.engine, prefix=f"grid_{args.size}x{args.size}")
    
    steps = int(args.duration / 0.1)
    for i in range(steps):
        network.step()
        if i % 10 == 0:
            recorder.log_step(network.engine.current_time)
        if i % 1000 == 0:
            print(f"  Step {i}/{steps} | Active: {network.engine.active_count}")
    
    stats = recorder.compute_summary()
    print(f"\n✅ Complete: {stats['total_vehicles']} vehicles, Avg delay: {stats['avg_delay']:.2f}s")


def run_intersection(args):
    """Run single intersection simulation."""
    print(f"🚦 Intersection Simulation: Rate={args.rate}, Duration={args.duration}s")
    
    sim = SingleIntersection(
        spawn_rate=args.rate,
        control_mode='adaptive' if args.adaptive else 'fixed'
    )
    
    recorder = VectorStatsRecorder(sim.engine, prefix="intersection")
    
    steps = int(args.duration / 0.1)
    for i in range(steps):
        sim.step()
        if i % 10 == 0:
            recorder.log_step(sim.engine.current_time)
        if i % 1000 == 0:
            print(f"  Step {i}/{steps} | Active: {sim.engine.active_count}")
    
    stats = recorder.compute_summary()
    print(f"\n✅ Complete: {stats['total_vehicles']} vehicles, Avg delay: {stats['avg_delay']:.2f}s")


def run_real(args):
    """Run real map simulation."""
    print(f"🗺️  Real Map Simulation: {args.map}, Duration={args.duration}s")
    
    network = RealTrafficNetwork(
        map_name=args.map,
        spawn_rate=args.rate,
        control_mode='adaptive' if args.adaptive else 'fixed'
    )
    
    recorder = VectorStatsRecorder(network.engine, prefix=f"real_{args.map}")
    
    steps = int(args.duration / 0.1)
    for i in range(steps):
        network.step()
        if i % 10 == 0:
            recorder.log_step(network.engine.current_time)
        if i % 1000 == 0:
            print(f"  Step {i}/{steps} | Active: {network.engine.active_count}")
    
    stats = recorder.compute_summary()
    print(f"\n✅ Complete: {stats['total_vehicles']} vehicles, Avg delay: {stats['avg_delay']:.2f}s")


def main():
    parser = argparse.ArgumentParser(
        description="Traffic Simulator - Clean, modular traffic simulation with GPU acceleration"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Simulation mode')
    
    # Grid simulation
    grid_parser = subparsers.add_parser('grid', help='NxN grid simulation')
    grid_parser.add_argument('--size', type=int, default=5, help='Grid size (default: 5)')
    grid_parser.add_argument('--rate', type=float, default=0.2, help='Spawn rate (default: 0.2)')
    grid_parser.add_argument('--duration', type=int, default=3600, help='Duration in seconds (default: 3600)')
    grid_parser.add_argument('--adaptive', action='store_true', help='Use adaptive signal control')
    
    # Intersection simulation
    int_parser = subparsers.add_parser('intersection', help='Single intersection simulation')
    int_parser.add_argument('--rate', type=float, default=0.5, help='Spawn rate (default: 0.5)')
    int_parser.add_argument('--duration', type=int, default=3600, help='Duration in seconds (default: 3600)')
    int_parser.add_argument('--adaptive', action='store_true', help='Use adaptive signal control')
    
    # Real map simulation
    real_parser = subparsers.add_parser('real', help='Real-world map simulation')
    real_parser.add_argument('--map', type=str, default='delhi', help='Map name (default: delhi)')
    real_parser.add_argument('--rate', type=float, default=0.3, help='Spawn rate (default: 0.3)')
    real_parser.add_argument('--duration', type=int, default=3600, help='Duration in seconds (default: 3600)')
    real_parser.add_argument('--adaptive', action='store_true', help='Use adaptive signal control')
    
    args = parser.parse_args()
    
    if args.command == 'grid':
        run_grid(args)
    elif args.command == 'intersection':
        run_intersection(args)
    elif args.command == 'real':
        run_real(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
