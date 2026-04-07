import requests
import os
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

# 日誌配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
# ===========================================

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
    # 1. 定義精確的截止時間 (使用具備時區資訊的 UTC，或你當前的時區)
    # 這裡我們取 UTC 並加上時區資訊
    now = datetime.now(timezone.utc)
    cutoff_time = now - timedelta(minutes=121)
    
    # 2. 為了讓 GitLab API 聽話，我們傳送「日期」就好 (取當天或前一天)
    # 這樣保證能抓到今天所有事件，我們再回來自己濾
    api_after_date = (now - timedelta(days=1)).date().isoformat()

    url = f"{GITLAB_URL}/api/v4/users/{USER_ID}/events"
    params = {
        "after": api_after_date,  # 使用 YYYY-MM-DD
        "sort": "desc",
        "per_page": 100 
    }
    headers = {"PRIVATE-TOKEN": GITLAB_TOKEN} if GITLAB_TOKEN else {}

    logging.info(f"【{BOT_NAME}】啟動：正在掃描 {USER_ID} 於 {api_after_date} 中 GSS GitLab 的活動...")
    
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        logging.info(f"發送請求至: {resp.url}")
        if resp.status_code == 200:
            events = resp.json()
            if not events:
                logging.info("監控結果：目標目前很飄，沒有工作紀錄。")
                return

            for event in events:
                project_name = get_project_name(event['project_id'])
                action = event.get("action_name")
                # 取得提交訊息或目標標題
                target = (event.get("target_title") or 
                          event.get("push_data", {}).get("commit_title") or 
                          "查看詳細動態")
                
                # 組合通知內容
                msg = (
                    f"🕵️‍♂️ **【{USER_ID}】活動報告**\n"
                    f"- **操作專案**: `{project_name}`\n"
                    f"- **動作類型**: `{action}`\n"
                    f"- **具體內容**: {target}"
                )
                
                send_notification(msg)
        else:
            logging.error(f"連線失敗 ({resp.status_code}): {resp.text}")
    except Exception as e:
        logging.error(f"執行出錯: {e}")

def send_notification(text):
    """發送至 Mattermost"""
    webhook_url = os.getenv("MM_WEBHOOK_URL")
    if not webhook_url:
        logging.warning("未偵測到 MM_WEBHOOK_URL，取消發送。")
        return

    # 使用 icon_emoji 替換 icon_url
    payload = {
        "username": BOT_NAME,
        "icon_emoji": BOT_ICON_EMOJI, 
        "text": text
    }
    
    try:
        requests.post(webhook_url, json=payload, timeout=10)
    except Exception as e:
        logging.error(f"通知發送失敗: {e}")

if __name__ == "__main__":
    check_gitlab()