#!/bin/bash

# Comprehensive live reload testing script for ww (watchfiles-systemd)

echo "🧪 Starting comprehensive live reload tests for ww system"
echo "========================================================="

# Function to wait for user input
wait_for_user() {
    echo ""
    echo "Press Enter to continue to next test..."
    read
}

# Function to show running services
show_services() {
    echo "📊 Current ww services:"
    ww ps
    echo ""
}

# Test 1: Single file monitoring with basic script
echo "🔬 Test 1: Basic single file monitoring"
echo "Starting test.py (basic counter)..."
ww test.py
sleep 2
show_services
echo "✅ test.py should be running and counting. Check logs with: ww ww-test.service logs"
wait_for_user

# Test 2: Multiple file monitoring
echo "🔬 Test 2: Multiple file monitoring"
echo "Starting multiple test scripts..."
ww test_quotes.py
ww test_numbers.py
ww test_colors.py
sleep 2
show_services
echo "✅ Multiple services should be running. Each should show different output patterns."
wait_for_user

# Test 3: Live reload test - modify a file while it's running
echo "🔬 Test 3: Live reload functionality test"
echo "Starting test_modifiable.py..."
ww test_modifiable.py
sleep 3
echo ""
echo "🔄 Now modifying test_modifiable.py to test live reload..."
echo "The script should restart automatically when we change the file."
echo ""
echo "Original content shows: '🔄 Original message - modify me to test live reload!'"
echo "We'll change it to show: '🎉 MODIFIED! Live reload is working!'"
echo ""

# Create a backup and modify the file
cp test_modifiable.py test_modifiable.py.backup

# Modify the file to test live reload
cat > test_modifiable.py << 'EOF'
import time

# This file has been MODIFIED to test live reload
MESSAGE = "🎉 MODIFIED! Live reload is working!"
SLEEP_INTERVAL = 1
EMOJI = "⚡"

counter = 1
while True:
    print(f"{EMOJI} {MESSAGE} (iteration {counter})", flush=True)
    counter += 1
    time.sleep(SLEEP_INTERVAL)
EOF

echo "✅ File modified! Check the logs to see if the script restarted:"
echo "   ww ww-test-modifiable.service follow"
echo ""
echo "You should see the watchfiles detect the change and restart the script."
echo "The output should change from '🔄 Original message' to '🎉 MODIFIED! Live reload is working!'"
wait_for_user

# Restore original file
echo "🔄 Restoring original file..."
mv test_modifiable.py.backup test_modifiable.py
echo "✅ File restored. The script should reload again and show the original message."
wait_for_user

# Test 4: Directory monitoring
echo "🔬 Test 4: Directory monitoring test"
echo "Starting directory watcher..."
ww test_directory_watcher.py
sleep 2
echo ""
echo "Creating a new test file to trigger directory change detection..."
echo 'print("I am a new test file!")' > tmp_rovodev_new_test.py
sleep 3
echo "✅ Check if the directory watcher detected the new file."
echo "   ww ww-test-directory-watcher.service logs"
wait_for_user

# Test 5: Error handling
echo "🔬 Test 5: Error handling test"
echo "Starting error-prone script..."
ww test_error_prone.py
sleep 2
echo "✅ This script simulates warnings and errors. Monitor with:"
echo "   ww ww-test-error-prone.service follow"
wait_for_user

# Test 6: JSON output test
echo "🔬 Test 6: JSON output test"
echo "Starting JSON output script..."
ww test_json_output.py
sleep 2
echo "✅ This script outputs structured JSON. Check with:"
echo "   ww ww-test-json-output.service logs"
wait_for_user

# Test 7: System monitoring
echo "🔬 Test 7: System monitoring test"
echo "Starting system info script..."
ww test_system_info.py
sleep 2
echo "✅ This script shows system metrics. Check with:"
echo "   ww ww-test-system-info.service logs"
wait_for_user

# Show final status
echo "🏁 Final test status:"
show_services

echo ""
echo "🧹 Cleanup options:"
echo "1. Stop all services: ww stop-all"
echo "2. Stop specific service: ww stop <service-name>"
echo "3. View logs: ww <service-name> logs"
echo "4. Follow logs: ww <service-name> follow"
echo ""
echo "🎯 Live reload testing complete!"
echo ""
echo "Key things to verify:"
echo "✓ Services start correctly"
echo "✓ Each script produces expected output"
echo "✓ File modifications trigger automatic restarts"
echo "✓ Directory changes are detected"
echo "✓ Multiple services can run simultaneously"
echo "✓ Services can be stopped and restarted"