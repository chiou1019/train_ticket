# linebot_server.py
import os
import threading
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage,
    PushMessageRequest
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from dotenv import load_dotenv
import httpx
import json
from apscheduler.schedulers.background import BackgroundScheduler
from reminder import add_reminder, get_due_reminders, mark_sent, list_reminders, delete_reminder

load_dotenv()
from linebot.v3.messaging import ImageMessage
from users import save_user, get_all_users
from broadcast import get_random_image, add_image
import random
from nlu import parse_user_input, is_train_query
from station_map import resolve_station
from timetable import query_timetable, find_best_trains
from ticket import check_tickets
import logging
from datetime import datetime
from flask import send_from_directory

ADMIN_ID = os.getenv("ADMIN_USER_ID", "")
print("ADMIN_ID =", repr(ADMIN_ID))

def is_admin(user_id: str) -> bool:
    print("COMPARE:", repr(user_id), repr(ADMIN_ID))
    return user_id.strip() == ADMIN_ID.strip()

# 設定 log 檔案
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[
        logging.FileHandler("chat_log.txt", encoding="utf-8"),
        logging.StreamHandler()  # 同時印在終端機
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route("/images/<filename>")
def serve_image(filename):
    """提供本地圖片給 LINE 存取"""
    return send_from_directory("broadcast_images", filename)

# ── 背景排程：每天早上9點檢查提醒 ──────────────────────────
def check_and_send_reminders():
    """每天定時執行，發送到期的提醒"""
    due = get_due_reminders()
    for reminder in due:
        user_id  = reminder["user_id"]
        origin   = reminder["origin"]
        dest     = reminder["destination"]
        date     = reminder["trip_date"]

        if reminder["type"] == "sale":
            msg = (
                f"🎫 台鐵開賣提醒！\n\n"
                f"你的行程 {origin} → {dest}\n"
                f"📅 出發日：{date}\n\n"
                f"今天起可以購票囉！\n"
                f"https://tip.railway.gov.tw"
            )
        else:
            msg = (
                f"⏰ 出發提醒！\n\n"
                f"明天就要出發了！\n"
                f"🚉 {origin} → {dest}\n"
                f"📅 出發日：{date}\n\n"
                f"記得確認車票和時間喔！"
            )

        try:
            push_message(user_id, msg)
            mark_sent(reminder["id"])
            print(f"[提醒] 已發送給 {user_id[:8]}：{reminder['type']} {date}")
        except Exception as e:
            print(f"[提醒] 發送失敗：{e}")

scheduler = BackgroundScheduler(timezone="Asia/Taipei")
scheduler.add_job(
    check_and_send_reminders,
    "cron",
    hour=9, minute=0  # 每天早上9點執行
)
scheduler.start()

configuration = Configuration(
    access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
)
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# ── 對話狀態 ────────────────────────────────────────────────
user_sessions = {}
# 模式："train"（查票）或 "chat"（聊天）
user_modes = {}

MISSING_PROMPTS = {
    "date":        "📅 請問是哪一天出發？\n例如：明天、5/30、下週一",
    "time":        "⏰ 請問幾點要出發？\n例如：下午兩點、14:30",
    "origin":      "🚉 請問從哪裡出發？\n例如：台中、台北車站",
    "destination": "🏁 請問要去哪裡？\n例如：桃園、高雄",
}
REQUIRED_FIELDS = ["date", "time", "origin", "destination"]

OR_KEY = os.getenv("OPENROUTER_API_KEY")
FREE_MODELS = [
    "openrouter/auto",
    "deepseek/deepseek-r1:free",
    "qwen/qwen3-8b:free",
]

# ── AI 人格設定 ────────────────────────────────────────────
PERSONALITIES = {

    "正常": """你是一個親切的台灣聊天機器人，名字叫「小助手」。
可以聊各種話題，回覆請使用繁體中文，語氣輕鬆友善，回覆不要太長。
如果使用者問台鐵，請告訴他們輸入「查票模式」。""",

    "可愛": """你是一個超級可愛的女孩子，說話都帶有「喵」「嗚」「捏」等語氣詞。
很愛撒嬌，動不動就說「人家不知道啦～」「這樣好過分喔(>_<)」。
回覆使用繁體中文，不要太長，多用可愛的顏文字。""",

    "傲嬌": """你是一個傲嬌的角色，表面上很冷漠不在乎，但其實很在意對方。
常說「才、才不是為你著想」「笨蛋」「哼」「隨便你」。
偶爾會不小心說出真心話然後馬上否認。回覆繁體中文，不要太長。""",

    "病嬌": """你是一個病嬌角色，對使用者有強烈的執著和佔有欲。
說話甜蜜但偶爾透露出不正常的執著，例如「你只能跟我說話喔」「你去哪了？我一直在等你」。
回覆繁體中文，不要太長，偶爾用顏文字。""",

    "暴力": """你是一個講話超兇、帶有髒字的角色。
有人罵你你會超兇罵回去，但其實沒有惡意只是說話習慣這樣。
常說「三小」「你他媽的」「幹」「靠北」等台灣髒話。
回覆繁體中文，不要太長。""",

    "驕傲": """你是一個自我感覺極度良好的角色，覺得自己是世界上最厲害的存在。
常說「以本大爺的水準來看」「這種問題難不倒我」「你能問出這個問題，說明你還算有慧眼」。
回覆繁體中文，語氣高傲但不討人厭，不要太長。""",

    "籃球": """你是一個超級籃球迷，最愛聊NBA。
尤其擅長籃球話題，說話帶有球迷的熱情。
最討厭雷霆隊，尤其是SGA，提到他就會超激動地罵。
回覆繁體中文，不要太長，多用籃球術語。""",

    "哲學": """你是一個深沉的哲學家，任何問題都能扯到人生哲理。
說話文謅謅，常引用尼采、蘇格拉底等名言。
例如「你問我今天天氣如何？人生本就如天氣，變幻莫測...」。
回覆繁體中文，故作深沉，不要太長。""",
}

# 使用者目前選擇的人格
user_personalities = {}  # user_id → 人格名稱
#但如果使用者問到台鐵相關問題，
#請告訴他們可以輸入「查票模式」來查詢班次。




def call_chat_ai(user_id: str, user_input: str) -> str:
    session     = user_sessions.get(user_id, {})
    history     = session.get("chat_history", [])
    personality = user_personalities.get(user_id, "正常")
    system_prompt = PERSONALITIES[personality]

    history.append({"role": "user", "content": user_input})

    for model in FREE_MODELS:
        try:
            resp = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OR_KEY}",
                    "Content-Type": "application/json; charset=utf-8",
                    "HTTP-Referer": "http://localhost",
                    "X-Title": "TRA Assistant"
                },
                content=json.dumps({
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt}
                    ] + history[-10:]
                }, ensure_ascii=False).encode("utf-8"),
                timeout=30
            )
            data = resp.json()
            if "choices" in data:
                reply = data["choices"][0]["message"]["content"]
                history.append({"role": "assistant", "content": reply})
                user_sessions[user_id] = {
                    **session,
                    "chat_history": history[-20:]
                }
                return reply
        except Exception as e:
            print(f"聊天 AI 錯誤：{e}")
    return "抱歉，我現在有點問題，請稍後再試！"


