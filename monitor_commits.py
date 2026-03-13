import requests
import os
from datetime import datetime, timedelta

# 配置
USER = "Neal75418"
# 建議在 Secrets 設定 GH_TOKEN，避免 API 次數限制 (每小時 60 次 -> 5000 次)
TOKEN = os.getenv("GH_TOKEN") 
MM_WEBHOOK = os.getenv("MM_WEBHOOK_URL")

headers = {
    "Accept": "application/vnd.github.v3+json",
}
if TOKEN:
    headers["Authorization"] = f"token {TOKEN}"

def get_active_repos():
    """獲取該帳號最近有更新的公開倉庫"""
    url = f"https://api.github.com/users/{USER}/repos"
    params = {"sort": "updated", "per_page": 10}
    resp = requests.get(url, params=params, headers=headers)
    if resp.status_code == 200:
        return [repo["name"] for repo in resp.json()]
    return []

def check_commits():
    # 設定時間範圍：過去 180 分鐘 (多加 1 分鐘緩衝避免邊際遺漏)
    time_threshold = datetime.utcnow() - timedelta(minutes=181)
    since_time = time_threshold.isoformat() + "Z"
    
    repos = get_active_repos()
    found_any = False

    for repo in repos:
        url = f"https://api.github.com/repos/{USER}/{repo}/commits"
        params = {"author": USER, "since": since_time}
        
        resp = requests.get(url, params=params, headers=headers)
        if resp.status_code == 200:
            commits = resp.json()
            for c in commits:
                found_any = True
                commit_msg = c['commit']['message'].split('\n')[0] # 只取標題
                msg = (
                    f"🛠️ **GitHub 提交監控**\n"
                    f"- **倉庫**: `{repo}`\n"
                    f"- **訊息**: {commit_msg}\n"
                    f"- **連結**: [檢視 Commit]({c['html_url']})"
                )
                requests.post(MM_WEBHOOK, json={"text": msg})
    
    if not found_any:
        print(f"{datetime.now()}: 沒有發現新提交。")

if __name__ == "__main__":
    check_commits()