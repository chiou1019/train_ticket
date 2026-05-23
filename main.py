# main.py
import time
from nlu import parse_user_input
from station_map import resolve_station
from timetable import query_timetable, find_best_trains
from ticket import check_tickets

# 每個欄位缺少時的提問
MISSING_PROMPTS = {
    "date":        "📅 請問是哪一天出發？（例如：明天、5/30、下週一）",
    "time":        "⏰ 請問幾點要出發（或抵達）？（例如：下午兩點、14:30）",
    "origin":      "🚉 請問從哪裡出發？（例如：台中、台北車站）",
    "destination": "🏁 請問要去哪裡？（例如：桃園、高雄）",
}

def ask_missing(field: str) -> str:
    """提示使用者補充缺少的欄位，回傳使用者輸入"""
    print(f"\n  ❓ {MISSING_PROMPTS[field]}")
    return input("  👉 ").strip()

def collect_info(initial_input: str) -> dict | None:
    """
    對話式收集搭車資訊。
    先解析初始輸入，缺什麼欄位就問什麼，不需要重打全部。
    """
    # 先解析初始輸入
    parsed = parse_user_input(initial_input)
    if not parsed:
        print("❌ 無法理解輸入，請重新描述。")
        return None

    # 逐一檢查必要欄位，缺少就補問
    required_fields = ["date", "time", "origin", "destination"]

    for field in required_fields:
        # 最多問3次
        attempts = 0
        while not parsed.get(field) and attempts < 3:
            attempts += 1
            supplement = ask_missing(field)
            if not supplement:
                continue

            # 把補充內容合併進去重新解析
            combined = f"{initial_input}。補充：{supplement}"
            new_parsed = parse_user_input(combined)
            if new_parsed and new_parsed.get(field):
                parsed[field] = new_parsed[field]
                # 順便更新其他可能一起補充的欄位
                for f in required_fields:
                    if not parsed.get(f) and new_parsed.get(f):
                        parsed[f] = new_parsed[f]

        if not parsed.get(field):
            print(f"❌ 無法取得{MISSING_PROMPTS[field][:6]}，取消查詢。")
            return None

    return parsed


def run(user_input: str):
    print("\n" + "="*55)
    print(f"使用者輸入：{user_input}")
    print("="*55)

    # ── Step 1：對話式收集資訊 ───────────────────────────
    parsed = collect_info(user_input)
    if not parsed:
        return

    date        = parsed.get("date")
    target_time = parsed.get("time")
    origin_text = parsed.get("origin")
    dest_text   = parsed.get("destination")

    print(f"\n✅ 收到完整資訊：")
    print(f"   📅 日期：{date}")
    print(f"   ⏰ 時間：{target_time}")
    print(f"   🚉 出發：{origin_text}")
    print(f"   🏁 目的：{dest_text}")

    # ── Step 2：地名 → 站名代碼 ──────────────────────────
    origin_station = resolve_station(origin_text)
    dest_station   = resolve_station(dest_text)

    if not origin_station:
        print(f"\n❌ 找不到出發站「{origin_text}」")
        print("   💡 提示：請輸入台鐵有停靠的站名，例如台中、桃園、台北")
        return
    if not dest_station:
        print(f"\n❌ 找不到目的站「{dest_text}」")
        print("   💡 提示：請輸入台鐵有停靠的站名，例如台中、桃園、台北")
        return

    origin_name, origin_od_id, origin_full_id = origin_station
    dest_name,   dest_od_id,   dest_full_id   = dest_station

    print(f"\n🗺  出發站：{origin_name}（ID：{origin_od_id}）")
    print(f"🗺  目的站：{dest_name}（ID：{dest_od_id}）")

    # ── Step 3：TDX 時刻表查詢 ───────────────────────────
    print(f"\n🔍 查詢 {date} {target_time} 前，{origin_name} → {dest_name} 的班次...")
    timetable = query_timetable(origin_od_id, dest_od_id, date, origin_full_id, dest_full_id)

    if not timetable:
        print("❌ 查無班次，請確認日期是否在60天內。")
        return

    best = find_best_trains(timetable, target_time, top_n=3)
    if not best:
        print(f"❌ {target_time} 前沒有符合的班次。")
        return

    print(f"✅ TDX 找到 {len(best)} 班候選車次")

    # ── Step 4：爬蟲查票務狀態 ───────────────────────────
    print(f"\n🕷  啟動爬蟲查詢票務狀態...")
    check_tickets(origin_name, dest_name, date, best)


if __name__ == "__main__":
    print("=" * 55)
    print(" 台鐵 AI 查詢助手")
    print("=" * 55)
    print("直接用自然語言描述你的需求！")
    print("範例：我明天下午兩點要從台中回桃園")
    print("輸入 q 離開")
    print("=" * 55)

    while True:
        try:
            user_input = input("\n🗣  請說：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再見！")
            break

        if not user_input:
            continue
        if user_input.lower() == "q":
            print("掰掰！下次見 👋")
            break

        run(user_input)
        time.sleep(2)