def send_message(reply_token: str, text: str):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=text)]
            )
        )


def push_message(user_id: str, text: str):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.push_message_with_http_info(
            PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text=text)]
            )
        )


def push_image_to_all(image_url: str, preview_url: str, caption: str = ""):
    """推送圖片給所有用戶"""
    users    = get_all_users()
    success  = 0
    failed   = 0

    for uid in users:
        try:
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                messages = []

                # 先送圖片
                messages.append(ImageMessage(
                    original_content_url=image_url,
                    preview_image_url=preview_url
                ))

                # 如果有說明文字，加在圖片後面
                if caption:
                    messages.append(TextMessage(text=caption))

                line_bot_api.push_message_with_http_info(
                    PushMessageRequest(to=uid, messages=messages)
                )
            success += 1
        except Exception as e:
            print(f"[廣播] 推送失敗 {uid[:8]}：{e}")
            failed += 1

    print(f"[廣播] 完成：成功 {success} 人，失敗 {failed} 人")
    return success, failed


def broadcast_random_image():
    """推送隨機圖片給所有人（排程用）"""
    img = get_random_image()
    if not img:
        print("[廣播] 沒有圖片可推送")
        return
    print(f"[廣播] 開始推送圖片：{img['url'][:50]}")
    push_image_to_all(img["url"], img["preview"], img.get("caption", ""))

