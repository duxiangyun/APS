FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/node:20-alpine

WORKDIR /app

# npm 换源为 npmmirror 镜像，加速依赖安装
RUN npm config set registry https://registry.npmmirror.com

# 代码由 docker-compose 以 volume 挂载（./web:/app），依赖在启动时安装（与原部署行为一致）
CMD ["sh", "-c", "npm install && npm run dev -- --host 0.0.0.0"]
