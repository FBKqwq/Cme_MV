# 医疗智能辅助平台

本目录整合了病例诊断辅助预测与医学知识复验两个模块。前端通过路由独立切换，后端由一个 FastAPI 进程统一提供接口。

## 目录

- `frontend`：Vue 3、Vue Router、Pinia、Element Plus。
- `backend`：FastAPI、PostgreSQL 诊断数据、SQLite 复验状态。
- `ml`：诊断模型离线训练脚本。
- `data/review`：人工维护的知识复验输入及运行状态。

## 启动后端

```powershell
Set-Location .\backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
# 编辑 .env，填写 PostgreSQL 配置
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

诊断模块依赖可访问的 PostgreSQL 数据库和 `backend/models/diagnosis_classifier.joblib`。知识复验数据缺失只会使复验模块降级，不影响诊断模块。

## 启动前端

```powershell
Set-Location .\frontend
npm install
npm run dev
```

打开 `http://localhost:5173`。诊断页面保留原路径，知识复验页面位于 `/knowledge-review`。

## 检查

```powershell
Set-Location .\frontend
npm test
npm run build

Set-Location ..\backend
python -m pytest -q
```

未配置 PostgreSQL 时，诊断 API 集成测试会跳过；知识复验仓库、路由和降级行为仍会执行。
