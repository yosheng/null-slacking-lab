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
    # 設定時間範圍：過去 120 分鐘 (UTC)
    time_threshold = datetime.utcnow() - timedelta(minutes=121)
    since_time = time_threshold.isoformat() + "Z"
    
    repos = get_active_repos()
    all_commit_messages = [] # 用來存儲所有格式化後的提交資訊

    for repo in repos:
        url = f"https://api.github.com/repos/{USER}/{repo}/commits"
        params = {"author": USER, "since": since_time}
        
        resp = requests.get(url, params=params, headers=headers)
        if resp.status_code == 200:
            commits = resp.json()
            for c in commits:
                # 解析時間與格式化
                raw_date = c['commit']['author']['date']
                dt = datetime.fromisoformat(raw_date.replace('Z', '+08:00'))
                formatted_date = dt.strftime('%Y-%m-%d %H:%M:%S')
                
                commit_msg = c['commit']['message'].split('\n')[0]
                
                # 建立單條訊息簡潔版
                single_msg = (
                    f"📦 **`{repo}`** | {formatted_date}\n"
                    f"💬 {commit_msg} [🔗]({c['html_url']})"
                )
                all_commit_messages.append(single_msg)

    # 如果有收集到任何提交，整合後發送一次
    if all_commit_messages:
        header = f"🛠️ **GitHub 提交彙報 (過去 2 小時)**\n"
        
        # 使用兩個換行符隔開每個 commit，避免視覺太擠
        final_msg = header + "\n" + "\n\n".join(all_commit_messages)
        
        payload = {
            "text": final_msg,
            "username": "摸魚監控員",
            "icon_emoji": ":detective:"
        }
        requests.post(MM_WEBHOOK, json=payload)
    else:
        print(f"{datetime.now()}: 沒有發現新提交。")

if __name__ == "__main__":
    check_commits()