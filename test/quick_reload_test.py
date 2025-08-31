#!/usr/bin/env python3
"""
Quick live reload demonstration script
This script can be easily modified to test live reload functionality
"""

import time
import datetime

# Configuration - modify these values to test live reload
TITLE = "🔥 LIVE RELOAD TEST"
MESSAGE = "This is the ORIGINAL version"
SLEEP_TIME = 2
COUNTER_START = 1

def main():
    counter = COUNTER_START
    print(f"\n{TITLE}")
    print("=" * 50)
    print(f"Started at: {datetime.datetime.now()}")
    print("=" * 50)
    
    while True:
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {MESSAGE} - Count: {counter}", flush=True)
        counter += 1
        time.sleep(SLEEP_TIME)

if __name__ == "__main__":
    main()