"""数据导出服务（新增功能）。

对应任务要求：在 Claude Code 中将"导出数据"分解为以下子任务，由 Agent 协调处理：
  1. 获取查询结果   -> fetch_result()
  2. 格式化数据     -> format_data()
  3. 创建文件       -> build_file()

对外暴露 export_query() 编排上述三个子任务，实现"执行查询 + 导出结果"的一键完成。
支持格式：CSV、JSON（满足"至少两种导出格式"的硬性要求）。
"""
import csv
import io
import json
from typing import Any, Literal

from backend.services.query import execute_query

ExportFormat = Literal["csv", "json"]


def fetch_result(name: str, sql: str) -> dict[str, Any]:
    """子任务 1：获取查询结果。

    复用查询服务执行 SQL，返回 columns / rows / rowCount。
    """
    result = execute_query(name, sql, source="EXPORT")
    return {
        "columns": result["columns"],
        "rows": result["rows"],
        "rowCount": result["rowCount"],
    }


def format_data(result: dict[str, Any], fmt: ExportFormat) -> str:
    """子任务 2：格式化数据。

    将 {columns, rows} 转换为 CSV 或 JSON 字符串。
    - CSV：首行列头，后续为数据行；逗号/引号/换行按 RFC4180 处理。
    - JSON：以对象数组形式输出，并附带元信息。
    """
    columns = result["columns"]
    rows = result["rows"]

    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
        writer.writerow(columns)
        for row in rows:
            writer.writerow(["" if v is None else v for v in row])
        return buf.getvalue()

    if fmt == "json":
        records = [dict(zip(columns, row)) for row in rows]
        payload = {
            "meta": {
                "format": "json",
                "rowCount": result["rowCount"],
                "columns": columns,
            },
            "data": records,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    raise ValueError(f"不支持的导出格式：{fmt}（仅支持 csv / json）")


def build_file(content: str, fmt: ExportFormat, base_name: str = "query_result") -> tuple[bytes, str, str]:
    """子任务 3：创建文件。

    返回 (文件字节, 文件名, Content-Type)，供 HTTP 响应直接使用。
    """
    ext = "csv" if fmt == "csv" else "json"
    filename = f"{base_name}_{__timestamp()}.{ext}"
    media = "text/csv" if fmt == "csv" else "application/json"
    data = content.encode("utf-8-sig" if fmt == "csv" else "utf-8")
    return data, filename, media


def export_query(
    name: str,
    sql: str,
    fmt: ExportFormat,
    base_name: str = "query_result",
) -> tuple[bytes, str, str, dict[str, Any]]:
    """编排：一键完成"查询 + 导出"。

    Returns:
        (文件字节, 文件名, Content-Type, 导出元信息)
    """
    # —— Agent 子任务编排 ——
    result = fetch_result(name, sql)          # 1. 获取查询结果
    content = format_data(result, fmt)        # 2. 格式化数据
    data, filename, media = build_file(content, fmt, base_name)  # 3. 创建文件

    meta = {
        "format": fmt,
        "filename": filename,
        "contentType": media,
        "rowCount": result["rowCount"],
        "byteSize": len(data),
        "sql": sql,
    }
    return data, filename, media, meta


def __timestamp() -> str:
    import datetime as _dt
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
