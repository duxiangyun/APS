FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/python:3.13-slim

WORKDIR /app
COPY requirements.txt .
# apt 换源为阿里云镜像：Debian 12+ 用 debian.sources，老版本回退 sources.list
RUN (sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null \
     || sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list) \
    && apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# pip 换源为阿里云 PyPI 镜像
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ \
    && pip config set global.trusted-host mirrors.aliyun.com \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

ENV APS_BASE_URL=http://aps:8000 \
    PORT=8100 \
    AGENT_DB_PATH=/app/data/audit.db

EXPOSE 8100
# 启动前先执行数据库迁移（幂等），成功后再启动服务
CMD ["sh", "-c", "python migrate.py && uvicorn app.main:app --host 0.0.0.0 --port 8100"]
