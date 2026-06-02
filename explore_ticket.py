# explore_ticket.py
# 目的：用瀏覽器打開台鐵訂票網站，觀察票務查詢的流程和 HTML 結構

from playwright.sync_api import sync_playwright
import time

def explore():
    with sync_playwright() as p:
        # headless=False 代表開啟看得到的瀏覽器視窗，方便觀察
        browser = p.chromium.launch(headless=False, slow_mo=100)
        page = browser.new_page()

        print("開啟台鐵訂票網站...")
        page.goto("https://tip.railway.gov.tw/tra-tip-web/tip/tip001/tip112/querybytime")
        page.wait_for_load_state("networkidle")

        print("網頁標題：", page.title())
        print("目前網址：", page.url)

        # 截圖存下來，方便你看到網頁長什麼樣
        page.screenshot(path="screenshot_1_homepage.png")
        print("截圖已存：screenshot_1_homepage.png")

        # 印出頁面上所有 input 欄位
        inputs = page.query_selector_all("input")
        print(f"\n找到 {len(inputs)} 個 input 欄位：")
        for i, inp in enumerate(inputs):
            name        = inp.get_attribute("name") or ""
            id_attr     = inp.get_attribute("id") or ""
            placeholder = inp.get_attribute("placeholder") or ""
            input_type  = inp.get_attribute("type") or ""
            print(f"  [{i}] type={input_type:10s} id={id_attr:30s} name={name:20s} placeholder={placeholder}")

        # 印出所有按鈕
        buttons = page.query_selector_all("button")
        print(f"\n找到 {len(buttons)} 個按鈕：")
        for i, btn in enumerate(buttons):
            text = btn.inner_text().strip().replace("\n", " ")
            print(f"  [{i}] {text[:60]}")

        print("\n瀏覽器保持開啟10秒，你可以自己觀察...")
        time.sleep(10)
        browser.close()

if __name__ == "__main__":
    explore()