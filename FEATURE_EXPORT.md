# FEATURE_EXPORT.md — 数据导出功能设计思路

> 本文档描述在「智能数据库查询工具」（源自 `geektime-bootcamp-ai/w2/db_query`）基础上新增「数据导出功能模块」的设计思路、切入点、AI Agent 任务分解与工具链整合方案。

## 一、设计目标

在已有「连接管理 + SQL 查询 + 自然语言转 SQL（NL2SQL）」能力之上，新增数据导出能力，使「执行查询」与「导出结果」可以一键完成或通过简单命令触发，并通过自然语言/界面操作触发导出。

对应作业的三条硬性要求：

1. **导出格式支持**：支持至少两种导出格式（CSV、JSON）。
2. **自动化流程**：利用 Claude Code 的 Agent / 自定义 Command 能力，使「执行查询」与「导出结果」可一键完成或通过简单命令触发。
3. **用户交互**：通过自然语言或简单界面操作触发导出（查询后 AI 主动询问是否导出为 CSV / JSON）。

## 二、代码库理解与切入点选择

### 2.1 原项目结构理解

原项目为前后端分离架构：

```
w2/db_query/
├── backend/                    # FastAPI (Python 3.12+)
│   └── app/
│       ├── main.py             # 应用入口，注册 routers
│       ├── database.py         # 连接与会话
│       ├── api/v1/
│       │   ├── databases.py    # GET  /api/v1/dbs
│       │   └── queries.py      # POST /api/v1/dbs/{name}/query
│       │                       # POST /api/v1/dbs/{name}/query/natural
│       │                       # GET  /api/v1/dbs/{name}/history
│       └── services/           # query_wrapper / nl2sql / metadata / sql_validator
└── frontend/                   # React + Refine 5 (TypeScript)
```

核心数据契约（关键切入点）：

- 查询结果 `QueryResult` 的结构为 `{ columns, rows, rowCount, executionTimeMs }`。
- NL2SQL 返回 `{ sql, explanation }`。

### 2.2 切入点决策

「导出」本质是对「查询结果」的二次加工，因此最合适的切入点是 **复用查询服务产出的 `{columns, rows}`**，而不是重新实现查询。这样：

- 不侵入原有查询逻辑，保持向后兼容；
- 导出与查询共享同一份结果源，保证数据一致；
- 易于接入「自然语言 → SQL → 查询 → 导出」的一键链路。

> 因此导出服务在 `backend/services/exporter.py` 中直接调用 `query.execute_query()`，形成"获取查询结果 → 格式化数据 → 创建文件"的三段式编排。

## 三、功能架构

### 3.1 模块划分

```
backend/
├── database.py                  # 内存 SQLite + 示例数据 + 元数据（替代 PostgreSQL，便于离线运行）
├── api.py                       # 路由分发（保留原 API 契约 + 新增导出端点）
├── server.py                    # HTTP 入口（同时托管前端静态资源）
└── services/
    ├── query.py                 # 查询执行 + 历史（对应原 query_wrapper）
    ├── nl2sql.py                # 规则式 NL2SQL（替代 OpenAI，便于离线演示 AI 交互）
    └── exporter.py              # 【新增】数据导出服务（CSV/JSON）
```

### 3.2 导出服务内部结构（AI Agent 子任务分解）

`exporter.py` 将"导出数据"显式分解为三个子任务，并对外暴露 `export_query()` 进行编排：

| 子任务 | 函数 | 职责 |
| --- | --- | --- |
| ① 获取查询结果 | `fetch_result(name, sql)` | 复用查询服务执行 SQL，返回 `{columns, rows, rowCount}` |
| ② 格式化数据 | `format_data(result, fmt)` | 将结构化结果转为 CSV（RFC4180）或 JSON（对象数组 + 元信息） |
| ③ 创建文件 | `build_file(content, fmt)` | 生成文件字节、文件名、Content-Type，附 BOM 以兼容 Excel 打开 CSV |

```python
def export_query(name, sql, fmt, base_name):
    result = fetch_result(name, sql)                         # ① 获取查询结果
    content = format_data(result, fmt)                      # ② 格式化数据
    data, filename, media = build_file(content, fmt, base_name)  # ③ 创建文件
    return data, filename, media, meta
```

这种"分解 + 编排"的结构，正是为了在 Claude Code Agent 场景下让 Agent 能清晰感知并协调各子任务（见第五节）。

