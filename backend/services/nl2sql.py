"""自然语言转 SQL 服务：对应原项目 app/services/nl2sql.py。

原项目使用 OpenAI 进行 NL2SQL；此处采用规则匹配作为离线可运行的模拟实现，
保证无需 API Key 即可演示"自然语言查询"的 AI 交互体验。
"""
import re
from typing import Any


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def generate_sql(prompt: str, metadata: dict[str, Any]) -> dict[str, str]:
    """根据自然语言生成 SQL 与解释。

    Args:
        prompt: 用户的自然语言提问
        metadata: 数据库表结构元数据（tables: [{name, columns, rowCount}]）

    Returns:
        {"sql": "...", "explanation": "..."}
    """
    p = _norm(prompt)
    table_names = [t["name"] for t in metadata.get("tables", [])]

    # 表名命中
    target = None
    for t in table_names:
        if t in p or t.rstrip("s") in p:
            target = t
            break

    # 计数 / 统计类
    if re.search(r"(多少|数量|个数|统计|count)", p):
        if "部门" in p and "员工" in p:
            sql = "SELECT department, COUNT(*) AS employee_count FROM employees GROUP BY department ORDER BY employee_count DESC"
            return {"sql": sql, "explanation": "按部门对员工进行分组计数，并按人数降序排列。"}
        if target == "employees" or "员工" in p:
            sql = "SELECT COUNT(*) AS total FROM employees"
            return {"sql": sql, "explanation": "统计员工总数。"}
        if target == "orders" or "订单" in p:
            sql = "SELECT COUNT(*) AS total FROM orders"
            return {"sql": sql, "explanation": "统计订单总数。"}
        if target == "products" or "商品" in p:
            sql = "SELECT COUNT(*) AS total FROM products"
            return {"sql": sql, "explanation": "统计商品总数。"}
        sql = f"SELECT COUNT(*) AS total FROM {target or 'employees'}"
        return {"sql": sql, "explanation": f"统计 {target or 'employees'} 表的记录数。"}

    # 平均 / 薪资
    if re.search(r"(平均|avg|average)", p) and ("薪水" in p or "工资" in p or "salary" in p):
        sql = "SELECT department, AVG(salary) AS avg_salary FROM employees GROUP BY department ORDER BY avg_salary DESC"
        return {"sql": sql, "explanation": "计算各部门平均薪资并降序排列。"}

    if re.search(r"(平均|avg)", p) and ("价格" in p or "price" in p):
        sql = "SELECT category, AVG(price) AS avg_price FROM products GROUP BY category"
        return {"sql": sql, "explanation": "按品类计算商品平均价格。"}

    # 排序：最高 / 最高薪
    if re.search(r"(最高|最高薪|top|max)", p) and ("薪水" in p or "工资" in p or "salary" in p):
        sql = "SELECT name, department, salary FROM employees ORDER BY salary DESC LIMIT 5"
        return {"sql": sql, "explanation": "查询薪资最高的前 5 名员工。"}

    # 条件：大于 / 超过
    m = re.search(r"(?:大于|超过|高于|高于|>=|>)\s*(\d+)", p)
    if m and ("薪水" in p or "工资" in p or "salary" in p):
        sql = f"SELECT * FROM employees WHERE salary > {int(m.group(1))} ORDER BY salary DESC"
        return {"sql": sql, "explanation": f"查询薪资大于 {m.group(1)} 的员工。"}
    if m and ("价格" in p or "price" in p):
        sql = f"SELECT * FROM products WHERE price > {int(m.group(1))} ORDER BY price DESC"
        return {"sql": sql, "explanation": f"查询价格大于 {m.group(1)} 的商品。"}

    # 条件：小于 / 低于
    m = re.search(r"(?:小于|低于|低于|<=|<)\s*(\d+)", p)
    if m and ("价格" in p or "price" in p):
        sql = f"SELECT * FROM products WHERE price < {int(m.group(1))} ORDER BY price"
        return {"sql": sql, "explanation": f"查询价格低于 {m.group(1)} 的商品。"}
    if m and ("库存" in p or "stock" in p):
        sql = f"SELECT * FROM products WHERE stock < {int(m.group(1))} ORDER BY stock"
        return {"sql": sql, "explanation": f"查询库存低于 {m.group(1)} 的商品。"}

    # 订单状态
    if "订单" in p and re.search(r"(状态|完成|发货|处理)", p):
        sql = "SELECT status, COUNT(*) AS count FROM orders GROUP BY status"
        return {"sql": sql, "explanation": "按状态统计订单数量。"}

    # 部门相关：查员工
    if "部门" in p and ("员工" in p or "人员" in p):
        sql = "SELECT name, department, position, salary FROM employees ORDER BY department, salary DESC"
        return {"sql": sql, "explanation": "查询各部门员工信息，按部门与薪资排序。"}

    # 默认：查表全部
    if target:
        sql = f"SELECT * FROM {target} LIMIT 100"
        return {"sql": sql, "explanation": f"查询 {target} 表的全部数据（限 100 行）。"}

    # 兜底
    sql = "SELECT * FROM employees LIMIT 100"
    return {
        "sql": sql,
        "explanation": "未精确匹配到意图，默认查询员工表数据。可尝试如：'统计每个部门的员工数量'、'查询薪水大于20000的员工'、'查询价格低于300的商品'。",
    }
