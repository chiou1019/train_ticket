# debug_sold_out.py
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=300)
    page = browser.new_page()

    page.goto("https://tip.railway.gov.tw/tra-tip-web/tip/tip001/tip112/querybytime")
    page.wait_for_load_state("networkidle")

    page.click("#startStation")
    page.type("#startStation", "臺北", delay=150)
    page.wait_for_timeout(1500)
    page.evaluate("""() => {
        const items = document.querySelectorAll('.ui-menu-item');
        for (const item of items) {
            if (item.getAttribute('data-value').includes('臺北') &&
                !item.getAttribute('data-value').includes('環島')) {
                item.click(); return;
            }
        }
    }""")
    page.wait_for_timeout(800)

    page.click("#endStation")
    page.type("#endStation", "高雄", delay=150)
    page.wait_for_timeout(1500)
    page.evaluate("""() => {
        const items = document.querySelectorAll('.ui-menu-item');
        for (const item of items) {
            if (item.getAttribute('data-value').includes('高雄')) {
                item.click(); return;
            }
        }
    }""")
    page.wait_for_timeout(800)

    # 用端午節假期，比較可能有售完的班次
    page.fill("#rideDate", "2026/05/31")
    page.select_option("#startTime", "08:00")
    page.select_option("#endTime", "12:00")
    page.check("#startOrEndTime1")
    page.click("input[type=submit]")
    page.wait_for_timeout(3000)

    # 印出每班車最後一格（票務狀態格）的完整 HTML
    rows = page.query_selector_all("table tr")
    print(f"共 {len(rows)} 行")
    for i, row in enumerate(rows):
        cells = row.query_selector_all("td")
        if len(cells) < 5:
            continue
        last_cell = cells[-1]
        last_html = last_cell.inner_html()
        last_text = last_cell.inner_text().strip()
        train_text = cells[0].inner_text().strip()[:30]
        print(f"\n班次：{train_text}")
        print(f"票務格文字：{last_text}")
        print(f"票務格HTML：{last_html[:300]}")

    time.sleep(30)
    browser.close()