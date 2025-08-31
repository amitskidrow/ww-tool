import time
import os
import psutil
import platform

counter = 1
while True:
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    print(f"📊 System Info #{counter}:", flush=True)
    print(f"   CPU: {cpu_percent}% | RAM: {memory.percent}% | Disk: {disk.percent}%", flush=True)
    print(f"   Platform: {platform.system()} {platform.release()}", flush=True)
    print(f"   Load Average: {os.getloadavg()}", flush=True)
    print("   " + "="*50, flush=True)
    
    counter += 1
    time.sleep(5)