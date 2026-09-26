FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/python:3.13-slim

WORKDIR /app
COPY requirements.txt .
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

ENV APS_BASE_URL=http://aps:8000 \
    PORT=8100 \
    AGENT_DB_PATH=/app/data/audit.db

EXPOSE 8100
# 启动前先执行数据库迁移（幂等），成功后再启动服务
CMD ["sh", "-c", "python migrate.py && uvicorn app.main:app --host 0.0.0.0 --port 8100"]
