import time
import datetime
import calendar

counter = 1
while True:
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    day_name = calendar.day_name[now.weekday()]
    month_name = calendar.month_name[now.month]
    
    print(f"⏰ Update #{counter} - {day_name}, {month_name} {now.day}, {now.year} at {now.strftime('%I:%M:%S %p')}", flush=True)
    counter += 1
    time.sleep(3)