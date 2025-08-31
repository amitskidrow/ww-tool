import time
import math

def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

def is_prime(n):
    if n < 2:
        return False
    for i in range(2, int(math.sqrt(n)) + 1):
        if n % i == 0:
            return False
    return True

counter = 1
while True:
    fib = fibonacci(min(counter, 20))  # Limit to avoid long computation
    prime_status = "PRIME" if is_prime(counter) else "not prime"
    
    print(f"Number {counter}: Fibonacci({min(counter, 20)})={fib}, Status: {prime_status}", flush=True)
    counter += 1
    time.sleep(1.5)