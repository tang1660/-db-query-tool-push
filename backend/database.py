"""内存数据库：基于 SQLite，内置示例数据，模拟 PostgreSQL 数据源。

对应原项目 backend/app/database.py 与 metadata 的职责：
- 提供连接与会话
- 提供表结构元数据（供 NL2SQL 生成 SQL 时作为上下文）
"""
import sqlite3
import threading
import json
from typing import Any

# 全局内存数据库连接（线程安全通过锁保证）
_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

# 模拟的数据库连接（对应原项目 DatabaseConnection 模型）
CONNECTIONS = [
    {
        "name": "company_db",
        "dbType": "postgresql",
        "description": "公司业务主库（员工/部门/商品/订单）",
        "host": "mock-localhost",
        "port": 5432,
        "databaseName": "company_db",
    },
    {
        "name": "sales_db",
        "dbType": "postgresql",
        "description": "销售分析库（订单与商品）",
        "host": "mock-localhost",
        "port": 5432,
        "databaseName": "sales_db",
    },
]


def _build_mock_schema(conn: sqlite3.Connection) -> None:
    """建表并写入示例数据。"""
    c = conn.cursor()
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            manager TEXT,
            location TEXT,
            budget REAL
        );

        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            department TEXT,
            position TEXT,
            salary REAL,
            hire_date TEXT
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT,
            price REAL,
            stock INTEGER,
            supplier TEXT
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY,
            customer TEXT NOT NULL,
            product_id INTEGER,
            quantity INTEGER,
            total REAL,
            order_date TEXT,
            status TEXT
        );
        """
    )

    # 仅在表为空时灌入示例数据
    if c.execute("SELECT COUNT(*) FROM departments").fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO departments VALUES (?,?,?,?,?)",
            [
                (1, "研发部", "张伟", "北京", 5000000),
                (2, "市场部", "李娜", "上海", 3000000),
                (3, "财务部", "王强", "北京", 2000000),
                (4, "人事部", "刘洋", "深圳", 1500000),
                (5, "销售部", "陈静", "广州", 4000000),
            ],
        )
    if c.execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO employees VALUES (?,?,?,?,?,?)",
            [
                (1, "赵敏", "研发部", "高级工程师", 28000, "2020-03-15"),
                (2, "孙杰", "研发部", "技术专家", 35000, "2018-07-01"),
                (3, "周婷", "市场部", "市场经理", 22000, "2019-11-20"),
                (4, "吴磊", "市场部", "市场专员", 14000, "2021-05-10"),
                (5, "郑爽", "财务部", "财务主管", 26000, "2017-09-01"),
                (6, "冯雪", "财务部", "会计", 13000, "2022-02-14"),
                (7, "褚明", "人事部", "HR经理", 20000, "2019-04-08"),
                (8, "卫华", "人事部", "招聘专员", 12000, "2023-01-03"),
                (9, "蒋涛", "销售部", "销售总监", 40000, "2016-06-18"),
                (10, "沈丽", "销售部", "销售代表", 16000, "2021-08-25"),
                (11, "韩鹏", "销售部", "销售代表", 15500, "2022-03-30"),
                (12, "杨柳", "研发部", "初级工程师", 18000, "2023-07-01"),
            ],
        )
    if c.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO products VALUES (?,?,?,?,?,?)",
            [
                (1, "机械键盘 K8", "外设", 599, 120, "极客外设"),
                (2, "人体工学椅 E1", "办公家具", 1899, 45, "舒适家"),
                (3, "4K 显示器 27寸", "显示设备", 2199, 60, "视界科技"),
                (4, "无线鼠标 M3", "外设", 159, 300, "极客外设"),
                (5, "USB-C 扩展坞", "配件", 269, 88, "极客外设"),
                (6, "降噪耳机 N5", "音频设备", 1299, 70, "声学未来"),
                (7, "智能台灯 L2", "照明", 399, 150, "舒适家"),
                (8, "固态硬盘 1TB", "存储", 799, 200, "存储之星"),
            ],
        )
    if c.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO orders VALUES (?,?,?,?,?,?,?)",
            [
                (1, "北京科技公司", 1, 10, 5990, "2024-01-15", "已完成"),
                (2, "上海设计院", 2, 5, 9495, "2024-01-18", "已完成"),
                (3, "深圳媒体", 3, 8, 17592, "2024-02-02", "已完成"),
                (4, "广州工作室", 4, 50, 7950, "2024-02-10", "已发货"),
                (5, "成都游戏公司", 6, 3, 3897, "2024-02-20", "已发货"),
                (6, "杭州研究院", 8, 12, 9588, "2024-03-01", "已完成"),
                (7, "北京科技公司", 5, 20, 5380, "2024-03-12", "处理中"),
                (8, "武汉高校", 7, 30, 11970, "2024-03-25", "已完成"),
                (9, "南京设计公司", 1, 15, 8985, "2024-04-05", "已发货"),
                (10, "上海设计院", 8, 6, 4794, "2024-04-15", "处理中"),
            ],
        )
    conn.commit()


def init_db() -> None:
    """初始化内存数据库（对应原项目 init_db）。"""
    global _conn
    with _lock:
        if _conn is None:
            _conn = sqlite3.connect(":memory:", check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _build_mock_schema(_conn)


def get_connection() -> sqlite3.Connection:
    """获取数据库连接。"""
    if _conn is None:
        init_db()
    assert _conn is not None
    return _conn


def get_metadata(name: str) -> dict[str, Any]:
    """返回数据库的表结构元数据（对应原项目 metadata 服务）。

    供 NL2SQL 作为上下文，生成更准确的 SQL。
    """
    conn = get_connection()
    tables: list[dict[str, Any]] = []
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    for (tname,) in cur.fetchall():
        cur.execute(f"PRAGMA table_info({tname})")
        cols = [{"name": r[1], "type": r[2]} for r in cur.fetchall()]
        cur.execute(f"SELECT COUNT(*) FROM {tname}")
        count = cur.fetchone()[0]
        tables.append({"name": tname, "columns": cols, "rowCount": count})
    return {"database": name, "tables": tables}
