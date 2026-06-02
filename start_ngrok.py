from pyngrok import ngrok, conf
import time
import os

conf.get_default().auth_token = "3EWVohsOObz6ScXPuBbakTQPYNy_6F6bkzhaw9WEvA3RA8zSe"

public_url = ngrok.connect(5000)
url_str    = str(public_url).split('"')[1]

print(f"\n✅ Webhook URL：{url_str}/callback")
print(f"📸 圖片網址：{url_str}/images/你的圖片.jpg")

# 自動更新 .env 裡的 PUBLIC_URL
env_path = ".env"
lines    = []
updated  = False

if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if line.startswith("PUBLIC_URL="):
            lines[i] = f"PUBLIC_URL={url_str}\n"
            updated  = True

if not updated:
    lines.append(f"PUBLIC_URL={url_str}\n")

with open(env_path, "w", encoding="utf-8") as f:
    f.writelines(lines)

print(f"✅ PUBLIC_URL 已自動更新到 .env")
print("\n保持這個視窗開著，按 Ctrl+C 停止")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    ngrok.kill()