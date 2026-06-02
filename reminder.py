# reminder.py
import json
import os
from datetime import datetime, timedelta

REMINDER_FILE = "reminders.json"

def load_reminders() -> list[dict]:
    if not os.path.exists(REMINDER_FILE):
        return []
    with open(REMINDER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_reminders(reminders: list[dict]):
    with open(REMINDER_FILE, "w", encoding="utf-8") as f:
        json.dump(reminders, f, ensure_ascii=False, indent=2)

def add_reminder(user_id: str, date: str, origin: str, destination: str):
    """
    新增提醒，自動計算兩個提醒時間：
    1. 開賣日（28天前）
    2. 前一天
    """
    reminders = load_reminders()
    trip_date = datetime.strptime(date, "%Y-%m-%d")

    # 開賣日提醒（28天前）
    sale_date = trip_date - timedelta(days=28)
    # 前一天提醒
    day_before = trip_date - timedelta(days=1)
    today      = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    added = []

    # 開賣日還沒過才加
    if sale_date.date() >= today.date():
        reminders.append({
            "id":          f"{user_id}_{date}_sale",
            "user_id":     user_id,
            "type":        "sale",
            "trip_date":   date,
            "remind_date": sale_date.strftime("%Y-%m-%d"),
            "origin":      origin,
            "destination": destination,
            "sent":        False,
        })
        added.append(f"🎫 開賣提醒：{sale_date.strftime('%Y/%m/%d')}")

    # 前一天提醒還沒過才加
    if day_before.date() >= today.date():
        reminders.append({
            "id":          f"{user_id}_{date}_before",
            "user_id":     user_id,
            "type":        "before",
            "trip_date":   date,
            "remind_date": day_before.strftime("%Y-%m-%d"),
            "origin":      origin,
            "destination": destination,
            "sent":        False,
        })
        added.append(f"⏰ 出發前提醒：{day_before.strftime('%Y/%m/%d')}")

    save_reminders(reminders)
    return added

def get_due_reminders() -> list[dict]:
    """取得今天該發送的提醒"""
    reminders = load_reminders()
    today     = datetime.now().strftime("%Y-%m-%d")
    due       = [r for r in reminders
                 if r["remind_date"] == today and not r["sent"]]
    return due

def mark_sent(reminder_id: str):
    """標記提醒已發送"""
    reminders = load_reminders()
    for r in reminders:
        if r["id"] == reminder_id:
            r["sent"] = True
    save_reminders(reminders)

def list_reminders(user_id: str) -> list[dict]:
    """列出某用戶的所有未發送提醒"""
    reminders = load_reminders()
    return [r for r in reminders
            if r["user_id"] == user_id and not r["sent"]]

def delete_reminder(user_id: str, trip_date: str):
    """刪除某用戶某日期的提醒"""
    reminders = load_reminders()
    reminders = [r for r in reminders
                 if not (r["user_id"] == user_id and r["trip_date"] == trip_date)]
    save_reminders(reminders)