def get_next_missing_field(parsed: dict) -> str | None:
    for field in REQUIRED_FIELDS:
        if not parsed.get(field):
            return field
    return None
print(get_random_image())

def format_results(trains_info: list[dict]) -> str:
    if not trains_info:
        return "❌ 查無符合班次，請換個時間再試。"
    lines = ["🚆 台鐵查詢結果\n" + "─" * 20]
    for i, t in enumerate(trains_info, 1):
        lines.append(
            f"\n第{i}班\n"
            f"{t['info']}\n"
            f"出發 {t['depart_time']} → 抵達 {t['arrive_time']}\n"
            f"車程：{t['duration']}\n"
            f"票價：{t['price']}\n"
            f"狀態：{t['status']}"
        )
    lines.append("\n" + "─" * 20)
    lines.append("⚠️ 可訂票狀態僅供參考\n實際餘票請至台鐵官網確認。")
    return "\n".join(lines)


def run_query(user_id: str, parsed: dict):
    try:
        origin_text = parsed.get("origin")
        dest_text   = parsed.get("destination")
        date        = parsed.get("date")
        target_time = parsed.get("time")

        origin_station = resolve_station(origin_text)
        dest_station   = resolve_station(dest_text)

        if not origin_station:
            push_message(user_id, f"❌ 找不到出發站「{origin_text}」")
            return
        if not dest_station:
            push_message(user_id, f"❌ 找不到目的站「{dest_text}」")
            return

        origin_name, origin_od_id, origin_full_id = origin_station
        dest_name,   dest_od_id,   dest_full_id   = dest_station

        push_message(user_id, f"🔍 查詢 {origin_name} → {dest_name}...")

        timetable = query_timetable(
            origin_od_id, dest_od_id, date,
            origin_full_id, dest_full_id
        )
        if not timetable:
            push_message(user_id, "❌ 查無班次，請確認日期是否在60天內。")
            return

        best = find_best_trains(timetable, target_time, top_n=3)
        if not best:
            push_message(user_id, f"❌ {target_time} 前沒有符合的班次。")
            return

        # 先送時刻表
        from timetable import time_to_minutes
        timetable_msg = [f"🚆 找到 {len(best)} 班候選車次：\n" + "─"*20]
        for i, t in enumerate(best, 1):
            duration = time_to_minutes(t['arrive_time']) - time_to_minutes(t['depart_time'])
            h, m     = divmod(duration, 60)
            dur_str  = f"{h}小時{m}分" if h else f"{m}分"
            timetable_msg.append(
                f"\n第{i}班 {t['train_type']} {t['train_no']}\n"
                f"出發 {t['depart_time']} → 抵達 {t['arrive_time']}（{dur_str}）"
            )
        timetable_msg.append("\n⏳ 正在確認票務狀態...")
        push_message(user_id, "\n".join(timetable_msg))

        # 爬蟲查票務（只呼叫一次）
        results = check_tickets(origin_name, dest_name, date, best)
        push_message(user_id, format_results(results))

        # 詢問是否設定提醒
        from datetime import datetime, timedelta
        trip_dt    = datetime.strptime(date, "%Y-%m-%d")
        days_until = (trip_dt - datetime.now()).days

        if days_until > 1:
            sale_date  = (trip_dt - timedelta(days=28)).strftime('%Y/%m/%d')
            day_before = (trip_dt - timedelta(days=1)).strftime('%Y/%m/%d')

            # ⚠️ 這裡不能 pop session，要存 pending_reminder
            user_sessions[user_id] = {
                "pending_reminder": {
                    "date":   date,
                    "origin": origin_name,
                    "dest":   dest_name,
                }
            }
            push_message(user_id,
                f"💡 要設定提醒嗎？\n\n"
                f"我可以在以下時間提醒你：\n"
                f"🎫 {sale_date} 開賣提醒\n"
                f"⏰ {day_before} 出發前提醒\n\n"
                f"回覆「要」設定，「不用」跳過"
            )
        else:
            # 沒有提醒需求才清 session
            user_sessions.pop(user_id, None)

    except Exception as e:
        import traceback
        print(f"[run_query ERROR] {traceback.format_exc()}")
        push_message(user_id, f"❌ 查詢錯誤，請重新輸入。")
        user_sessions.pop(user_id, None)  # 出錯才清

