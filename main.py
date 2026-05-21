# main.py
import time
from nlu import parse_user_input
from station_map import resolve_station
from timetable import query_timetable, find_best_trains
from ticket import check_tickets

def run(user_input: str):
    print("\n" + "="*55)
    print(f"使用者輸入：{user_input}")
    print("="*55)

    # ── Step 1：AI 解析自然語言 ──────────────────────────
    parsed = parse_user_input(user_input)
    if not parsed:
        print("❌ 無法解析輸入，請重新描述。")
        return

    date        = parsed.get("date")
    target_time = parsed.get("time")
    origin_text = parsed.get("origin")
    dest_text   = parsed.get("destination")

    if not all([date, target_time, origin_text, dest_text]):
        print(f"❌ 資訊不完整：{parsed}")
        return

    print(f"\n📅 日期：{date}")
    print(f"⏰ 目標時間：{target_time}")
    print(f"🚉 出發地：{origin_text}")
    print(f"🏁 目的地：{dest_text}")

    # ── Step 2：地名 → 站名代碼 ──────────────────────────
    origin_station = resolve_station(origin_text)
    dest_station   = resolve_station(dest_text)

    if not origin_station:
        print(f"❌ 找不到出發站：{origin_text}")
        return
    if not dest_station:
        print(f"❌ 找不到目的站：{dest_text}")
        return

    origin_name, origin_od_id, origin_full_id = origin_station
    dest_name,   dest_od_id,   dest_full_id   = dest_station

    print(f"\n🗺  出發站：{origin_name}（ID：{origin_od_id}）")
    print(f"🗺  目的站：{dest_name}（ID：{dest_od_id}）")

    # ── Step 3：TDX 時刻表查詢（找目標時間前三班）────────
    print(f"\n🔍 查詢 {date} {target_time} 前，{origin_name} → {dest_name} 的班次...")
    timetable = query_timetable(origin_od_id, dest_od_id, date, origin_full_id, dest_full_id)

    if not timetable:
        print("❌ 查無班次，請確認日期是否在60天內。")
        return

    best = find_best_trains(timetable, target_time, top_n=3)
    if not best:
        print(f"❌ {target_time} 前沒有符合的班次。")
        return

    print(f"✅ TDX 找到 {len(best)} 班候選車次，時間範圍：{best[-1]['depart_time']} ~ {best[0]['depart_time']}")

    # ── Step 4：爬蟲查票務狀態 ───────────────────────────
    print(f"\n🕷  啟動爬蟲查詢票務狀態...")
    results = check_tickets(origin_name, dest_name, date, best)

    if not results:
        print("❌ 爬蟲查無結果。")


if __name__ == "__main__":
    print("=" * 55)
    print("🚆  台鐵 AI 查詢助手")
    print("=" * 55)
    print("範例：我5/30，2:30要回去桃園，我在台中")
    print("輸入 q 離開")
    print("=" * 55)

    while True:
        try:
            user_input = input("\n請輸入搭車需求：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再見！")
            break

        if not user_input:
            continue
        if user_input.lower() == "q":
            print("再見！")
            break

        run(user_input)
        time.sleep(2)