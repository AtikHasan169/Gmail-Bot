import random, hashlib

def generate(email, mode="SMART", seed=None):
    name, domain = email.split("@")
    if seed:
        random.seed(seed)

    if mode == "HASHED":
        h = hashlib.md5(email.encode()).hexdigest()[:6]
        return f"{name}.{h}@{domain}"

    out = ""
    for c in name:
        out += c.upper() if random.random() > 0.5 else c.lower()
    return out + "@" + domain