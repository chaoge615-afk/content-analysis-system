## 系列文章目录

[B站视频内容智能分析系统（一）：项目介绍与架构设计](./01-项目介绍与架构设计.md)
[B站视频内容智能分析系统（二）：Docker Compose 一键部署](./02-Docker-Compose一键部署.md)
[B站视频内容智能分析系统（三）：B站视频自动采集](./03-B站视频自动采集.md)
[B站视频内容智能分析系统（四）：语音转写三级回退](./04-语音转写三级回退.md)
[B站视频内容智能分析系统（五）：LLM 内容精炼与多域分类](./05-LLM内容精炼与分类.md)
[B站视频内容智能分析系统（六）：Text-to-SQL 结构化查询](./06-Text-to-SQL结构化查询.md)
[B站视频内容智能分析系统（七）：RAG 语义检索](./07-RAG语义检索.md)
[B站视频内容智能分析系统（八）：Router Agent 智能路由](./08-Router-Agent智能路由.md)
B站视频内容智能分析系统（九）：React 前端与管理面板


### 文章目录

+ [系列文章目录](#_0)
+ [前言](#前言)
+ [一、整体架构](#一整体架构)
    + [1. 技术栈](#1-技术栈)
    + [2. 双视图设计](#2-双视图设计)
    + [3. 组件清单](#3-组件清单)
+ [二、对话视图](#二对话视图)
    + [1. 消息组件](#1-消息组件)
    + [2. 路由标签](#2-路由标签)
    + [3. SQL 和来源展示](#3-sql-和来源展示)
+ [三、斜杠命令](#三斜杠命令)
    + [1. 命令列表](#1-命令列表)
    + [2. 结构化展示](#2-结构化展示)
+ [四、管理面板](#四管理面板)
    + [1. 采集触发](#1-采集触发)
    + [2. Cookie 管理](#2-cookie-管理)
    + [3. GPU 转录](#3-gpu-转录)
    + [4. 查询日志](#4-查询日志)
    + [5. 服务监控](#5-服务监控)
+ [五、UP主管理](#五up主管理)
    + [1. 添加 UP主](#1-添加-up主)
    + [2. 导入导出](#2-导入导出)
+ [六、Nginx 反向代理](#六nginx-反向代理)
+ [七、Docker SDK 容器触发](#七docker-sdk-容器触发)
+ [总结](#总结)




## 前言

前面八篇把后端的采集、转写、精炼、查询、路由全部讲完了。这篇来讲用户直接看到的部分——React 前端和管理面板。

前端的设计目标是**一个页面搞定所有事**：既能自然语言问答，又能管理采集任务、查看系统状态。所以我做了双视图设计——顶部 Tab 切换"对话"和"管理面板"，不需要页面跳转。


## 一、整体架构

### 1. 技术栈

```
React 18 + TypeScript + Tailwind CSS + Vite
```

- **React 18**：函数组件 + Hooks，没用 Redux（状态不复杂）
- **TypeScript**：类型安全，API 响应有明确的 interface 定义
- **Tailwind CSS**：原子化 CSS，写样式快
- **Vite**：开发服务器 + 构建，HMR 秒级刷新
- **Axios**：HTTP 请求，2 分钟超时（LLM 查询可能很慢）

### 2. 双视图设计

```
┌──────────────────────────────────────────┐
│  智能内容分析系统     [对话] [管理面板]     │
├──────────────────────────────────────────┤
│                                          │
│  对话视图                  管理面板视图    │
│  ┌────────────┬────────┐  ┌────────────┐ │
│  │            │  侧    │  │ [采集]     │ │
│  │  聊天区域  │  边    │  │ [GPU转录]  │ │
│  │            │  栏    │  │ [查询日志] │ │
│  ├────────────┤        │  │ [服务监控] │ │
│  │  输入框    │        │  │            │ │
│  └────────────┴────────┘  └────────────┘ │
└──────────────────────────────────────────┘
```

状态管理很简单，一个 `activeTab` 控制显示哪个视图：

```tsx
type MainTab = 'chat' | 'admin';
const [activeTab, setActiveTab] = useState<MainTab>('chat');
```

### 3. 组件清单

| 组件 | 职责 |
|------|------|
| `App.tsx` | 应用外壳，Tab 切换 + 侧边栏 |
| `ChatInput` | 输入框，支持斜杠命令和域选择 |
| `ChatMessage` | 消息气泡，路由标签 + SQL + 推理 + 来源 |
| `QuickView` | 斜杠命令结果的结构化展示 |
| `StatusPanel` | 右侧边栏（数据概览 + 快捷问题 + 状态） |
| `AdminPanel` | 管理面板容器，4 个子 Tab |
| `MonitorTrigger` | 采集触发 + Cookie 管理 |
| `UpManager` | UP主添加/删除/列表 |
| `GpuTranscribe` | GPU 转录 + 云 ASR 转写 |
| `QueryLog` | 查询日志分页列表 |
| `SystemMetrics` | 服务监控仪表盘 |


## 二、对话视图

### 1. 消息组件

每条消息是一个 `ChatMessage` 组件，支持展示多种信息：

```tsx
interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;            // Markdown 格式的回答
  routeType?: string;         // structured | semantic | hybrid
  sql?: string;               // SQL 语句（可展开）
  sqlResult?: any[];          // SQL 查询结果（表格）
  reasoning?: string;         // 推理过程（可折叠）
  responseTime?: number;      // 响应时间
  sources?: SourceItem[];     // 来源引用
  quickView?: { ... };        // 斜杠命令结果
}
```

### 2. 路由标签

每条 AI 回答前面有一个彩色标签，标识走了哪个通道：

```tsx
// 路由标签颜色
const routeColors = {
  structured: 'bg-blue-100 text-blue-800',   // 蓝色
  semantic: 'bg-green-100 text-green-800',   // 绿色
  hybrid: 'bg-purple-100 text-purple-800',   // 紫色
};

const routeLabels = {
  structured: '结构化',
  semantic: '语义',
  hybrid: '混合',
};
```

用户可以一眼看出这个问题的回答来自哪个通道。

### 3. SQL 和来源展示

结构化查询会展示 SQL 语句和查询结果表格：

```tsx
{message.sql && (
  <details className="mt-2">
    <summary className="cursor-pointer text-xs text-gray-500">
      查看 SQL
    </summary>
    <pre className="mt-1 p-2 bg-gray-50 rounded text-xs overflow-x-auto">
      {message.sql}
    </pre>
  </details>
)}

{message.sqlResult && (
  <ResultTable data={message.sqlResult} />
)}
```

语义查询会展示来源引用（来自哪些视频）：

```tsx
{message.sources && message.sources.length > 0 && (
  <div className="mt-2 text-xs text-gray-500">
    来源：{message.sources.map(s =>
      `[${s.up_name}] ${s.title}`
    ).join(', ')}
  </div>
)}
```

[截图：对话界面展示一个混合查询——紫色 hybrid 标签 + 自然语言回答 + 可折叠 SQL + 来源引用]


## 三、斜杠命令

### 1. 命令列表

输入框支持以 `/` 开头的快捷命令：

| 命令 | 功能 |
|------|------|
| `/status` | 系统状态（Router / SQL / RAG 可用性） |
| `/up_list` | 所有 UP主列表及视频数 |
| `/recent` | 最近采集的 10 个视频 |
| `/categories` | 31 个情感分类统计 |
| `/sql [问题]` | 强制走 Text-to-SQL |
| `/rag [问题]` | 强制走 RAG |
| `/clear` | 清空对话 |
| `/help` | 显示帮助 |

处理逻辑：

```tsx
const handleSend = async (input: string) => {
  if (input.startsWith('/')) {
    const response = await handleSlashCommand(input);
    setMessages(prev => [...prev, response]);
  } else {
    const result = await chat(input);
    // ...
  }
};
```

### 2. 结构化展示

斜杠命令的结果不是普通文本，而是通过 `QuickView` 组件做结构化展示：

- `/status`：三色状态卡片（绿=正常、红=异常、灰=未知）
- `/up_list`：UP主卡片列表（头像 + 名称 + 视频数）
- `/recent`：视频列表（标题 + UP主 + 分类标签 + 时长）
- `/categories`：水平条形图（分类名 + 视频数 + 百分比）

```tsx
// /categories 条形图
{categories.map(cat => (
  <div key={cat.name} className="flex items-center gap-2">
    <span className="w-20 text-xs text-right">{cat.name}</span>
    <div className="flex-1 bg-gray-100 rounded-full h-4">
      <div
        className="bg-blue-500 h-4 rounded-full"
        style={{ width: `${(cat.count / max) * 100}%` }}
      />
    </div>
    <span className="text-xs w-12">{cat.count}</span>
  </div>
))}
```

[截图：斜杠命令 /categories 的效果——水平条形图展示各分类的视频数量]


## 四、管理面板

### 1. 采集触发

管理面板的第一个 Tab 是采集触发，主要功能：

- **状态指示器**：显示采集状态（空闲/运行中/完成/失败）
- **UP主多选**：下拉选择要采集的 UP主
- **参数设置**：最大视频数、全量扫描复选框
- **触发按钮**：一键启动采集
- **实时日志**：终端风格的日志窗口，运行中每 5 秒自动刷新

```tsx
// 运行中时自动轮询
useEffect(() => {
  if (status?.status === 'running') {
    pollRef.current = setInterval(fetchStatus, 5000);
  }
  return () => {
    if (pollRef.current) clearInterval(pollRef.current);
  };
}, [status?.status]);
```

[截图：采集触发页面——状态指示器（蓝色脉冲）、UP主多选下拉、全量扫描复选框、实时日志窗口]

### 2. Cookie 管理

B站 Cookie 管理是可折叠的面板：

- **保存 Cookie**：粘贴 Netscape 格式的内容
- **测试 Cookie**：调用 B站 API 验证有效性
- **删除 Cookie**：清除已保存的 Cookie

状态灯指示 Cookie 状态：
- 🟢 已配置 + 有效
- 🔴 已过期
- 🔴 未配置

```tsx
// Cookie 状态灯
<div className={`w-3 h-3 rounded-full ${
  cookieValid ? 'bg-green-500' : 'bg-red-500'
} ${isRunning ? 'animate-pulse' : ''}`} />
```

采集前会自动预检 Cookie，如果未配置或已过期，采集按钮会被禁用。

### 3. GPU 转录

分成两个区域：

**GPU 转录（开发机）**：
- GPU 状态卡片（CUDA 可用性、显存、PyTorch 版本）
- 模型/设备选择
- 进度条 + 实时日志

**云 ASR 转写（NAS）**：
- 开关控制（启用/禁用 ASR）
- 月度预算设置 + 用量进度条
- 手动触发按钮
- 最近转写记录

### 4. 查询日志

展示所有历史查询记录：

- **统计卡片**：总查询数、平均响应时间、各路由类型分布
- **查询表格**：问题、路由类型（彩色标签）、响应时间、查询时间
- **过滤 + 分页**：按路由类型过滤，每页 15 条

### 5. 服务监控

实时展示各容器的运行状态：

- **容器状态卡片**：状态灯 + 内存使用进度条 + CPU 使用率 + 端口
- **知识库指标**：向量文档块数、视频总数、总查询数
- **查询类型分布**：水平条形图（结构化/语义/混合占比）

自动刷新（默认 30 秒），也可以手动刷新。

[截图：服务监控页面——6个容器状态卡片 + 知识库指标 + 查询分布条形图]


## 五、UP主管理

### 1. 添加 UP主

在采集触发页面底部，可以添加新的 UP主：

1. 粘贴 B站链接（主页链接或视频链接）
2. 选择 Whisper 模型（small / medium）
3. 选择内容域（情感 / 求职）
4. 点击"解析"→ 展示预览卡片
5. 点击"确认添加"→ 生成 YAML 配置

```
支持两种链接格式：
- 主页：https://space.bilibili.com/<uid>
- 视频：https://www.bilibili.com/video/<bvid>
```

后端会调 B站 API 获取 UP主 信息（名称、UID、头像），前端展示预览卡片让用户确认。

### 2. 导入导出

UP主数据支持 ZIP 打包导入导出：

**导出**：把所有 UP主 的配置 + 元数据 + 向量 + 转写文本打包成 ZIP
**导入**：上传 ZIP 文件，一键恢复所有 UP主 数据

这个功能用于跨环境迁移——在开发机上采集的数据，打包后导入到 NAS：

```
导出 ZIP 内容：
├── configs/          # UP主 YAML 配置
├── metadata/         # DuckDB 导出的元数据
├── transcripts/      # 转写文本文件
└── manifest.json     # 版本和校验信息
```

Nginx 配置了 `client_max_body_size 500m`，支持大文件上传。


## 六、Nginx 反向代理

前端容器同时承担 Nginx 反向代理的职责。所有 API 请求都通过 Nginx 转发到后端：

```nginx
# /api/ → Router Agent
location /api/ {
    client_max_body_size 500m;
    set $upstream_router http://router-agent:8000;
    proxy_pass $upstream_router;
    proxy_read_timeout 120s;
}

# /query → Text-to-SQL（向后兼容）
location /query {
    set $upstream_t2s http://text-to-sql:8010;
    proxy_pass $upstream_t2s;
}

# 静态资源缓存 1 年
location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

关键配置：
- **`resolver 127.0.0.11`**：Docker 内置 DNS，用变量避免容器重建后 IP 变化导致 502
- **`client_max_body_size 500m`**：支持 UP主导入的大文件上传
- **`proxy_read_timeout 120s`**：LLM 查询可能需要较长时间

API 层（`api.ts`）的超时也配合设置为 2 分钟：

```typescript
const api = axios.create({
  baseURL: '/api',
  timeout: 120000,  // 2分钟（LLM 查询可能很慢）
});
```


## 七、Docker SDK 容器触发

前端触发采集不是直接调 bilibili-monitor 的 API（它是批处理容器，没有常驻 API），而是通过 Router Agent 的 Docker SDK 动态启动新容器：

```
前端 POST /api/trigger_monitor {up_names: ["桃姐"], full_scan: true}
  ↓
Router Agent（monitor_trigger.py）
  ↓ Docker SDK
  docker run --rm content-analysis-system-bilibili-monitor \
    python src/monitor_all.py --up 桃姐 --full-scan
  ↓
前端 GET /api/trigger_status（每5秒轮询）
  → {status: "running", logs: [...]}
  → {status: "completed", exit_code: 0}
```

Router Agent 挂载了 Docker socket（`/var/run/docker.sock`），所以可以在容器内控制宿主机的 Docker daemon。

前端的轮询逻辑：

```tsx
useEffect(() => {
  if (status?.status === 'running') {
    pollRef.current = setInterval(fetchStatus, 5000);
  } else {
    if (pollRef.current) clearInterval(pollRef.current);
  }
  return () => {
    if (pollRef.current) clearInterval(pollRef.current);
  };
}, [status?.status]);
```

运行中时 5 秒轮询一次，完成后停止轮询。日志窗口自动滚动到最新行。

[截图：采集运行中的实时日志——深色背景、绿色字体、终端风格]


## 总结

前端用 React + TypeScript + Tailwind CSS 构建，双视图设计（对话 + 管理面板）让用户在一个页面内完成所有操作。对话视图支持自然语言问答和斜杠命令，每条回答附带路由标签、SQL 语句和来源引用。管理面板集成了采集触发、Cookie 管理、GPU 转录、查询日志和服务监控。Nginx 反向代理统一转发 API 请求，Docker SDK 实现容器的动态触发。下一篇是这个系列的最后一篇——踩坑记录与性能优化。
