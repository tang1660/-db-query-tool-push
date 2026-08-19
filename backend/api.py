"""FastAPI 风格的 API 路由（基于标准库实现）。

保留原项目 API 契约：
  GET  /api/v1/dbs                       列出数据库连接
  POST /api/v1/dbs/{name}/query          执行 SQL
  POST /api/v1/dbs/{name}/query/natural  自然语言转 SQL
  GET  /api/v1/dbs/{name}/history        查询历史

新增（数据导出功能）：
  POST /api/v1/dbs/{name}/export         查询并导出（CSV/JSON 文件下载）
  POST /api/v1/dbs/{name}/query-and-export  一键：自然语言→SQL→查询→导出

同时提供：
  GET  /api/v1/metadata/{name}           表结构元数据
  GET  /health                           健康检查
"""
import json
import re
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, quote

from backend.database import CONNECTIONS, get_metadata
from backend.services.query import execute_query, get_query_history
from backend.services.nl2sql import generate_sql
from backend.services.exporter import export_query


def _send_json(handler: BaseHTTPRequestHandler, status: int, payload) -> None:
    body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.end_headers()
    handler.wfile.write(body)


def _send_file(handler: BaseHTTPRequestHandler, data: bytes, filename: str, media: str) -> None:
    handler.send_response(200)
    handler.send_header("Content-Type", media)
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header(
        "Content-Disposition",
        f'attachment; filename="{filename}"',
    )
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(data)


def _read_json(handler: BaseHTTPRequestHandler):
    length = int(handler.headers.get("Content-Length", 0))
    if length == 0:
        return {}
    raw = handler.rfile.read(length)
    return json.loads(raw.decode("utf-8"))


