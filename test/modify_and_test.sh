#!/bin/bash

echo "🚀 Quick Live Reload Test Script"
echo "================================="
echo ""

# Function to modify the test file
modify_test_file() {
    local version=$1
    local message=$2
    local emoji=$3
    local sleep_time=$4
    
    cat > quick_reload_test.py << EOF
#!/usr/bin/env python3
"""
Quick live reload demonstration script
This script can be easily modified to test live reload functionality
"""

import time
import datetime

# Configuration - modify these values to test live reload
TITLE = "${emoji} LIVE RELOAD TEST - VERSION ${version}"
MESSAGE = "${message}"
SLEEP_TIME = ${sleep_time}
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
EOF
    echo "✅ Modified quick_reload_test.py to version $version"
}

echo "Step 1: Start the watcher"
echo "Run: ww quick_reload_test.py"
echo ""
echo "Step 2: Follow the logs in another terminal"
echo "Run: ww ww-quick-reload-test.service follow"
echo ""
echo "Step 3: Press Enter to start automatic modifications..."
read

echo "🔄 Modification 1: Changing message and emoji..."
modify_test_file "2" "FIRST MODIFICATION - Live reload working!" "⚡" "1.5"
sleep 5

echo "🔄 Modification 2: Changing sleep time and message..."
modify_test_file "3" "SECOND MODIFICATION - Faster updates!" "🚀" "1"
sleep 5

echo "🔄 Modification 3: Different emoji and slower updates..."
modify_test_file "4" "THIRD MODIFICATION - Slower but steady!" "🐢" "3"
sleep 5

echo "🔄 Modification 4: Back to fast updates with new message..."
modify_test_file "5" "FINAL MODIFICATION - Testing complete!" "🎉" "0.5"

echo ""
echo "🎯 Live reload testing complete!"
echo ""
echo "You should have seen the script restart 4 times with different:"
echo "- Messages"
echo "- Emojis" 
echo "- Sleep intervals"
echo ""
echo "Each restart should show a new 'Started at:' timestamp"
echo ""
echo "To stop: ww stop ww-quick-reload-test.service"