# ticket.py
from playwright.sync_api import sync_playwright
import time

# 台鐵官網用「臺」不是「台」
NAME_MAP = {
    "台北": "臺北", "台中": "臺中", "台南": "臺南", "台東": "臺東",
}

def to_tra_name(name: str) -> str:
    return NAME_MAP.get(name, name)

def round_down_30(time_str: str) -> str:
    """把時間無條件捨去到最近的 :00 或 :30，例如 13:34 → 13:30"""
    h, m = time_str.split(":")
    m_int = 0 if int(m) < 30 else 30
    return f"{int(h):02d}:{m_int:02d}"

def round_up_30(time_str: str) -> str:
    """把時間無條件進位到最近的 :00 或 :30，例如 14:22 → 14:30"""
    h, m = time_str.split(":")
    h_int, m_int = int(h), int(m)
    if m_int == 0:
        pass
    elif m_int <= 30:
        m_int = 30
    else:
        m_int = 0
        h_int += 1
    return f"{h_int:02d}:{m_int:02d}"

def type_and_select_station(page, field_id: str, station_name: str):
    tra_name = to_tra_name(station_name)

    page.click(f"#{field_id}")
    page.wait_for_timeout(300)
    page.fill(f"#{field_id}", "")
    page.type(f"#{field_id}", tra_name, delay=150)
    page.wait_for_timeout(2000)

    # 直接用 JavaScript 找 visible 的 ui-menu-item 並點擊符合的
    clicked = page.evaluate(f"""
        (traName) => {{
            const items = document.querySelectorAll('.ui-menu-item');
            let firstMatch = null;
            for (const item of items) {{
                const dv = item.getAttribute('data-value') || '';
                const style = window.getComputedStyle(item.parentElement);
                // 確認父元素是可見的（display不是none）
                if (style.display === 'none') continue;
                const namePart = dv.includes('-') ? dv.split('-').slice(1).join('-') : dv;
                if (namePart === traName) {{
                    item.click();
                    return 'exact:' + dv;
                }}
                // 記錄第一個不含港/機場/高鐵的
                if (!firstMatch && !dv.includes('港') && !dv.includes('機場') && !dv.includes('高鐵')) {{
                    firstMatch = item;
                }}
            }}
            if (firstMatch) {{
                const dv = firstMatch.getAttribute('data-value');
                firstMatch.click();
                return 'fallback:' + dv;
            }}
            return 'not_found';
        }}
    """, tra_name)

    print(f"  [爬蟲] {field_id} JS點選結果：{clicked}")
    page.wait_for_timeout(800)

    # 點別的地方讓下拉確實關閉
    page.click("h1, .form_title, body", timeout=2000)
    page.wait_for_timeout(500)
    return "not_found" not in str(clicked)

