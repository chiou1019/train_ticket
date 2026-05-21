# timetable.py
import os
import time
import httpx
from dotenv import load_dotenv

load_dotenv()

TDX_CLIENT_ID     = os.getenv("TDX_CLIENT_ID")
TDX_CLIENT_SECRET = os.getenv("TDX_CLIENT_SECRET")
TDX_AUTH_URL      = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
TDX_API_BASE      = "https://tdx.transportdata.tw/api/basic"

_token_cache      = {"access_token": None}
_timetable_cache  = {}   # date → 全班次資料，避免重複打 API


def get_token() -> str:
    if _token_cache["access_token"]:
        return _token_cache["access_token"]
    resp = httpx.post(
        TDX_AUTH_URL,
        data={
            "grant_type":    "client_credentials",
            "client_id":     TDX_CLIENT_ID,
            "client_secret": TDX_CLIENT_SECRET,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    resp.raise_for_status()
    token = resp.json()["access_token"]
    _token_cache["access_token"] = token
    return token


def _fetch_all_trains(date: str) -> list[dict]:
    """
    抓取某日期全部班次，有快取就直接回傳，避免重複打 API
    """
    if date in _timetable_cache:
        print(f"  [TDX] 使用快取資料（{date}）")
        return _timetable_cache[date]

    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{TDX_API_BASE}/v2/Rail/TRA/DailyTimetable/TrainDate/{date}?$format=JSON"

    # 最多重試3次，每次等待時間加倍
    wait = 5
    for attempt in range(3):
        resp = httpx.get(url, headers=headers, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            _timetable_cache[date] = data
            print(f"  [TDX] 當天共 {len(data)} 班車次")
            return data
        elif resp.status_code == 429:
            print(f"  [TDX] 被限速，等待 {wait} 秒後重試（第{attempt+1}次）...")
            time.sleep(wait)
            wait *= 2
        elif resp.status_code == 401:
            _token_cache["access_token"] = None
            token = get_token()
            headers = {"Authorization": f"Bearer {token}"}
        else:
            print(f"  [TDX] 錯誤 {resp.status_code}：{resp.text[:100]}")
            break

    return []


def query_timetable(origin_id: str, dest_id: str, date: str,
                    origin_full_id: str = None, dest_full_id: str = None) -> list[dict]:
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}

    # 策略一：OD 直接查詢（快速）
    url = (
        f"{TDX_API_BASE}/v2/Rail/TRA/DailyTimetable/OD"
        f"/{origin_id}/to/{dest_id}/{date}?$format=JSON"
    )
    resp = httpx.get(url, headers=headers, timeout=15)

    if resp.status_code == 401:
        _token_cache["access_token"] = None
        return query_timetable(origin_id, dest_id, date)

    if resp.status_code == 200:
        data = resp.json()
        if data:
            print(f"  [TDX] OD查詢成功，找到 {len(data)} 班")
            return data

    # 策略二：從全班次快取裡過濾
    print(f"  [TDX] OD查詢為空（{resp.status_code}），改用全班次過濾...")
    all_trains = _fetch_all_trains(date)

    result = []
    for train in all_trains:
        stops      = train.get("StopTimes", [])
        origin_seq = None
        dest_seq   = None
        origin_dep = None
        dest_arr   = None

        for stop in stops:
            sid = stop.get("StationID", "")
            if sid == (origin_full_id or origin_id) and origin_seq is None:
                origin_seq = stop.get("StopSequence", 0)
                origin_dep = stop.get("DepartureTime", "")
            if sid == (dest_full_id or dest_id) and dest_seq is None:
                dest_seq = stop.get("StopSequence", 0)
                dest_arr  = stop.get("ArrivalTime", "") or stop.get("DepartureTime", "")

        if origin_seq and dest_seq and origin_seq < dest_seq:
            info = train.get("DailyTrainInfo", {})   # ← 改這行，從 TrainInfo 改成 DailyTrainInfo
            result.append({
                "TrainDate": date,
                "DailyTrainInfo": {
                    "TrainNo":       info.get("TrainNo", ""),
                    "TrainTypeName": info.get("TrainTypeName", {}),
                },
                "OriginStopTime":      {"DepartureTime": origin_dep},
                "DestinationStopTime": {"ArrivalTime":   dest_arr},
            })

    print(f"  [TDX] 過濾後找到 {len(result)} 班符合班次")
    return result


def time_to_minutes(time_str: str) -> int:
    try:
        h, m = time_str.split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return 0


def find_best_trains(timetable: list[dict], target_time: str, top_n: int = 3) -> list[dict]:
    target_min = time_to_minutes(target_time)
    candidates = []

    for train in timetable:
        info        = train.get("DailyTrainInfo", {})
        origin      = train.get("OriginStopTime", {})
        dest        = train.get("DestinationStopTime", {})
        depart_time = origin.get("DepartureTime", "")
        arrive_time = dest.get("ArrivalTime", "") or dest.get("DepartureTime", "")

        if not depart_time:
            continue

        depart_min = time_to_minutes(depart_time)
        if depart_min <= target_min:
            candidates.append({
                "train_no":    info.get("TrainNo", ""),
                "train_type":  info.get("TrainTypeName", {}).get("Zh_tw", ""),
                "depart_time": depart_time,
                "arrive_time": arrive_time,
                "depart_min":  depart_min,
            })

    candidates.sort(key=lambda x: x["depart_min"], reverse=True)
    return candidates[:top_n]

if __name__ == "__main__":
    import json
    trains = _fetch_all_trains("2026-05-23")
    # 印出第一筆的完整結構
    print(json.dumps(trains[0], ensure_ascii=False, indent=2))