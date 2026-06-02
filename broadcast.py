# broadcast.py
import json
import os
import random

BROADCAST_FILE  = "broadcast_images.json"
LOCAL_IMAGE_DIR = "broadcast_images"  # 放圖片的資料夾名稱

def get_public_base_url() -> str:
    """從環境變數讀取 ngrok 的公開網址"""
    return os.getenv("PUBLIC_URL", "").rstrip("/")

def load_images() -> list[dict]:
    """載入 JSON 設定的圖片 + 掃描本地資料夾的圖片"""
    images = []

    # 1. 讀取 JSON 設定的遠端圖片
    if os.path.exists(BROADCAST_FILE):
        with open(BROADCAST_FILE, "r", encoding="utf-8") as f:
            images.extend(json.load(f))

    # 2. 掃描本地資料夾
    base_url = get_public_base_url()
    if base_url and os.path.exists(LOCAL_IMAGE_DIR):
        supported = (".jpg", ".jpeg", ".png")
        for filename in os.listdir(LOCAL_IMAGE_DIR):
            if filename.lower().endswith(supported):
                url = f"{base_url}/images/{filename}"
                images.append({
                    "url":     url,
                    "preview": url,
                    "caption": "",
                    "source":  "local",
                })

    return images

def get_random_image() -> dict | None:
    images = load_images()
    return random.choice(images) if images else None

def add_image(url: str, preview_url: str, caption: str = ""):
    images = []
    if os.path.exists(BROADCAST_FILE):
        with open(BROADCAST_FILE, "r", encoding="utf-8") as f:
            images = json.load(f)
    images.append({"url": url, "preview": preview_url, "caption": caption})
    with open(BROADCAST_FILE, "w", encoding="utf-8") as f:
        json.dump(images, f, ensure_ascii=False, indent=2)

def list_local_images() -> list[str]:
    """列出本地圖片資料夾的所有檔名"""
    if not os.path.exists(LOCAL_IMAGE_DIR):
        return []
    supported = (".jpg", ".jpeg", ".png")
    return [f for f in os.listdir(LOCAL_IMAGE_DIR)
            if f.lower().endswith(supported)]