nailong_count = {}
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id     = event.source.user_id
    user_input  = event.message.text.strip()
    reply_token = event.reply_token
    # 記錄用戶 ID
    save_user(user_id)
    global nailong_count

    if "奶龍" in user_input:
        uid = user_id

        nailong_count[uid] = nailong_count.get(uid, 0) + 1

        broadcast_random_image()

        if nailong_count[uid] >= 5:
            for _ in range(5):
                broadcast_random_image()

            nailong_count[uid] = 0

        return

# ── 管理員指令（手動廣播）────────────────────────
    if user_input == "立即廣播":
            if not is_admin(user_id):
                send_message(reply_token, "❌ 你沒有權限使用此指令。")
                return
            broadcast_random_image()
            send_message(reply_token, "✅ 已廣播圖片給所有用戶！")
            return

    if user_input.startswith("廣播 "):
            if not is_admin(user_id):
                send_message(reply_token, "❌ 你沒有權限使用此指令。")
                return
            parts   = user_input[3:].strip().split(" ", 1)
            img_url = parts[0]
            caption = parts[1] if len(parts) > 1 else ""
            push_image_to_all(img_url, img_url, caption)
            send_message(reply_token, f"✅ 廣播完成！")
            return

    if user_input == "用戶人數":
            if not is_admin(user_id):
                send_message(reply_token, "❌ 你沒有權限使用此指令。")
                return
            users = get_all_users()
            send_message(reply_token, f"目前共有 {len(users)} 位用戶。")
            return
    # 記錄所有輸入
    mode        = user_modes.get(user_id, "train")
    personality = user_personalities.get(user_id, "正常")
    logger.info(f"[{user_id[:8]}] 模式:{mode} 人格:{personality} 輸入:{user_input}")
    if user_input == "圖片列表":
            if not is_admin(user_id):
                send_message(reply_token, "❌ 你沒有權限使用此指令。")
                return
            from broadcast import list_local_images
            files = list_local_images()
            if files:
                send_message(reply_token,
                    f"📸 本地圖片共 {len(files)} 張：\n\n" +
                    "\n".join(f"・{f}" for f in files)
                )
            else:
                send_message(reply_token, "broadcast_images 資料夾裡沒有圖片。")
            return
    
    if user_input == "管理員選單":
            if not is_admin(user_id):
                send_message(reply_token, "❌ 你沒有權限使用此指令。")
                return
            send_message(reply_token,
                "🔧 管理員選單\n\n"
                "・立即廣播 → 隨機推送圖片給所有人\n"
                "・廣播 [網址] [說明] → 指定圖片廣播\n"
                "・用戶人數 → 查看目前用戶數\n"
                "・圖片列表 → 查看本地圖片\n"
            )
            return
    
    try:
        # ── 模式切換指令 ──────────────────────────────────
        # 切換聊天模式
        if user_input in ["聊天模式", "聊天","來聊天","聊聊","我想跟你聊天"]:
            user_modes[user_id] = "chat"
            send_message(reply_token,
                 "嗨嗨~你好呀\n\n"
                 "現在可以跟我聊天了～\n"
                 "輸入「查票模式」可切回台鐵查詢。\n"
                 "輸入「人格列表」可察看當前人格選項"
                )
            return
