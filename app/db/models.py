# app/db/models.py

import json
import os
from typing import List, Dict

DB_FILE = os.environ.get("DB_FILE", "/app/data/users.json")

os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)

def _load() -> List[Dict]:
    if not os.path.exists(DB_FILE):
        return []
    with open(DB_FILE, "r") as f:
        return json.load(f)

def _save(data: List[Dict]):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2)

def save_user(user: Dict):
    users = _load()
    users = [u for u in users if u["telegram_id"] != user["telegram_id"]]
    users.append(user)
    _save(users)

def all_users() -> List[Dict]:
    return _load()