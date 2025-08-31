import time
import os
import glob

# This script monitors its own directory and reports file changes
counter = 1
last_file_count = 0

while True:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    py_files = glob.glob(os.path.join(current_dir, "*.py"))
    file_count = len(py_files)
    
    if file_count != last_file_count:
        print(f"📁 Directory change detected! Now {file_count} Python files", flush=True)
        for f in sorted(py_files):
            print(f"   - {os.path.basename(f)}", flush=True)
        last_file_count = file_count
    else:
        print(f"📂 Directory scan #{counter} - {file_count} Python files", flush=True)
    
    counter += 1
    time.sleep(2)