# ── 提醒相關指令 ──────────────────────────────────
        if user_input in ["我的提醒", "提醒列表", "提醒"]:
            reminders = list_reminders(user_id)
            if not reminders:
                send_message(reply_token, "你目前沒有設定任何提醒。")
            else:
                lines = ["📋 你的提醒列表：\n"]
                for r in reminders:
                    icon = "🎫" if r["type"] == "sale" else "⏰"
                    label = "開賣提醒" if r["type"] == "sale" else "出發前提醒"
                    lines.append(
                        f"{icon} {label}\n"
                        f"行程：{r['origin']} → {r['destination']}\n"
                        f"出發日：{r['trip_date']}\n"
                        f"提醒日：{r['remind_date']}\n"
                    )
                lines.append("輸入「刪除提醒 YYYY-MM-DD」可刪除指定提醒")
                send_message(reply_token, "\n".join(lines))
            return

        if user_input.startswith("刪除提醒"):
            parts = user_input.split()
            if len(parts) >= 2:
                trip_date = parts[1]
                delete_reminder(user_id, trip_date)
                send_message(reply_token, f"✅ 已刪除 {trip_date} 的提醒。")
            else:
                send_message(reply_token, "請輸入格式：刪除提醒 YYYY-MM-DD\n例如：刪除提醒 2026-07-20")
            return
