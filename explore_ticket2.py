# explore_ticket2.py
from playwright.sync_api import sync_playwright
import time

def explore():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=800)
        page = browser.new_page()

        print("開啟台鐵時刻查詢頁面...")
        page.goto("https://tip.railway.gov.tw/tra-tip-web/tip/tip001/tip112/querybytime")
        page.wait_for_load_state("networkidle")

        print("網頁標題：", page.title())
        page.screenshot(path="screenshot_querybytime.png")

        # 印出所有 input
        inputs = page.query_selector_all("input")
        print(f"\n找到 {len(inputs)} 個 input 欄位：")
        for i, inp in enumerate(inputs):
            id_attr     = inp.get_attribute("id") or ""
            input_type  = inp.get_attribute("type") or ""
            placeholder = inp.get_attribute("placeholder") or ""
            value       = inp.get_attribute("value") or ""
            print(f"  [{i}] type={input_type:10s} id={id_attr:30s} placeholder={placeholder} value={value}")

        # 印出按鈕
        buttons = page.query_selector_all("button")
        print(f"\n找到 {len(buttons)} 個按鈕：")
        for i, btn in enumerate(buttons[:20]):
            text = btn.inner_text().strip().replace("\n", " ")
            print(f"  [{i}] {text[:60]}")

        # 有沒有 reCAPTCHA
        recaptcha = page.query_selector("[data-sitekey], .g-recaptcha, #g-recaptcha")
        print(f"\nreCAPTCHA：{'有！' if recaptcha else '沒有！可以直接爬'}")

        time.sleep(10)
        browser.close()

if __name__ == "__main__":
    explore()