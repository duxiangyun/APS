"""Web Agent 后端入口

启动：uvicorn app.main:app --host 0.0.0.0 --port 8100（或 ./start.sh）
"""
import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import audit
from .routes import router

app = FastAPI(
    title="APS Web Agent 后端",
    version="0.2.0",
    description="轻量 ReAct 循环 + APS 只读工具 + SSE 流式输出",
)

# web/ 开发服务器（5173）跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# 启动时确保审计表存在（幂等）
audit.init_db()


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8100")),
    )
