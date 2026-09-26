import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import "antd/dist/reset.css";
import App from "./App";
import "./design-tokens.css";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: { colorPrimary: "#2563eb", borderRadius: 8, fontSize: 13 },
      }}
    >
      <App />
    </ConfigProvider>
  </StrictMode>,
);