def dispatch(handler: BaseHTTPRequestHandler) -> bool:
    """处理 API 路由。返回 True 表示已处理，False 表示未命中。"""
    method = handler.command
    parsed = urlparse(handler.path)
    path = parsed.path.rstrip("/") or "/"
    parts = [p for p in path.split("/") if p]

    # CORS 预检
    if method == "OPTIONS":
        _send_json(handler, 204, {})
        return True

    # GET /health
    if method == "GET" and path == "/health":
        _send_json(handler, 200, {"status": "healthy", "version": "1.1.0"})
        return True

    # GET /api/v1/dbs
    if method == "GET" and parts == ["api", "v1", "dbs"]:
        _send_json(handler, 200, {"items": CONNECTIONS, "count": len(CONNECTIONS)})
        return True

    # /api/v1/dbs/{name}/... 与 /api/v1/metadata/{name}
    if len(parts) >= 4 and parts[0] == "api" and parts[1] == "v1":
        name = parts[3] if parts[2] == "dbs" else (parts[3] if parts[2] == "metadata" else None)
        # metadata
        if parts[2] == "metadata" and len(parts) == 4 and method == "GET":
            try:
                _send_json(handler, 200, get_metadata(name))
            except Exception as e:  # noqa: BLE001
                _send_json(handler, 500, {"detail": str(e)})
            return True

        if parts[2] != "dbs":
            return False
        if not _connection_exists(name):
            _send_json(handler, 404, {"detail": f"数据库连接 '{name}' 不存在"})
            return True

        # GET /api/v1/dbs/{name}/history
        if len(parts) == 5 and parts[4] == "history" and method == "GET":
            limit = _parse_query_int(parsed.query, "limit", 50)
            _send_json(handler, 200, get_query_history(name, limit))
            return True

        # POST /api/v1/dbs/{name}/query
        if len(parts) == 5 and parts[4] == "query" and method == "POST":
            body = _read_json(handler)
            sql = body.get("sql", "").strip()
            if not sql:
                _send_json(handler, 400, {"detail": "sql 不能为空"})
                return True
            try:
                result = execute_query(name, sql, source="MANUAL")
                _send_json(handler, 200, result)
            except Exception as e:  # noqa: BLE001
                _send_json(handler, 400, {"detail": str(e)})
            return True

        # POST /api/v1/dbs/{name}/query/natural
        if len(parts) == 6 and parts[4] == "query" and parts[5] == "natural" and method == "POST":
            body = _read_json(handler)
            prompt = body.get("prompt", "").strip()
            if not prompt:
                _send_json(handler, 400, {"detail": "prompt 不能为空"})
                return True
            try:
                metadata = get_metadata(name)
                gen = generate_sql(prompt, metadata)
                _send_json(handler, 200, gen)
            except Exception as e:  # noqa: BLE001
                _send_json(handler, 500, {"detail": str(e)})
            return True

        # POST /api/v1/dbs/{name}/export  （新增：查询并导出文件）
        if len(parts) == 5 and parts[4] == "export" and method == "POST":
            body = _read_json(handler)
            sql = body.get("sql", "").strip()
            fmt = (body.get("format") or "csv").lower()
            base_name = body.get("baseName") or "query_result"
            if not sql:
                _send_json(handler, 400, {"detail": "sql 不能为空"})
                return True
            if fmt not in ("csv", "json"):
                _send_json(handler, 400, {"detail": "format 仅支持 csv / json"})
                return True
            try:
                data, filename, media, meta = export_query(name, sql, fmt, base_name)
                # 通过 X-Export-Meta 头附带元信息，便于前端展示
                handler.send_response(200)
                handler.send_header("Content-Type", media)
                handler.send_header("Content-Length", str(len(data)))
                handler.send_header(
                    "Content-Disposition", f'attachment; filename="{filename}"'
                )
                handler.send_header("Access-Control-Allow-Origin", "*")
                handler.send_header(
                    "Access-Control-Expose-Headers", "Content-Disposition, X-Export-Meta"
                )
                # 对元信息做 URL 编码，避免非 ASCII 字符破坏 HTTP 头（前端用 decodeURIComponent 解码）
                handler.send_header("X-Export-Meta", quote(json.dumps(meta, ensure_ascii=False)))
                handler.end_headers()
                handler.wfile.write(data)
            except Exception as e:  # noqa: BLE001
                _send_json(handler, 400, {"detail": str(e)})
            return True

        # POST /api/v1/dbs/{name}/query-and-export （新增：一键 自然语言→SQL→查询→导出）
        if len(parts) == 5 and parts[4] == "query-and-export" and method == "POST":
            body = _read_json(handler)
            prompt = body.get("prompt", "").strip()
            fmt = (body.get("format") or "csv").lower()
            if not prompt:
                _send_json(handler, 400, {"detail": "prompt 不能为空"})
                return True
            if fmt not in ("csv", "json"):
                _send_json(handler, 400, {"detail": "format 仅支持 csv / json"})
                return True
            try:
                metadata = get_metadata(name)
                gen = generate_sql(prompt, metadata)
                sql = gen["sql"]
                data, filename, media, meta = export_query(name, sql, fmt, "nl_export")
                meta["generatedSql"] = sql
                meta["explanation"] = gen["explanation"]
                handler.send_response(200)
                handler.send_header("Content-Type", media)
                handler.send_header("Content-Length", str(len(data)))
                handler.send_header(
                    "Content-Disposition", f'attachment; filename="{filename}"'
                )
                handler.send_header("Access-Control-Allow-Origin", "*")
                handler.send_header(
                    "Access-Control-Expose-Headers", "Content-Disposition, X-Export-Meta"
                )
                # 对元信息做 URL 编码，避免非 ASCII 字符破坏 HTTP 头（前端用 decodeURIComponent 解码）
                handler.send_header("X-Export-Meta", quote(json.dumps(meta, ensure_ascii=False)))
                handler.end_headers()
                handler.wfile.write(data)
            except Exception as e:  # noqa: BLE001
                _send_json(handler, 400, {"detail": str(e)})
            return True

    return False


def _connection_exists(name: str) -> bool:
    return any(c["name"] == name for c in CONNECTIONS)


def _parse_query_int(query: str, key: str, default: int) -> int:
    for pair in query.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            if k == key:
                try:
                    return int(v)
                except ValueError:
                    return default
    return default
