# 同时起后端与前端开发服务
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\..\backend'; uv run uvicorn app.main:app --port 8756 --reload"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\..\frontend'; pnpm dev"
