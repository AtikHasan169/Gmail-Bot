def is_admin(user_id: int, admins: list[int]) -> bool:
    return user_id in admins