### 3.3 新增 API 端点

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/v1/dbs/{name}/export` | 【新增】执行 SQL 并导出为 CSV/JSON 文件 |
| POST | `/api/v1/dbs/{name}/query-and-export` | 【新增】一键：自然语言 → SQL → 查询 → 导出 |

- 请求体：`{ sql | prompt, format: "csv"|"json", baseName? }`
- 响应：文件流（`Content-Disposition: attachment`），并通过 `X-Export-Meta` 头附带元信息（行数、字节数、文件名、生成的 SQL、AI 解释），便于前端展示。

原有端点完全保留：

- `GET  /api/v1/dbs`
- `POST /api/v1/dbs/{name}/query`
- `POST /api/v1/dbs/{name}/query/natural`
- `GET  /api/v1/dbs/{name}/history`
- `GET  /api/v1/metadata/{name}`
- `GET  /health`

## 四、格式化设计

### 4.1 CSV

- 首行为列名，其后为数据行；
- 使用 `csv.writer(quoting=QUOTE_MINIMAL, lineterminator="\r\n")`，遵循 RFC4180，正确处理逗号/引号/换行；
- 编码 `utf-8-sig`（带 BOM），保证 Excel 直接双击打开中文不乱码。

### 4.2 JSON

```json
{
  "meta": { "format": "json", "rowCount": 5, "columns": ["department", "employee_count"] },
  "data": [ { "department": "研发部", "employee_count": 3 }, ... ]
}
```

- 以对象数组承载数据，附带 `meta` 元信息，便于下游程序消费。

## 五、AI Agent 任务分解（Claude Code 视角）

在 Claude Code 中，"导出数据"被分解为可被 Agent 协调的子任务，对应一个自定义 Command 的执行步骤：

```
/export <format> <natural language>
  ├─ Step 1  获取查询结果   — 调用 query.execute_query()
  ├─ Step 2  格式化数据     — exporter.format_data(result, fmt)
  └─ Step 3  创建文件       — exporter.build_file(...)
```

**自动化一键流程**（`POST /query-and-export`）进一步把 NL2SQL 串入：

```
自然语言 ──nl2sql──▶ SQL ──execute──▶ 结果 ──format──▶ 文件 ──下载
```

前端「一键查询并导出」页面通过日志流式展示 Agent 各子任务的执行与衔接（进行中 / 完成 / 失败），便于观察"Agent 协调处理过程"。

## 六、用户交互设计

满足"通过自然语言或简单界面操作触发导出"：

1. **SQL 查询页**：执行查询后，结果区下方出现醒目的「导出 CSV / 导出 JSON」按钮条。
2. **自然语言查询页**：AI 完成 NL→SQL→执行后，在对话气泡内**主动询问**「是否导出结果？」，并直接提供「导出 CSV / 导出 JSON」按钮。
3. **一键查询并导出页**：输入自然语言 + 选择格式 + 单击按钮，即可走完"生成 SQL → 查询 → 导出"全流程并下载文件。

## 七、工具链整合（Cursor + Claude Code）

| 环节 | 工具 | 作用 |
| --- | --- | --- |
| 快速理解代码库 | Cursor | 用 AI 快速通读原 `queries.py` / `query_wrapper`，定位 `QueryResult` 契约，找到切入点 |
| 代码生成与快速迭代 | Cursor | 生成导出服务、前端导出 UI、CSS 等，快速试错 |
| 多步骤自动化 | Claude Code Agent | 将"导出数据"分解为"获取查询结果 / 格式化数据 / 创建文件"，并编排一键流程；通过自定义 Command 触发 |
| 一键可演示 | 标准库自托管后端 | 后端同时托管前端，单命令启动，便于功能截图 |

## 八、安全与边界

- 仅允许 `SELECT / WITH` 类查询进入导出流程，避免破坏数据（`query.py: _is_read_only`）。
- 导出文件名使用时间戳避免覆盖，并做 `Content-Disposition` 转义。
- 查询结果通过 `X-Export-Meta` 头回传元信息，不污染文件正文。

## 九、可运行性说明

为保证作业可被快速验证与截图，本项目以 Python 标准库自包含运行（无需 PostgreSQL / OpenAI Key / Node），并保留与原项目一致的 API 契约与目录组织：

```bash
python backend/server.py
# 访问 http://localhost:8000
```

详见根目录 `README.md`。
