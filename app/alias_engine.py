def generate_aliases(email):
    local, domain = email.split("@")
    return [
        f"{local}+test@{domain}",
        f"{local.replace('.', '')}@{domain}",
        f"{local.upper()}@{domain}",
        f"{local.lower()}@{domain}",
    ]