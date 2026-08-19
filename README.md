# 智能数据库查询工具（含数据导出功能）

基于 [geektime-bootcamp-ai/w2/db_query](https://github.com/tyrchen/geektime-bootcamp-ai/tree/master/w2/db_query) 扩展，新增**数据导出功能模块**。

## 功能亮点

- **数据库查询**：执行 SQL，结果以表格展示（保留原 `/api/v1/dbs/{name}/query` 契约）。
- **自然语言查询**：AI 助手将自然语言翻译为 SQL 并执行（规则式 NL2SQL，离线可运行）。
- **数据导出（新增）**：支持 **CSV** 与 **JSON** 两种格式，一键下载。
- **一键查询并导出（新增自动化）**：自然语言 → SQL → 查询 → 导出，单命令完成。
- **AI 主动询问**：自然语言查询完成后，AI 主动询问是否导出为 CSV / JSON。

## 快速开始

> 仅需 Python 3.10+，无需安装任何第三方库、无需 PostgreSQL / OpenAI Key。

```bash
python backend/server.py
```

浏览器访问：**http://localhost:8000**

健康检查：http://localhost:8000/health

## 目录结构

```
db_query_export/
├── backend/
│   ├── server.py            # 入口：HTTP 服务 + 静态资源托管
│   ├── api.py               # 路由分发（原契约 + 新增导出端点）
│   ├── database.py          # 内存 SQLite + 示例数据 + 元数据
│   └── services/
│       ├── query.py         # 查询执行 + 历史
│       ├── nl2sql.py        # 自然语言 → SQL
│       └── exporter.py      # 【新增】数据导出（CSV/JSON）
├── frontend/
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── FEATURE_EXPORT.md        # 新增功能设计思路文档（作业提交物）
└── README.md
```

## API 一览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET  | `/api/v1/dbs` | 列出数据库连接 |
| POST | `/api/v1/dbs/{name}/query` | 执行 SQL |
| POST | `/api/v1/dbs/{name}/query/natural` | 自然语言转 SQL |
| GET  | `/api/v1/dbs/{name}/history` | 查询历史 |
| POST | `/api/v1/dbs/{name}/export` | **新增** 执行 SQL 并导出 CSV/JSON |
| POST | `/api/v1/dbs/{name}/query-and-export` | **新增** 一键：自然语言→SQL→查询→导出 |

## 示例数据表

内置示例库（`company_db` / `sales_db`）：`departments`、`employees`、`products`、`orders`。

可尝试的自然语言：

- 统计每个部门的员工数量
- 查询薪水大于 20000 的员工
- 查询价格低于 300 的商品
- 按状态统计订单数量

## 设计思路

详见 [FEATURE_EXPORT.md](./FEATURE_EXPORT.md)。
