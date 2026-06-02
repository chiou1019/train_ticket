# debug_soldout.py
from playwright.sync_api import sync_playwright
import time
import re

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=300)
    page = browser.new_page()

    page.goto("https://tip.railway.gov.tw/tra-tip-web/tip/tip001/tip112/querybytime")
    page.wait_for_load_state("networkidle")

    # 出發站：桃園
    page.click("#startStation")
    page.type("#startStation", "桃園", delay=150)
    page.wait_for_timeout(1500)
    page.evaluate("""() => {
        const items = document.querySelectorAll('.ui-menu-item');
        for (const item of items) {
            if (item.getAttribute('data-value') === '1080-桃園') {
                item.click(); return;
            }
        }
    }""")
    page.wait_for_timeout(800)

    # 抵達站：台中
    page.click("#endStation")
    page.type("#endStation", "臺中", delay=150)
    page.wait_for_timeout(1500)
    page.evaluate("""() => {
        const items = document.querySelectorAll('.ui-menu-item');
        for (const item of items) {
            if (item.getAttribute('data-value') === '3300-臺中') {
                item.click(); return;
            }
        }
    }""")
    page.wait_for_timeout(800)

    page.fill("#rideDate", "2026/05/24")
    page.select_option("#startTime", "17:00")
    page.select_option("#endTime", "19:30")
    page.check("#startOrEndTime1")
    page.click("input[type=submit]")
    page.wait_for_timeout(3000)

    # 印出所有班次最後一格 HTML
    rows = page.query_selector_all("table tr")
    for row in rows:
        cells = row.query_selector_all("td")
        if len(cells) < 5:
            continue
        first = cells[0].inner_text().strip()
        if not re.search(r'(自強|莒光|區間|普悠瑪|太魯閣)', first):
            continue
        if first.count("\n") > 3:
            continue
        print(f"\n班次：{first[:40]}")
        print(f"最後一格文字：{cells[-1].inner_text().strip()[:80]}")
        print(f"最後一格HTML：{cells[-1].inner_html()[:500]}")

    time.sleep(20)
    browser.close()