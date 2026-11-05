# 本地运行指南

这份说明按 Windows + PowerShell 编写。照着命令逐条复制运行即可。

## 第一次运行

### 1. 先启动 MySQL

请确认电脑上的 MySQL 8 已经启动。项目会使用名为 `ai_cs` 的数据库；下面的初始化命令会自动创建数据库、数据表和几条示例订单。

### 2. 准备本地配置文件

打开 PowerShell，先进入项目文件夹：

```powershell
cd C:\Users\A\Desktop\ruanjiankeshe
```

如果 `backend\.env` 还不存在，复制一份示例配置：

```powershell
Copy-Item .env.example backend\.env
```

打开配置文件：

```powershell
notepad backend\.env
```

在记事本里填写自己的 MySQL 用户名、密码和 DeepSeek API Key，然后保存。数据库连接和模型设置格式如下：

```text
DATABASE_URL=mysql+pymysql://root:你的MySQL密码@127.0.0.1:3306/ai_cs?charset=utf8mb4
LLM_PROVIDER=deepseek
LLM_API_KEY=你的DeepSeek_API密钥
LLM_MODEL=deepseek-flash
LLM_BASE_URL=https://api.deepseek.com
EMBEDDING_MODEL=text-embedding-v4
```

请把示例文字换成你自己的值。不要把真实密码或 API Key 发给别人，也不要提交到代码仓库。

### 3. 安装后端依赖并初始化数据库

在 PowerShell 里运行：

```powershell
py -3.11 -m venv backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install --upgrade pip
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\backend\.venv\Scripts\python.exe backend\init_db.py
```

看到 `Database initialized` 就表示数据库准备好了。这一步只需第一次运行时做。

### 4. 安装前端依赖

```powershell
cd frontend
npm install
```

看到安装完成后，第一次安装就结束了。

## 以后再次运行

每次使用前，请先确认 MySQL 已启动。然后打开两个 PowerShell 窗口。

### 窗口一：启动后端

```powershell
cd C:\Users\A\Desktop\ruanjiankeshe\backend
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

看到 `Uvicorn running` 后，让这个窗口保持打开。

### 窗口二：启动前端

```powershell
cd C:\Users\A\Desktop\ruanjiankeshe\frontend
npm run dev
```

看到本地访问地址后，在浏览器打开：

```text
http://localhost:5173/chat
```

两个窗口都要保持打开。要停止项目，在两个窗口里分别按 `Ctrl+C`。再次运行时**不用重新安装依赖，也不用再次初始化数据库**。

## 页面介绍

- **首页 `/`**：显示服务健康状态。看到 `{"status":"ok"}` 表示前后端已经连通。
- **聊天 `/chat`**：新建对话、发送消息和查看历史会话。AI 回复需要有效且有权限的模型 API Key 和可用额度。
- **偏好设置 `/settings`**：设置回复风格、长度、是否显示来源和昵称。
- **知识管理 `/knowledge`**：知识库管理页面。目前知识检索和部分管理接口还没有完整接通；基础页面启动不需要 Docker。

## 常见情况

- **`/api/health/db` 出错**：确认 MySQL 正在运行，并检查 `backend\.env` 里的用户名、密码和数据库名。
- **浏览器能打开页面，但 AI 没有回复**：检查 `backend\\.env` 中的 DeepSeek API Key、模型名 `deepseek-flash` 和账户余额/额度。
- **首页显示 JSON**：这是健康检查结果，属于正常现象。聊天页面地址是 `http://localhost:5173/chat`。
- **没有安装 Docker**：基础前后端和聊天页面可以先启动。完整的 Milvus 知识检索需要后续配置 Docker 和 Milvus。

## 环境要求

- Windows、Python 3.11、Node.js 18 或更高版本
- MySQL 8
- DeepSeek API Key（使用 AI 回复时需要）
- Docker Desktop（仅在配置 Milvus 知识检索时需要）
