#!/usr/bin/env python3
"""
Directory monitoring test - watches for changes in the current directory
This tests directory-level live reload functionality
"""

import time
import os
import glob
from pathlib import Path

def get_directory_info():
    """Get information about files in current directory"""
    current_dir = Path.cwd()
    py_files = list(current_dir.glob("*.py"))
    sh_files = list(current_dir.glob("*.sh"))
    
    return {
        'py_files': sorted([f.name for f in py_files]),
        'sh_files': sorted([f.name for f in sh_files]),
        'total_files': len(py_files) + len(sh_files)
    }

def main():
    print("📁 Directory Monitor Started")
    print("=" * 50)
    print(f"Monitoring: {Path.cwd()}")
    print("=" * 50)
    
    last_info = None
    counter = 1
    
    while True:
        current_info = get_directory_info()
        timestamp = time.strftime("%H:%M:%S")
        
        if current_info != last_info:
            print(f"\n🔄 [{timestamp}] DIRECTORY CHANGE DETECTED (scan #{counter})")
            print(f"   Total files: {current_info['total_files']}")
            print(f"   Python files ({len(current_info['py_files'])}):")
            for f in current_info['py_files']:
                print(f"     - {f}")
            print(f"   Shell files ({len(current_info['sh_files'])}):")
            for f in current_info['sh_files']:
                print(f"     - {f}")
            last_info = current_info
        else:
            print(f"[{timestamp}] Directory scan #{counter} - {current_info['total_files']} files (no changes)")
        
        counter += 1
        time.sleep(2)

if __name__ == "__main__":
    main()