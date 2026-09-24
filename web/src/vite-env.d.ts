/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Agent 后端地址，如 /agent（相对路径，走 vite 代理）或 http://127.0.0.1:8100 */
  readonly VITE_AGENT_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
