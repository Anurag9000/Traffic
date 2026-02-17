import sys
import traceback

sys.path.insert(0, 'D:\\TrafficSim')

try:
    print("Step 1: Importing modules...")
    from core import TrafficGridNetwork, VectorStatsRecorder
    print("SUCCESS - modules imported")
    
    print("\nStep 2: Creating grid network...")
    network = TrafficGridNetwork(grid_size=2, spawn_rate=0.1)
    print(f"SUCCESS - network created")
    
    print("\nStep 3: Running one step...")
    network.step()
    print("SUCCESS - step completed")
    
except Exception as e:
    print(f"\nERROR: {e}")
    print("\nFull traceback:")
    traceback.print_exc()
