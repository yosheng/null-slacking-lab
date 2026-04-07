import requests
import os
import json
import logging
from datetime import datetime, timedelta, timezone

# ================= 配置區域 =================
# 根據你的要求修改
GITLAB_URL = "https://git.gss.com.tw"
USER_ID = "neal_chen"
GITLAB_TOKEN = os.getenv("GITLAB_TOKEN") # 請在白虎面板環境變數設定

# 通知自訂
BOT_NAME = "摸魚監工"
BOT_ICON_EMOJI = ":senior:" # 使用 Mattermost 內建圖標

# 持久化目錄（腳本同目錄下的 seen_events 資料夾）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SEEN_DIR = os.path.join(SCRIPT_DIR, "seen_events")

# 日誌配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
# ===========================================

def get_today_seen_file():
    """取得今天的已發送事件記錄檔路徑"""
    os.makedirs(SEEN_DIR, exist_ok=True)
    # 使用台灣時區（UTC+8）的日期命名
    tw_tz = timezone(timedelta(hours=8))
    today_str = datetime.now(tw_tz).strftime("%Y-%m-%d")
    return os.path.join(SEEN_DIR, f"{today_str}.json")

def load_seen_ids():
    """載入今天已發送過的 event ID 集合"""
    path = get_today_seen_file()
    if not os.path.exists(path):
        return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data)
    except Exception as e:
        logging.error(f"讀取已發送記錄失敗: {e}")
        return set()

def save_seen_ids(seen_ids):
    """將已發送的 event ID 集合寫回今天的記錄檔"""
    path = get_today_seen_file()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(list(seen_ids), f, ensure_ascii=False)
    except Exception as e:
        logging.error(f"寫入已發送記錄失敗: {e}")

def get_project_name(project_id):
    """將 Project ID 轉換為專案名稱"""
    if not GITLAB_TOKEN:
        return f"ID:{project_id}"

    url = f"{GITLAB_URL}/api/v4/projects/{project_id}"
    headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            # 返回命名空間 + 專案名，例如 "Group / Project"
            return resp.json().get("name_with_namespace", f"ID:{project_id}")
    except Exception as e:
        logging.error(f"無法獲取專案 {project_id} 名稱: {e}")

    return f"ID:{project_id}"

def check_gitlab():
    """執行監控邏輯"""
    # 1. 定義精確的截止時間 (使用具備時區資訊的 UTC)
    now = datetime.now(timezone.utc)

    # 2. GitLab API 時間篩選只接受日期，用昨天確保能抓到今天所有事件，再自行過濾
    api_after_date = (now - timedelta(days=1)).date().isoformat()

    url = f"{GITLAB_URL}/api/v4/users/{USER_ID}/events"
    params = {
        "after": api_after_date,  # 使用 YYYY-MM-DD
        "sort": "desc",
        "per_page": 100
    }
    headers = {"PRIVATE-TOKEN": GITLAB_TOKEN} if GITLAB_TOKEN else {}

    logging.info(f"【{BOT_NAME}】啟動：正在掃描 {USER_ID} 於 {api_after_date} 後 GSS GitLab 的活動...")

    # 3. 載入今天已發送過的 event ID
    seen_ids = load_seen_ids()
    logging.info(f"已載入 {len(seen_ids)} 筆已發送記錄")

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        logging.info(f"發送請求至: {resp.url}")
        if resp.status_code != 200:
            logging.error(f"連線失敗 ({resp.status_code}): {resp.text}")
            return

        events = resp.json()
        if not events:
            logging.info("監控結果：目標目前很飄，沒有工作紀錄。")
            return

        # 4. 過濾掉已發送過的事件
        new_events = [e for e in events if str(e.get("id")) not in seen_ids]
        logging.info(f"共 {len(events)} 筆事件，其中 {len(new_events)} 筆為新增")

        if not new_events:
            logging.info("本次無新事件，跳過發送。")
            return

        # 5. 組合所有新事件為單一訊息
        lines = [f"🕵️‍♂️ **【{USER_ID}】活動報告（共 {len(new_events)} 筆）**"]
        for event in new_events:
            project_name = get_project_name(event["project_id"])
            action = event.get("action_name", "unknown")
            target = (event.get("target_title") or
                      event.get("push_data", {}).get("commit_title") or
                      "查看詳細動態")
            lines.append(f"- 專案: `{project_name}` | 動作: `{action}` | 內容: {target}")

        msg = "\n".join(lines)
        send_notification(msg)

        # 6. 發送成功後更新已發送記錄
        for event in new_events:
            seen_ids.add(str(event.get("id")))
        save_seen_ids(seen_ids)
        logging.info(f"已更新已發送記錄，目前共 {len(seen_ids)} 筆")

    except Exception as e:
        logging.error(f"執行出錯: {e}")

def send_notification(text):
    """發送至 Mattermost"""
    webhook_url = os.getenv("MM_WEBHOOK_URL")
    if not webhook_url:
        logging.warning("未偵測到 MM_WEBHOOK_URL，取消發送。")
        return

    payload = {
        "username": BOT_NAME,
        "icon_emoji": BOT_ICON_EMOJI,
        "text": text
    }

    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        logging.info(f"通知發送完成，狀態碼: {resp.status_code}")
    except Exception as e:
        logging.error(f"通知發送失敗: {e}")

if __name__ == "__main__":
    check_gitlab()