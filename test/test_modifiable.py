import time

# This file is designed to be easily modified to test live reload
MESSAGE = "🔄 Original message - modify me to test live reload!"
SLEEP_INTERVAL = 1
EMOJI = "🚀"

counter = 1
while True:
    print(f"{EMOJI} {MESSAGE} (iteration {counter})", flush=True)
    counter += 1
    time.sleep(SLEEP_INTERVAL)