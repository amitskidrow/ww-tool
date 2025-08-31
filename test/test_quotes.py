import time
import random

quotes = [
    "The only way to do great work is to love what you do. - Steve Jobs",
    "Life is what happens to you while you're busy making other plans. - John Lennon",
    "The future belongs to those who believe in the beauty of their dreams. - Eleanor Roosevelt",
    "It is during our darkest moments that we must focus to see the light. - Aristotle",
    "The way to get started is to quit talking and begin doing. - Walt Disney",
    "Don't let yesterday take up too much of today. - Will Rogers",
    "You learn more from failure than from success. - Unknown",
    "If you are working on something exciting that you really care about, you don't have to be pushed. - Steve Jobs"
]

counter = 1
while True:
    quote = random.choice(quotes)
    print(f"Quote #{counter}: {quote}", flush=True)
    counter += 1
    time.sleep(2)