def check_tickets(origin_name: str, dest_name: str, date: str, train_list: list[dict]) -> list[dict]:
    """
    爬取台鐵時刻查詢，確認班次票務狀態
    """
    ride_date  = date.replace("-", "/")

    # 計算查詢時間範圍
    # 最早班次出發時間往前30分，最晚班次出發時間往後30分
    # 查詢時間範圍：最早往前1小時，最晚往後1小時
    depart_times = [t["depart_time"] for t in train_list]
    earliest     = min(depart_times)
    latest       = max(depart_times)

    # 往前1小時
    h, m   = earliest.split(":")
    start_h = max(0, int(h) - 1)
    start_time = f"{start_h:02d}:00"

    # 往後1小時
    h, m   = latest.split(":")
    end_h  = min(23, int(h) + 1)
    end_time = f"{end_h:02d}:30"

    print(f"\n[爬蟲] 查詢時間範圍：{start_time} ~ {end_time}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        page    = browser.new_page()

        print(f"[爬蟲] 開啟台鐵時刻查詢...")
        page.goto("https://tip.railway.gov.tw/tra-tip-web/tip/tip001/tip112/querybytime")
        page.wait_for_load_state("networkidle")

        # ── 出發站 ────────────────────────────────────────
        print(f"[爬蟲] 填出發站：{origin_name}")
        type_and_select_station(page, "startStation", origin_name)

        # ── 抵達站 ────────────────────────────────────────
        print(f"[爬蟲] 填抵達站：{dest_name}")
        type_and_select_station(page, "endStation", dest_name)

        # ── 日期 ──────────────────────────────────────────
        print(f"[爬蟲] 填日期：{ride_date}")
        page.fill("#rideDate", ride_date)
        page.wait_for_timeout(300)

        # ── 時間範圍（select 下拉）────────────────────────
        print(f"[爬蟲] 選起始時間：{start_time}")
        page.select_option("#startTime", start_time)
        page.wait_for_timeout(300)

        print(f"[爬蟲] 選結束時間：{end_time}")
        page.select_option("#endTime", end_time)
        page.wait_for_timeout(300)

        # ── 選「出發時間」模式 ────────────────────────────
        page.check("#startOrEndTime1")
        page.wait_for_timeout(300)

        # ── 截圖確認填表 ──────────────────────────────────
        page.screenshot(path="screenshot_before_submit.png")
        print(f"[爬蟲] 填表截圖已存：screenshot_before_submit.png")

        # ── 查詢 ──────────────────────────────────────────
        print(f"[爬蟲] 送出查詢...")
        page.click("input[type=submit]")
        # ── 解析結果表格 ──────────────────────────────────
        page.wait_for_timeout(3000)

        trains_info = []
        rows = page.query_selector_all("table tr")

        for row in rows:
            cells = row.query_selector_all("td")
            if len(cells) < 5:
                continue

            # 只取第一個 td 的文字，判斷是否是主要資訊行
            # 主要行格式：「自強 118 ( 屏東 → 七堵 )」，不會有大量空白
            first_cell = cells[0].inner_text().strip()
            if not first_cell or len(first_cell) > 60:
                continue
            # 跳過表頭
            if "車種" in first_cell or "車次" in first_cell:
                continue
            # 跳過空白過多的行（詳細展開行）
            if first_cell.count("\n") > 3:
                continue

            depart_time = cells[1].inner_text().strip() if len(cells) > 1 else ""
            arrive_time = cells[2].inner_text().strip() if len(cells) > 2 else ""
            duration    = cells[3].inner_text().strip() if len(cells) > 3 else ""
            price_full  = cells[6].inner_text().strip() if len(cells) > 6 else ""

            # 時間格式驗證：必須是 HH:MM
            import re
            if not re.match(r'^\d{2}:\d{2}$', depart_time):
                continue
            if not re.match(r'^\d{2}:\d{2}$', arrive_time):
                continue

            row_html   = row.inner_html()
            is_full    = any(k in row_html for k in ["售完", "額滿", "無票", "候補"])
            has_ticket = "訂票" in row_html and not is_full

            trains_info.append({
                "info":        first_cell,
                "depart_time": depart_time,
                "arrive_time": arrive_time,
                "duration":    duration,
                "price":       price_full,
                "has_ticket":  has_ticket,
                "is_full":     is_full,
            })

        print(f"\n{'='*55}")
        print(f"{'台鐵官網查詢結果':^45}")
        print(f"{'='*55}")
        for i, t in enumerate(trains_info, 1):
            status = "🔴 售完/候補" if t["is_full"] else ("🟢 可訂票" if t["has_ticket"] else "🟡 自由座")
            print(f"\n  第{i}班")
            print(f"  {t['info']}")
            print(f"  出發 {t['depart_time']} → 抵達 {t['arrive_time']}（{t['duration']}）")
            print(f"  票價：{t['price']}　狀態：{status}")
        print(f"\n{'='*55}")

        return trains_info


if __name__ == "__main__":
    test_trains = [
        {"train_no": "1191", "train_type": "區間", "depart_time": "14:22", "arrive_time": "15:22"},
        {"train_no": "2213", "train_type": "區間", "depart_time": "13:59", "arrive_time": "15:05"},
        {"train_no": "1187", "train_type": "區間", "depart_time": "13:34", "arrive_time": "14:38"},
    ]
    check_tickets("台中", "桃園", "2026-05-30", test_trains)