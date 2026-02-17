import sys
import traceback

sys.path.insert(0, 'D:\\TrafficSim')

try:
    print("Importing core...")
    import core
    print("SUCCESS!")
except Exception as e:
    print(f"\nERROR: {e}")
    print("\nFull traceback:")
    traceback.print_exc()
