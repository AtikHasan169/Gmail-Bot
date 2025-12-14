from itertools import product

def generate(email, limit=500):
    local, domain = email.split("@", 1)

    chars = []
    for c in local:
        if c.isalpha():
            chars.append((c.lower(), c.upper()))
        else:
            chars.append((c,))

    result = []
    for combo in product(*chars):
        result.append("".join(combo) + "@" + domain)
        if len(result) >= limit:
            break

    return result