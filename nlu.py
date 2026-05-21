import os
import json
import httpx
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

or_key = os.getenv("OPENROUTER_API_KEY")

FREE_MODELS = [
    "openrouter/auto",
    "deepseek/deepseek-r1:free",
    "qwen/qwen3-8b:free",
    "arcee-ai/trinity-large-preview:free",
]

# 今天的年份，讓 AI 知道現在是哪一年
TODAY = datetime.now().strftime("%Y-%m-%d")

SYSTEM_PROMPT = f"""你是一個台鐵查詢助手的資料解析器。
今天日期是 {TODAY}。

使用者會用自然語言描述搭車需求，你必須解析出以下四個欄位並以 JSON 格式回傳：
- date: 出發日期，格式 YYYY-MM-DD
- time: 最晚到達目的地的時間（或搭車時間），格式 HH:MM（24小時制）
- origin: 出發地（保留使用者原始說法）
- destination: 目的地（保留使用者原始說法）

規則：
1. 只輸出 JSON，不要任何說明文字、不要 markdown 格式
2. 如果使用者說「要回去」某地，那個地方是 destination
3. 如果使用者說「我在」某地，那個地方是 origin  
4. 如果年份不明，預設使用今年
5. 如果時間是「2:30」沒有說上午下午，根據上下文判斷（回家通常是下午）
6. 如果無法解析某欄位，該欄位填 null

範例輸入：我5/30，2:30要回去桃園市桃園區，我人在台中市中區
範例輸出：{{"date":"2025-05-30","time":"14:30","origin":"台中市中區","destination":"桃園市桃園區"}}
"""

def call_ai(user_input: str) -> str | None:
    """呼叫 AI，回傳原始文字"""
    for model in FREE_MODELS:
        try:
            resp = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {or_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost",
                    "X-Title": "TRA Assistant"
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_input}
                    ]
                },
                timeout=30
            )
            data = resp.json()
            if "choices" in data:
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"  模型 {model} 發生錯誤：{e}")
    return None

def parse_user_input(user_input: str) -> dict | None:
    """
    解析使用者輸入，回傳結構化資料
    成功回傳 dict，失敗回傳 None
    """
    print(f"\n[NLU] 解析輸入：{user_input}")
    
    raw = call_ai(user_input)
    if not raw:
        print("[NLU] AI 呼叫失敗")
        return None
    
    # 清理 AI 可能多輸出的 markdown 格式
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1])  # 去掉首尾的 ``` 行
    
    try:
        result = json.loads(cleaned)
        print(f"[NLU] 解析結果：{result}")
        return result
    except json.JSONDecodeError:
        print(f"[NLU] JSON 解析失敗，AI 原始回應：{raw}")
        return None


# 測試用
if __name__ == "__main__":
    test_cases = [
        "我5/30，2:30要回去桃園市桃園區，我人在台中市中區",
        "明天早上10點要從台北車站去高雄",
        "下週五下午三點半，從新竹出發去台南",
    ]
    
    for test in test_cases:
        print("\n" + "="*50)
        result = parse_user_input(test)
        if result:
            print(f"  日期：{result.get('date')}")
            print(f"  時間：{result.get('time')}")
            print(f"  出發地：{result.get('origin')}")
            print(f"  目的地：{result.get('destination')}")
        else:
            print("  解析失敗")