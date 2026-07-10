# xiangmushu Frontend / 项目树前端

React SPA that provides the user interface for the xiangmushu document generation system. Built with React 18, Vite 6, TypeScript, and Tailwind CSS.

React 单页应用，为项目树文档生成系统提供用户界面。技术栈：React 18 + Vite 6 + TypeScript + Tailwind CSS。

---

## Prerequisites / 环境要求

- **Node.js**: 18+ (推荐 20 LTS)
- **npm**: 9+ (随 Node.js 安装)
- **Backend**: FastAPI server running at `http://localhost:8502` (default)

---

## Commands / 命令

```bash
# Install dependencies / 安装依赖
npm install

# Start dev server with hot reload / 启动开发服务器
npm run dev
# → http://localhost:5173

# Production build (TypeScript check + Vite build) / 生产构建
npm run build

# Preview production build / 预览生产构建
npm run preview
```

---

## Directory Structure / 目录结构

```
frontend/
├── src/
│   ├── pages/              # Route-level page components / 页面组件
│   │   ├── GeneratePage.tsx      # Main generation UI / 主生成界面
│   │   ├── SettingsPage.tsx      # API keys + model selection / 设置页
│   │   ├── KnowledgeBasePage.tsx # KB management / 知识库管理
│   │   ├── TemplateAnalysisPage.tsx # Template analyzer / 模板分析
│   │   ├── HistoryPage.tsx       # Generation history / 生成记录
│   │   ├── LoginPage.tsx         # Auth / 登录
│   │   ├── AdminPage.tsx         # Admin panel / 管理面板
│   │   └── HomePage.tsx          # Landing / 首页
│   ├── components/         # Reusable UI components / 可复用组件
│   ├── api.ts              # API client functions / 接口调用
│   ├── apiBase.ts          # API base URL resolution / 接口地址解析
│   ├── auth.tsx            # Auth context + JWT management / 认证上下文
│   ├── i18n.ts             # Internationalization (zh/en) / 国际化
│   ├── models.ts           # Data model types / 数据模型
│   ├── types.ts            # Shared TypeScript types / 类型定义
│   ├── hooks.ts            # Custom React hooks / 自定义 hooks
│   ├── workflow.tsx         # Generation workflow state / 生成流程状态
│   ├── App.tsx             # Root component + router / 根组件
│   └── main.tsx            # Entry point / 入口
├── public/                 # Static assets / 静态资源
├── vite.config.ts          # Vite config (dev proxy) / Vite 配置
├── tailwind.config.ts      # Tailwind CSS config / Tailwind 配置
├── tsconfig.json           # TypeScript config / TS 配置
├── package.json            # Dependencies / 依赖
└── .env.example            # Environment variables template / 环境变量模板
```

---

## Backend Connection / 后端连接

The frontend communicates with the FastAPI backend via REST and SSE.

前端通过 REST 和 SSE 与 FastAPI 后端通信。

**Development / 开发环境**: The Vite dev server proxies `/api` requests to the backend (default `http://localhost:8502`). No configuration needed if the backend runs on the default port.

**Production / 生产环境**: Set `VITE_API_BASE` to the backend origin:

```ini
# .env.local or .env.production
VITE_API_BASE=https://api.example.com
```

**Dev proxy target / 开发代理目标**: Override with `VITE_DEV_PROXY_TARGET`:

```ini
# .env.local
VITE_DEV_PROXY_TARGET=http://localhost:9000
```

See [.env.example](./.env.example) for all options.

---

## Internationalization / 国际化

The app supports Chinese (zh) and English (en). Language preference is stored per-user.

应用支持中文和英文。语言偏好按用户存储。

The `useI18n()` hook (from `src/i18n.ts`) provides translation functions:

```tsx
import { useI18n } from "./i18n";

function MyComponent() {
  const { t } = useI18n();
  return <h1>{t("app.name")}</h1>;
}
```

**Adding new strings / 添加新文案**: Edit `src/i18n.ts` and add entries to both the `zh` and `en` dictionaries. Use dot-notation keys grouped by feature area (e.g., `generate.title`, `settings.apiKey`).
