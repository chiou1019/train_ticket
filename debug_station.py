# debug_station.py
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=600)
    page = browser.new_page()

    page.goto("https://tip.railway.gov.tw/tra-tip-web/tip/tip001/tip112/querybytime")
    page.wait_for_load_state("networkidle")

    # 用 type 模擬真人打字，而不是 fill（fill 是直接貼上，不觸發 autocomplete）
    page.click("#startStation")
    page.type("#startStation", "台中", delay=150)  # 模擬真人打字
    page.wait_for_timeout(1500)  # 等autocomplete出現

    page.screenshot(path="screenshot_autocomplete.png")

    # 印出所有可見的 li
    all_li = page.query_selector_all("li")
    print("可見的 li：")
    for li in all_li:
        try:
            if li.is_visible():
                text = li.inner_text().strip()
                cls  = li.get_attribute("class") or ""
                if text and len(text) < 20:
                    print(f"  class='{cls}' text='{text}'")
        except:
            pass

    # 也找找 ui-autocomplete 相關元素
    ac = page.query_selector(".ui-autocomplete")
    if ac:
        print("\nui-autocomplete HTML：")
        print(ac.inner_html()[:500])
    else:
        print("\n找不到 .ui-autocomplete")

    time.sleep(20)
    browser.close()