# debug_trainno.py
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=300)
    page = browser.new_page()

    # 直接用車次查詢頁面，輸入車次477查詢
    url = "https://tip.railway.gov.tw/tra-tip-web/tip/tip001/tip112/querybytrainno?rideDate=2026/05/24&trainNo=477"
    print(f"開啟：{url}")
    page.goto(url)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    print("標題：", page.title())
    page.screenshot(path="screenshot_trainno.png")
    print("截圖已存：screenshot_trainno.png")

    # 印出頁面文字
    body = page.inner_text("body")
    print("\n頁面文字：")
    print(body[:3000])

    time.sleep(20)
    browser.close()