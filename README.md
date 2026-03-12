# N 大大摸魚日記

紀錄 Neal 日常摸魚的軌跡

## 快速開始

### 文檔服務

```sh
docsify serve docs
```

### GitHub 提交監控腳本

#### 環境配置

1. **創建虛擬環境**
   ```cmd
   python -m venv venv
   ```

2. **激活虛擬環境**

   在 **命令提示字元 (CMD)**:
   ```cmd
   venv\Scripts\activate
   ```

   在 **PowerShell**:
   ```powershell
   venv\Scripts\Activate.ps1
   ```

   如果 PowerShell 提示執行策略錯誤，執行：
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

3. **安裝依賴**
   ```cmd
   pip install -r requirements.txt
   ```

#### 配置 GitHub Token

設定 `GH_TOKEN` 環境變數以避免 GitHub API 限制 (從每小時 60 次提升至 5000 次)。

**臨時設定 (當前會話)**:

CMD:
```cmd
set GH_TOKEN=your_github_token_here
```

PowerShell:
```powershell
$env:GH_TOKEN="your_github_token_here"
```

**永久設定 (系統環境變數)**:
1. 開啟「系統內容」→「環境變數」
2. 新增使用者變數 `GH_TOKEN`，值為你的 GitHub Token

#### 運行腳本

```cmd
python monitor_commits.py
```

#### 停用虛擬環境

```cmd
deactivate
```