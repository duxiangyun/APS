import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// 开发服务器 5173。前端只与 agent（8100）通信，绝不直连 APS。
// 默认 VITE_AGENT_BASE_URL=/agent（同源相对路径，经下方代理转发）：
// 本地开发与 docker-compose（浏览器无法解析容器名 agent）都能工作，且无需 CORS。
// 如需直连，把 .env 里的 VITE_AGENT_BASE_URL 改成 http://127.0.0.1:8100。
//
// 「排产管理」Tab 的 iframe 走 /aps 同源代理（见 server.proxy["/aps"]）：
// 浏览器只请求相对路径 /aps/*，由 vite 转发到 APS_PROXY_TARGET，
// 避免写死 http://localhost:8000 在服务器环境指向访问者本机导致「连接被拒绝」。

/** /aps 代理前缀（响应重写时回加） */
const APS_PREFIX = "/aps";

/**
 * 把 APS 返回 HTML 中的根绝对路径改写为 /aps 前缀。
 * APS 模板使用 href="/res"、src="/static/..."、fetch('/api/...')、API_BASE='/api/...'
 * 等根绝对路径——不改写的话，iframe 内的导航、静态资源与接口请求会逃出 /aps 前缀，
 * 落到 vite 自身路由（SPA fallback 白屏）或被 /api 规则误转发给 agent。
 * 排除：协议相对（//cdn）、引号后非 / 的外部地址、已带 /aps 前缀的路径。
 */
function rewriteHtmlPaths(html: string): string {
  return html
    // 属性：href="/x"、src='/x'、action="/x"
    .replace(/\b(href|src|action)(\s*=\s*)(["'])\/(?!\/|aps\/)/gi, "$1$2$3/aps/")
    // 脚本：fetch('/x')、fetch("/x")、fetch(`/x`)
    .replace(/\bfetch\(\s*(["'`])\/(?!\/|aps\/)/g, "fetch($1/aps/")
    // CSS：url(/x)、url('/x')
    .replace(/\burl\(\s*(["']?)\/(?!\/|aps\/)/gi, "url($1/aps/")
    // 模板注入的 JS 基址：const API_BASE = '/api/...'
    .replace(/\bAPI_BASE(\s*=\s*)(["'])\/(?!\/|aps\/)/g, "API_BASE$1$2/aps/")
    // 脚本内跳转：location.href = '/x'
    .replace(/\blocation\.href(\s*=\s*)(["'])\/(?!\/|aps\/)/g, "location.href$1$2/aps/");
}

export default defineConfig(({ mode }) => {
  // 读取 .env* 文件；shell 环境变量优先（docker-compose 注入的容器内地址须覆盖 .env 文件）
  const fileEnv = loadEnv(mode, process.cwd(), "");
  const AGENT_TARGET =
    process.env.VITE_PROXY_TARGET || fileEnv.VITE_PROXY_TARGET || "http://127.0.0.1:8100";
  const APS_TARGET =
    process.env.APS_PROXY_TARGET || fileEnv.APS_PROXY_TARGET || "http://127.0.0.1:8000";

  return {
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
    host: "0.0.0.0",
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
      // /aps/* -> <APS>/* APS 反向代理（iframe「排产管理」Tab）
      "/aps": {
        target: APS_TARGET,
        changeOrigin: true,
        // 转发前剥掉 /aps 前缀：/aps → /、/aps/dashboard → /dashboard、/aps?x → /?x
        rewrite: (path: string) => {
          const stripped = path.replace(/^\/aps(?=\/|$|\?)/, "");
          if (stripped === "") return "/";
          return stripped.startsWith("?") ? "/" + stripped : stripped;
        },
        // HTML 页面与 3xx Location 内含根绝对路径，须重写后返回，
        // 否则 iframe 内导航 / 静态资源 / 接口请求会逃出 /aps 前缀
        selfHandleResponse: true,
        configure: (proxy) => {
          proxy.on("proxyRes", (proxyRes, req, res) => {
            if (res.headersSent || res.writableEnded) return;
            const status = proxyRes.statusCode ?? 502;
            const headers = { ...proxyRes.headers };

            // 重定向（如 APS 首页 / → /dashboard）：Location 回加 /aps 前缀，保持在代理前缀内
            const loc = headers.location;
            if (typeof loc === "string") {
              if (loc.startsWith("/") && !loc.startsWith(`${APS_PREFIX}/`) && loc !== APS_PREFIX) {
                headers.location = APS_PREFIX + loc;
              } else if (loc.startsWith(APS_TARGET)) {
                headers.location = APS_PREFIX + loc.slice(APS_TARGET.length);
              }
            }

            const contentType = String(headers["content-type"] ?? "");
            const isHtml =
              req.method !== "HEAD" &&
              contentType.includes("text/html") &&
              !headers["content-encoding"];

            if (!isHtml) {
              // 静态资源 / JSON / SSE：原样流式直通（去掉上游 chunked，由 Node 按需重新分块）
              delete headers["transfer-encoding"];
              res.writeHead(status, headers);
              proxyRes.pipe(res);
              return;
            }

            // HTML：缓冲后改写根绝对路径（APS 未启用 gzip，见 aps/src/web/app/main.py）
            const chunks: Buffer[] = [];
            proxyRes.on("data", (chunk: Buffer) => chunks.push(chunk));
            proxyRes.on("error", () => {
              if (!res.writableEnded) res.destroy();
            });
            proxyRes.on("end", () => {
              if (res.writableEnded || res.destroyed) return;
              const body = Buffer.from(
                rewriteHtmlPaths(Buffer.concat(chunks).toString("utf8")),
                "utf8",
              );
              delete headers["transfer-encoding"];
              headers["content-length"] = String(body.length);
              res.writeHead(status, headers);
              res.end(body);
            });
          });

          // APS 未启动时返回 502 提示，替代浏览器原始的「连接被拒绝」报错
          proxy.on("error", (err, _req, res) => {
            if (res && "writeHead" in res && !res.headersSent && !res.writableEnded) {
              res.writeHead(502, { "content-type": "text/plain; charset=utf-8" });
              res.end(
                `APS 代理转发失败（${APS_TARGET}）：${err.message}\n请先启动 APS 服务：./aps/start.sh`,
              );
            }
          });
        },
      },
    },
  },
  };
});
