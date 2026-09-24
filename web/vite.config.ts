import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 开发服务器 5173。前端只与 agent（8100）通信，绝不直连 APS。
// 默认 VITE_AGENT_BASE_URL=/agent（同源相对路径，经下方代理转发）：
// 本地开发与 docker-compose（浏览器无法解析容器名 agent）都能工作，且无需 CORS。
// 如需直连，把 .env 里的 VITE_AGENT_BASE_URL 改成 http://127.0.0.1:8100。
const AGENT_TARGET = process.env.VITE_PROXY_TARGET || "http://127.0.0.1:8100";

export default defineConfig({
  plugins: [react()],
  build: {
    // 拆包：antd / echarts 体积较大，单独成块便于缓存与加载
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (!id.includes("node_modules")) return undefined;
          if (id.includes("echarts") || id.includes("zrender")) return "echarts";
          if (id.includes("antd") || id.includes("@ant-design")) return "antd";
          if (/react-markdown|remark|micromark|mdast|unified|hast|unist|vfile/.test(id)) {
            return "markdown";
          }
          if (/[\\/]node_modules[\\/](react|react-dom|scheduler)[\\/]/.test(id)) return "react";
          return undefined;
        },
      },
    },
    chunkSizeWarningLimit: 1100,
  },
  server: {
    port: 5173,
    host: true,
    proxy: {
      // /agent/skills -> <agent>/skills
      "/agent": {
        target: AGENT_TARGET,
        changeOrigin: true,
        ws: false,
        rewrite: (p: string) => p.replace(/^\/agent/, ""),
      },
      // 兼容旧路径 /api/* -> <agent>/api/*
      "/api": {
        target: AGENT_TARGET,
        changeOrigin: true,
      },
    },
  },
});
