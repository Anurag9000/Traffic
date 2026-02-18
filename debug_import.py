import sys
import traceback
try:
    print("Attempting to import core.intersection...")
    import core.intersection
    print("Import successful!")
except Exception:
    traceback.print_exc()
