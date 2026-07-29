# 医疗智能辅助平台

本目录整合了病例诊断辅助预测与医学知识复验两个模块。前端通过路由独立切换，后端由一个 FastAPI 进程统一提供接口。

## 目录

- `frontend`：Vue 3、Vue Router、Pinia、Element Plus。
- `backend`：FastAPI、诊断模型以及 JSON 文件仓储。
- `ml`：诊断模型离线训练脚本。
- `data/review`：人工维护的知识复验输入及运行状态。
- `data/runtime`：病例、预测、标注、训练任务和模型版本等运行数据。

## 启动后端

```powershell
Set-Location .\backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

诊断模块依赖 `backend/models/diagnosis_classifier.joblib`，不依赖外部数据库。病例、预测和医生标注写入 `data/runtime/clinical_records.json`；训练任务和模型版本写入 `data/runtime/training_state.json`。配置中的数据目录均相对于项目根目录。

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

测试使用隔离的相对路径文件目录，不需要启动任何外部服务。
112122