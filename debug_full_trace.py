import sys
import traceback

sys.path.insert(0, 'D:\\TrafficSim')

try:
    print("Importing...")
    from core import TrafficGridNetwork
    print("Creating network...")
    network = TrafficGridNetwork(grid_size=2, spawn_rate=0.1)
    print("Running step...")
    network.step()
    print("✅ SUCCESS!")
except Exception as e:
    print(f"\n❌ ERROR: {e}\n")
    traceback.print_exc()
    print("\n" + "="*60)
    print("FULL EXCEPTION DETAILS:")
    print("="*60)
    import sys
    exc_type, exc_value, exc_traceback = sys.exc_info()
    traceback.print_exception(exc_type, exc_value, exc_traceback, limit=None, file=sys.stdout)
