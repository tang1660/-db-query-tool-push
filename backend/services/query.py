"""查询执行服务：对应原项目 app/services/query_wrapper.py。

职责：
- 执行 SQL 并将结果规范化为 {columns, rows, rowCount, executionTimeMs}
- 记录查询历史
"""
import time
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any

from backend.database import get_connection

# 查询历史（内存存储，对应原项目 QueryHistory 模型）
_history: list[dict[str, Any]] = []
_history_lock = threading.Lock()
_history_seq = 0

# 仅允许 SELECT 类查询，避免破坏内存示例数据
def _is_read_only(sql: str) -> bool:
    s = sql.strip().lower()
    return s.startswith("select") or s.startswith("with")


def execute_query(name: str, sql: str, source: str = "MANUAL") -> dict[str, Any]:
    """执行 SQL 查询，返回规范化结果。

    Args:
        name: 数据库连接名
        sql: 待执行的 SQL
        source: 查询来源 MANUAL / NATURAL_LANGUAGE

    Returns:
        {columns, rows, rowCount, executionTimeMs, sql}
    """
    global _history_seq
    conn = get_connection()
    start = time.perf_counter()
    success = True
    error_message = None
    columns: list[str] = []
    rows: list[list[Any]] = []
    row_count = 0

    try:
        if not _is_read_only(sql):
            raise ValueError("为安全起见，仅允许执行 SELECT / WITH 查询。")

        cur = conn.cursor()
        cur.execute(sql)
        columns = [desc[0] for desc in cur.description] if cur.description else []
        fetched = cur.fetchall()
        rows = [list(r) for r in fetched]
        row_count = len(rows)
    except Exception as e:  # noqa: BLE001
        success = False
        error_message = str(e)
    finally:
        elapsed = int((time.perf_counter() - start) * 1000)

    with _history_lock:
        _history_seq += 1
        _history.append(
            {
                "id": _history_seq,
                "databaseName": name,
                "sqlText": sql,
                "executedAt": datetime.now(timezone.utc).isoformat(),
                "executionTimeMs": elapsed,
                "rowCount": row_count,
                "success": success,
                "errorMessage": error_message,
                "querySource": source,
            }
        )
        # 仅保留最近 100 条
        if len(_history) > 100:
            del _history[: len(_history) - 100]

    if not success:
        raise RuntimeError(error_message or "查询执行失败")

    return {
        "columns": columns,
        "rows": rows,
        "rowCount": row_count,
        "executionTimeMs": elapsed,
        "sql": sql,
    }


def get_query_history(name: str, limit: int = 50) -> list[dict[str, Any]]:
    """获取指定数据库的查询历史。"""
    with _history_lock:
        items = [h for h in _history if h["databaseName"] == name]
    items = list(reversed(items))[:limit]
    return items
