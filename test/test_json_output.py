import time
import json
import random

counter = 1
while True:
    data = {
        "timestamp": time.time(),
        "counter": counter,
        "random_value": random.randint(1, 100),
        "status": "running",
        "message": f"JSON output #{counter}"
    }
    
    print(json.dumps(data, indent=2), flush=True)
    print("-" * 40, flush=True)
    counter += 1
    time.sleep(2)