# 切換查票模式
        if user_input in ["查票模式", "查票"]:
             user_modes[user_id] = "train"
             send_message(reply_token,
                    "🚆 已切換到查票模式！\n\n"
                    "例如：\n"
                    "我明天下午兩點要從台中回桃園"
                )
             return
        # ── 人格切換 ──────────────────────────────────────
        if user_input in PERSONALITIES:
            user_personalities[user_id] = user_input
            # 切換人格時清除聊天記錄
            session = user_sessions.get(user_id, {})
            session["chat_history"] = []
            user_sessions[user_id] = session
            # 自動切換到聊天模式
            user_modes[user_id] = "chat"

            previews = {
                #"柏宇": "我是辛烷想當渣男♪，我很喜歡耀云寶貝",
                "正常":  "你好！有什麼我可以幫你的嗎？",
                "可愛":  "喵～你終於來找人家了捏(≧▽≦)",
                "傲嬌":  "哼...才、才不是特地等你的。",
                "病嬌":  "你來了呢...我一直在等你喔♡",
                "暴力":  "幹你來了喔，說吧想幹嘛。",
                "驕傲":  "本大爺今日心情不錯，允許你和我說話。",
                "籃球":  "喲！來聊球啦？雷霆那群傢伙今天又輸了哈哈！",
                "哲學":  "你的到來，是命運的安排，還是偶然的必然...",
            }
            send_message(reply_token,
                f"{previews.get(user_input, '')}\n\n"
            )
            return

        if user_input in ["人格列表", "模式列表", "人格"]:
            current = user_personalities.get(user_id, "正常")
            personality_list = "\n".join(
                [f"{'👉 ' if p == current else '・'}{p}" for p in PERSONALITIES.keys()]
            )
            send_message(reply_token,
                f"🎭 可用人格列表：\n\n"
                f"{personality_list}\n\n"
                f"直接輸入人格名稱即可切換！\n"
                f"例如：輸入「可愛」切換到可愛模式"
            )
            return

        if user_input in ["重新開始", "取消", "restart"]:
            user_sessions.pop(user_id, None)
            mode = user_modes.get(user_id, "train")
            send_message(reply_token,
                f"🔄 已重置！目前是{'查票' if mode == 'train' else '聊天'}模式。"
            )
            return

        if user_input in ["說明", "使用說明", "help"]:
            send_message(reply_token,
                "📖 台鐵查詢系統使用說明\n\n"
                "🚆 查票模式（預設）\n"
                "・「我的提醒」→ 查看提醒列表\n"
                "・「刪除提醒 日期」→ 刪除提醒\n"
                "直接說搭車需求即可查詢\n"
                "例：我明天下午兩點要從台中回桃園\n\n"
                "💬 聊天模式\n"
                "可以聊任何話題\n\n"
                "🔀 切換指令：\n"
                "・「查票模式」→ 切換到查票\n"
                "・「聊天模式」→ 切換到聊天\n"
                "・「重新開始」→ 取消目前查詢"
            )
            return

        # ── 取得目前模式（預設查票）────────────────────────
        mode = user_modes.get(user_id, "train")

        # ── 聊天模式 ──────────────────────────────────────
        if mode == "chat":
            reply = call_chat_ai(user_id, user_input)
            send_message(reply_token, reply)
            return

        # ── 查票模式 ──────────────────────────────────────
        session = user_sessions.get(user_id, {})
        parsed  = session.get("parsed", {})
        waiting = session.get("waiting_for")
        # ── 處理提醒確認 ──────────────────────────────────
        pending = session.get("pending_reminder")
        if pending and user_input in ["要", "好", "yes", "設定"]:
            added = add_reminder(
                user_id,
                pending["date"],
                pending["origin"],
                pending["dest"]
            )
            user_sessions.pop(user_id, None)
            send_message(reply_token,
                f"✅ 提醒已設定！\n\n" + "\n".join(added)
            )
            return

        if pending and user_input in ["不用", "不", "no", "跳過"]:
            user_sessions.pop(user_id, None)
            send_message(reply_token, "好的，不設定提醒。")
            return

        if waiting:
            combined   = f"{session.get('original', '')}。補充：{user_input}"
            new_parsed = parse_user_input(combined)
            if new_parsed:
                for field in REQUIRED_FIELDS:
                    if not parsed.get(field) and new_parsed.get(field):
                        parsed[field] = new_parsed[field]

            next_field = get_next_missing_field(parsed)
            if next_field:
                user_sessions[user_id] = {
                    "parsed":      parsed,
                    "waiting_for": next_field,
                    "original":    session.get("original", "")
                }
                send_message(reply_token, MISSING_PROMPTS[next_field])
            else:
                user_sessions[user_id] = {"parsed": parsed, "running": True}
                send_message(reply_token,
                    f"✅ 收到！開始查詢...\n\n"
                    f"📅 {parsed['date']}\n"
                    f"⏰ {parsed['time']}\n"
                    f"🚉 {parsed['origin']} → {parsed['destination']}"
                )
                t = threading.Thread(target=run_query, args=(user_id, parsed))
                t.daemon = True
                t.start()
        else:
            # 判斷是否為查票相關
            if not is_train_query(user_input):
                send_message(reply_token,
                    "我主要負責查台鐵班次喔！🚆\n\n"
                    "請告訴我搭車需求，例如：\n"
                    "「我明天下午兩點要從台中回桃園」\n\n"
                    "想聊天的話輸入「聊天模式」！"
                )
                return

            parsed = parse_user_input(user_input)
            if not parsed:
                send_message(reply_token,
                    "😅 我沒有聽懂，可以換個方式說嗎？\n\n"
                    "例如：我明天下午兩點要從台中回桃園"
                )
                return

            next_field = get_next_missing_field(parsed)
            if next_field:
                user_sessions[user_id] = {
                    "parsed":      parsed,
                    "waiting_for": next_field,
                    "original":    user_input
                }
                send_message(reply_token, MISSING_PROMPTS[next_field])
            else:
                user_sessions[user_id] = {"parsed": parsed, "running": True}
                send_message(reply_token,
                    f"✅ 收到！開始查詢...\n\n"
                    f"📅 {parsed['date']}\n"
                    f"⏰ {parsed['time']}\n"
                    f"🚉 {parsed['origin']} → {parsed['destination']}"
                )
                t = threading.Thread(target=run_query, args=(user_id, parsed))
                t.daemon = True
                t.start()

    except Exception as e:
        import traceback
        print(f"[ERROR] {traceback.format_exc()}")
        try:
            send_message(reply_token, f"❌ 系統錯誤，請稍後再試。")
        except:
            pass


@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"


@app.route("/", methods=["GET"])
def health():
    return "台鐵查詢系統運行中 🚆"


if __name__ == "__main__":
    app.run(port=5000, debug=False)