import time
import random

# This script occasionally "fails" to test error handling
counter = 1
while True:
    if counter % 10 == 0:
        print(f"⚠️  Simulated warning at iteration {counter}", flush=True)
    elif counter % 15 == 0:
        print(f"❌ Simulated error at iteration {counter}", flush=True)
        # Uncomment next line to test actual errors:
        # raise Exception("Test exception")
    else:
        print(f"✅ Normal operation - iteration {counter}", flush=True)
    
    counter += 1
    time.sleep(1)