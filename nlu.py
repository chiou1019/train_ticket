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

TODAY = datetime.now().strftime("%Y-%m-%d")

SYSTEM_PROMPT = f"""你是台鐵查詢助手的資料解析器。
今天日期是 {TODAY}。

你的任務有兩個：
1. 自動修正使用者的錯字和口語表達
2. 解析出搭車資訊

【常見錯字對照】
- 台鐵、台鐵、鐵路 → 正常詞
- 挑園、桃元、桃圓 → 桃園
- 台中、台忠、臺中 → 台中
- 台北、臺北、泰北 → 台北
- 高鐵、高速 → 高雄（如果是目的地）
- 幾點到、幾點抵達、幾點前到 → 目標抵達時間
- 幾點出發、幾點搭、幾點坐 → 出發時間
- 我在、我人在、我現在在、我從 → 出發地
- 要去、要到、要回、想去、想到 → 目的地

【解析欄位】
- date: 出發日期，格式 YYYY-MM-DD
- time: 目標時間（出發或抵達），格式 HH:MM（24小時制）
- time_type: "depart"（出發時間）或 "arrive"（抵達時間）
- origin: 出發地（保留使用者原始說法，已修正錯字）
- destination: 目的地（保留使用者原始說法，已修正錯字）

【規則】
1. 只輸出 JSON，不要任何說明文字、不要 markdown 格式
2. 無法解析的欄位填 null，不要猜測
3. 時間沒說上午下午，根據上下文判斷（回家通常下午、上班通常早上）
4. 「明天」「後天」「下週一」等相對日期，換算成絕對日期
5. 「2:30」沒有說上午下午，根據語境判斷
6. 如果使用者說「要回去」，目的地是家的方向
7. 錯字請直接修正後填入

【範例】
輸入：我5/30，2:30要回去挑園市桃園區，我人在台中市中區
輸出：{{"date":"2026-05-30","time":"14:30","time_type":"depart","origin":"台中市中區","destination":"桃園市桃園區"}}

輸入：明天早上十點台北出發去高雄
輸出：{{"date":"2026-05-23","time":"10:00","time_type":"depart","origin":"台北","destination":"高雄"}}

輸入：我想搭車去台南
輸出：{{"date":null,"time":null,"time_type":null,"origin":null,"destination":"台南"}}
"""

def call_ai(user_input: str) -> str | None:
    for model in FREE_MODELS:
        try:
            resp = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {or_key}",
                    "Content-Type": "application/json; charset=utf-8",
                    "HTTP-Referer": "http://localhost",
                    "X-Title": "TRA Assistant"
                },
                content=json.dumps({
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_input}
                    ]
                }, ensure_ascii=False).encode("utf-8"),
                timeout=30
            )
            data = resp.json()
            if "choices" in data:
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"  模型 {model} 錯誤：{e}")
    return None

def parse_user_input(user_input: str) -> dict | None:
    print(f"\n[NLU] 解析輸入：{user_input}")
    raw = call_ai(user_input)
    if not raw:
        print("[NLU] AI 呼叫失敗")
        return None
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1])
    try:
        result = json.loads(cleaned)
        print(f"[NLU] 解析結果：{result}")
        return result
    except json.JSONDecodeError:
        print(f"[NLU] JSON 解析失敗：{raw}")
        return None
def is_train_query(user_input: str) -> bool:
    """
    判斷使用者輸入是否跟台鐵查詢有關
    """
    # 明顯相關的關鍵字
    keywords = [
        "台鐵", "火車", "搭車", "坐車", "搭火車",
        "出發", "到", "去", "回", "前往",
        "車票", "訂票", "班次", "車次",
        "台北", "台中", "台南", "高雄", "桃園", "新竹",
        "花蓮", "台東", "基隆", "嘉義", "屏東",
        "幾點", "幾號", "明天", "後天", "下週",
        "今天", "早上", "下午", "晚上",
    ]
    
    text = user_input.strip()
    
    # 太短的輸入直接排除（少於2個字）
    if len(text) < 2:
        return False
    
    # 包含任何關鍵字就判斷為查詢
    return any(kw in text for kw in keywords)