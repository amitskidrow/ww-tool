import time
import random

# ANSI color codes
colors = {
    'red': '\033[91m',
    'green': '\033[92m',
    'yellow': '\033[93m',
    'blue': '\033[94m',
    'magenta': '\033[95m',
    'cyan': '\033[96m',
    'white': '\033[97m',
    'reset': '\033[0m'
}

color_names = list(colors.keys())[:-1]  # Exclude 'reset'

counter = 1
while True:
    color_name = random.choice(color_names)
    color_code = colors[color_name]
    reset_code = colors['reset']
    
    print(f"{color_code}🌈 Colorful message #{counter} in {color_name.upper()}! 🌈{reset_code}", flush=True)
    counter += 1
    time.sleep(1)