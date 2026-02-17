try:
    print("Importing SingleIntersection...")
    from core.intersection import SingleIntersection
    print("Success Importing SingleIntersection")
    sim = SingleIntersection()
    print("Success Instantiating SingleIntersection")
    print(f"Has step: {hasattr(sim, 'step')}")
    sim.step(0.1)
    print("Success Stepping SingleIntersection")
except Exception as e:
    print(f"FAILED: {e}")
    import traceback
    traceback.print_exc()
