# debug_form.py
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=400)
    page = browser.new_page()

    page.goto("https://tip.railway.gov.tw/tra-tip-web/tip/tip001/tip112/querybytime")
    page.wait_for_load_state("networkidle")

    # 1. 日期欄位完整 id
    date_input = page.query_selector("input.rideDate")
    if date_input:
        print("日期欄位：")
        print(f"  id='{date_input.get_attribute('id')}'")
        print(f"  name='{date_input.get_attribute('name')}'")
        print(f"  class='{date_input.get_attribute('class')}'")

    # 2. startTime select 的所有選項
    print("\nstartTime 選項（前10個）：")
    options = page.query_selector_all("#startTime option")
    for opt in options[:10]:
        print(f"  value='{opt.get_attribute('value')}' text='{opt.inner_text().strip()}'")

    # 3. endTime select 的所有選項
    print("\nendTime 選項（前10個）：")
    options2 = page.query_selector_all("#endTime option")
    for opt in options2[:10]:
        print(f"  value='{opt.get_attribute('value')}' text='{opt.inner_text().strip()}'")

    time.sleep(10)
    browser.close()