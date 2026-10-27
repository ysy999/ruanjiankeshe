# ruanjiankeshe

前后端分离的 monorepo：`backend/` 为 FastAPI 服务，`frontend/` 为 Vue 3 + Vite 前端。

## 环境要求

- Python 3.11
- Node.js 18+（含 npm）

## 启动后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

服务默认运行在 `http://localhost:8000`，健康检查：`GET /api/health`。

## 初始化数据库

复制 `backend/.env.example` 为 `backend/.env`，按示例填写（不要把真实 key / 密码写进代码）。健康检查：`GET /api/health`，数据库连通性：`GET /api/health/db`。

然后任选其一：

```bash
cd backend
mysql -u user -p < schema.sql
python init_db.py
```

`init_db.py` 会创建 `ai_cs` 库和 5 张表，并插入测试订单 `O20261001001` ~ `O20261001003`。

## 启动前端

另开一个终端：

```bash
cd frontend
npm install
npm run dev
```

开发服务器默认运行在 `http://localhost:5173`。`/api` 会代理到 `http://localhost:8000`。
