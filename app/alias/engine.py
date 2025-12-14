def generate_aliases(email: str):
    """
    Generate uppercase / lowercase aliases only.
    Gmail ignores case, but services may not.
    """
    local, domain = email.split("@")

    variants = set()
    variants.add(f"{local.lower()}@{domain}")
    variants.add(f"{local.upper()}@{domain}")
    variants.add(f"{local.capitalize()}@{domain}")

    return sorted(list(variants))