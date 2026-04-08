import requests
import os
import json
import logging
from datetime import datetime, timedelta, timezone

# ================= 配置區域 =================
GITLAB_URL = "https://git.gss.com.tw"
USER_ID = "neal_chen"
GITLAB_TOKEN = os.getenv("GITLAB_TOKEN")  # 請在白虎面板環境變數設定

# 通知自訂
BOT_NAME = "摸魚監工"
BOT_ICON_EMOJI = ":senior:"  # 使用 Mattermost 內建圖標

# 持久化目錄（腳本同目錄下的 seen_events 資料夾）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SEEN_DIR = os.path.join(SCRIPT_DIR, "seen_events")

# 時區
TW_TZ = timezone(timedelta(hours=8))

# 日誌配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
# ===========================================


# ==================== 持久化 ====================

def get_record_file(date_str: str = None) -> str:
    """
    取得指定日期（或今天）的記錄檔路徑。
    date_str 格式：YYYY-MM-DD，省略則使用台灣時區當天日期。
    """
    os.makedirs(SEEN_DIR, exist_ok=True)
    if date_str is None:
        date_str = datetime.now(TW_TZ).strftime("%Y-%m-%d")
    return os.path.join(SEEN_DIR, f"{date_str}.json")


def load_record(date_str: str = None) -> dict:
    """
    載入指定日期的事件記錄。
    回傳格式：{ "event_id": { "project_name", "action", "target", "sent_at" }, ... }
    """
    path = get_record_file(date_str)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"讀取事件記錄失敗 [{path}]: {e}")
        return {}


def save_record(record: dict, date_str: str = None) -> bool:
    """
    將事件記錄寫回檔案。
    回傳 True 表示成功，False 表示失敗。
    """
    path = get_record_file(date_str)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logging.error(f"寫入事件記錄失敗 [{path}]: {e}")
        return False


# ==================== GitLab API ====================

def get_project_info(project_id) -> tuple[str, str]:
    """將 Project ID 轉換為 (專案名稱, path_with_namespace)，失敗時回傳 fallback。"""
    if not GITLAB_TOKEN:
        return f"ID:{project_id}", ""

    url = f"{GITLAB_URL}/api/v4/projects/{project_id}"
    headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("name_with_namespace", f"ID:{project_id}"), data.get("path_with_namespace", "")
        logging.warning(f"查詢專案 {project_id} 回傳 {resp.status_code}")
    except Exception as e:
        logging.error(f"無法獲取專案 {project_id} 名稱: {e}")
    return f"ID:{project_id}", ""


def fetch_gitlab_events(after_date: str) -> list:
    """
    從 GitLab API 抓取指定日期之後的事件列表。
    after_date 格式：YYYY-MM-DD
    回傳事件列表，失敗時回傳空列表。
    """
    url = f"{GITLAB_URL}/api/v4/users/{USER_ID}/events"
    params = {
        "after": after_date,
        "sort": "desc",
        "per_page": 100,
    }
    headers = {"PRIVATE-TOKEN": GITLAB_TOKEN} if GITLAB_TOKEN else {}

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        logging.info(f"請求 GitLab API: {resp.url}")
        if resp.status_code == 200:
            return resp.json()
        logging.error(f"GitLab API 回傳錯誤 ({resp.status_code}): {resp.text}")
    except Exception as e:
        logging.error(f"GitLab API 請求失敗: {e}")
    return []


# ==================== 事件處理 ====================

def build_event_record(event: dict) -> dict:
    """
    將單筆 GitLab event 轉為持久化用的記錄格式。
    回傳：{ "project_name", "action", "target", "sent_at" }
    """
    project_name, project_path = get_project_info(event.get("project_id"))
    action = event.get("action_name", "unknown")
    push_data = event.get("push_data", {})
    # 優先取 push_data.commit_title，其次 target_title，最後 fallback
    target = (
        push_data.get("commit_title")
        or event.get("target_title")
        or "查看詳細動態"
    )
    commit_to = push_data.get("commit_to")
    commit_url = f"{GITLAB_URL}/{project_path}/-/commit/{commit_to}" if commit_to and project_path else ""
    created_at = datetime.fromisoformat(event["created_at"]).astimezone(TW_TZ).strftime("%Y-%m-%d %H:%M:%S")
    sent_at = datetime.now(TW_TZ).strftime("%Y-%m-%d %H:%M:%S")
    return {
        "project_name": project_name,
        "action": action,
        "target": target,
        "commit_url": commit_url,
        "created_at": created_at,
        "sent_at": sent_at,
    }


