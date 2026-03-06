import time

def now() -> int:
    return int(time.time())

def ttl(days = 14) -> int:
    return now() + days * 86400
