import itertools

def generate_aliases(email: str, limit=100):
    name, domain = email.split("@")
    name = name.replace(".", "")
    out = set()

    out.add(name.lower()+"@"+domain)
    out.add(name.upper()+"@"+domain)

    for r in range(1, min(len(name), 7)):
        for c in itertools.combinations(range(1, len(name)), r):
            s = name
            o = 0
            for i in c:
                s = s[:i+o] + "." + s[i+o:]
                o += 1
            out.add(s + "@" + domain)
            if len(out) >= limit:
                break
    return list(out)