def format_message(new_records: dict) -> str:
    """
    將新事件記錄組合成 Mattermost 訊息文字。
    new_records 格式：{ "event_id": { "project_name", "action", "target", ... }, ... }
    """
    count = len(new_records)
    lines = [f"🕵️‍♂️ **【{USER_ID}】活動報告（共 {count} 筆）**"]
    for record in new_records.values():
        lines.append(f"- 專案: `{record['project_name']}`| 時間: {record['created_at']}")
        commit_link = f" [🔗]({record['commit_url']})" if record.get("commit_url") else ""
        lines.append(f"  - 動作: `{record['action']}` | 內容: {record['target']}{commit_link}")
    return "\n".join(lines)


# ==================== 通知發送 ====================

def send_notification(text: str) -> bool:
    """
    發送訊息至 Mattermost Webhook。
    回傳 True 表示成功，False 表示失敗。
    """
    webhook_url = os.getenv("MM_WEBHOOK_URL")
    if not webhook_url:
        logging.warning("未偵測到 MM_WEBHOOK_URL，取消發送。")
        return False

    payload = {
        "username": BOT_NAME,
        "icon_emoji": BOT_ICON_EMOJI,
        "text": text,
    }
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        logging.info(f"通知發送完成，狀態碼: {resp.status_code}")
        return resp.status_code in (200, 201)
    except Exception as e:
        logging.error(f"通知發送失敗: {e}")
        return False


# ==================== 主流程 ====================

def check_gitlab():
    """
    主監控流程：
    1. 從 GitLab 抓取最近事件
    2. 比對本地記錄，篩出未發送的新事件
    3. 合併成一則訊息發送至 Mattermost
    4. 發送成功後將新事件（含內容）持久化至當天記錄檔
    """
    now_utc = datetime.now(timezone.utc)
    # GitLab API 只接受日期篩選，用昨天確保能取到今天全部事件，再本地去重
    api_after_date = (now_utc - timedelta(days=1)).date().isoformat()

    logging.info(f"【{BOT_NAME}】啟動：掃描 {USER_ID} 於 {api_after_date} 後的 GitLab 活動...")

    # 載入今天已發送記錄，key 為 event_id 字串
    today_record = load_record()
    seen_ids = set(today_record.keys())
    logging.info(f"已載入今日記錄：{len(seen_ids)} 筆已發送事件")

    # 抓取 GitLab 事件
    events = fetch_gitlab_events(api_after_date)
    if not events:
        logging.info("監控結果：目標目前很飄，沒有工作紀錄。")
        return

    # 篩出尚未發送的事件
    new_events = [e for e in events if str(e.get("id")) not in seen_ids]
    logging.info(f"共 {len(events)} 筆事件，{len(new_events)} 筆為新增")

    if not new_events:
        logging.info("本次無新事件，跳過發送。")
        return

    # 建立新事件記錄（含完整內容）
    new_records = {}
    for event in new_events:
        event_id = str(event.get("id"))
        new_records[event_id] = build_event_record(event)

    # 組合訊息並發送
    msg = format_message(new_records)
    success = send_notification(msg)

    if not success:
        logging.error("訊息發送失敗，本次事件不寫入記錄，下次執行將重新嘗試。")
        return

    # 發送成功後合併寫入記錄
    today_record.update(new_records)
    if save_record(today_record):
        logging.info(f"記錄已更新，今日累計 {len(today_record)} 筆事件")
    else:
        logging.error("記錄寫入失敗，下次執行可能重複發送相同事件。")


if __name__ == "__main__":
    check_gitlab()