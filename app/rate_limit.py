import time

_cache = {}

def allow(uid, limit=10, window=60):
    now = time.time()
    _cache.setdefault(uid, [])
    _cache[uid] = [t for t in _cache[uid] if now - t < window]
    if len(_cache[uid]) >= limit:
        return False
    _cache[uid].append(now)
    return True