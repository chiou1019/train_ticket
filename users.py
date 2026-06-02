# users.py
import json
import os

USERS_FILE = "users.json"

def load_users() -> list[str]:
    if not os.path.exists(USERS_FILE):
        return []
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_user(user_id: str):
    """新用戶加入時儲存"""
    users = load_users()
    if user_id not in users:
        users.append(user_id)
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
        print(f"[用戶] 新增：{user_id[:8]}")

def get_all_users() -> list[str]:
    return load_users()