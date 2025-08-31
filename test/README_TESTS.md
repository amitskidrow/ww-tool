# Live Reload Testing Suite for ww (watchfiles-systemd)

This directory contains a comprehensive test suite for testing the live reload functionality of the `ww` tool.

## Test Files Overview

### Basic Test Files
- **`test.py`** - Original simple counter (hello world 1, 2, 3...)
- **`test_quotes.py`** - Displays random inspirational quotes
- **`test_numbers.py`** - Shows Fibonacci numbers and prime number detection
- **`test_colors.py`** - Colorful output with ANSI color codes
- **`test_datetime.py`** - Date/time information with formatting
- **`test_system_info.py`** - System metrics (CPU, RAM, disk usage)

### Live Reload Testing Files
- **`test_modifiable.py`** - Designed for easy modification to test live reload
- **`quick_reload_test.py`** - Quick demonstration script for live reload
- **`test_json_output.py`** - Structured JSON output
- **`test_error_prone.py`** - Simulates warnings and errors
- **`test_directory_watcher.py`** - Monitors its own directory for changes
- **`test_directory_monitor.py`** - Advanced directory monitoring

### Test Scripts
- **`run_live_reload_tests.sh`** - Comprehensive automated test suite
- **`modify_and_test.sh`** - Automated file modification for live reload testing

## Quick Start Testing

### 1. Single File Live Reload Test
```bash
# Start monitoring a single file
ww test.py

# Check status
ww ps

# View logs
ww ww-test.service logs

# Follow logs in real-time
ww ww-test.service follow
```

### 2. Live Reload Modification Test
```bash
# Start the quick test
ww quick_reload_test.py

# In another terminal, follow logs
ww ww-quick-reload-test.service follow

# Run automated modifications
./modify_and_test.sh
```

### 3. Multiple File Monitoring
```bash
# Start multiple services
ww test_quotes.py
ww test_numbers.py
ww test_colors.py

# Check all running services
ww ps

# Stop all services
ww stop-all
```

### 4. Directory Monitoring Test
```bash
# Start directory monitor
ww test_directory_monitor.py

# In another terminal, create/delete files to trigger changes
touch tmp_rovodev_test_file.py
rm tmp_rovodev_test_file.py
```

## Manual Live Reload Testing

### Test 1: Modify Content
1. Start: `ww test_modifiable.py`
2. Edit `test_modifiable.py` and change the `MESSAGE` variable
3. Save the file
4. Watch logs: `ww ww-test-modifiable.service follow`
5. Verify the script restarts and shows new message

### Test 2: Modify Sleep Interval
1. Start: `ww quick_reload_test.py`
2. Edit `quick_reload_test.py` and change `SLEEP_TIME`
3. Save the file
4. Verify the output frequency changes

### Test 3: Add/Remove Code
1. Start any test script
2. Add new functions or modify existing logic
3. Save and verify restart

## Expected Behavior

### Live Reload Should:
✅ Detect file changes immediately
✅ Restart the script automatically
✅ Show new "Started at:" timestamp
✅ Preserve service name and configuration
✅ Handle syntax errors gracefully
✅ Work with multiple files simultaneously

### Logs Should Show:
- `watchfiles v1.1.0 👀 path="..." target="..." filter=PythonFilter...`
- File change detection messages
- Process restart notifications
- New output from restarted script

## Directory Structure After Tests
```
test/
├── test.py                      # Original test
├── test_*.py                    # Various test scripts
├── quick_reload_test.py         # Quick demo
├── *.sh                         # Test automation scripts
├── README_TESTS.md              # This file
└── tmp_rovodev_*               # Temporary test files (auto-cleanup)
```

## Troubleshooting

### If Live Reload Doesn't Work:
1. Check if `ww` is properly installed: `ww --version`
2. Verify service is running: `ww ps`
3. Check logs for errors: `ww <service-name> logs`
4. Ensure file permissions are correct
5. Try stopping and restarting: `ww stop <service>` then `ww <file>`

### Common Issues:
- **Service not starting**: Check Python syntax in test file
- **No reload on change**: Verify file is being saved properly
- **Multiple restarts**: Check for auto-save features in editor

## Cleanup
```bash
# Stop all ww services
ww stop-all

# Remove temporary files
rm tmp_rovodev_*

# Check no services running
ww ps
```

## Next Steps: Directory Monitoring
After single file testing, test directory-level monitoring:
1. Monitor entire directory for changes
2. Test with multiple file modifications
3. Test with file creation/deletion
4. Test with subdirectory changes