"""智能数据库查询工具 —— 后端入口（纯标准库实现）。

对应原项目 backend/app/main.py（FastAPI）的职责：
- 注册路由
- 提供 CORS
- 提供前端静态资源服务（原项目由前端 dev server 提供）

运行：python backend/server.py  （或 python -m backend.server）
访问：http://localhost:8000
"""
import os
import sys
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

# 将项目根目录加入 sys.path，使 `python backend/server.py` 也能导入 backend 包
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.database import init_db
from backend.api import dispatch as api_dispatch

HOST = "127.0.0.1"
PORT = 8000
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")


class Handler(BaseHTTPRequestHandler):
    # 让中文日志可读
    def log_message(self, format, *args):  # noqa: A002
        sys.stderr.write("[server] %s - %s\n" % (self.address_string(), format % args))

    def do_OPTIONS(self):
        api_dispatch(self)

    def do_GET(self):
        if api_dispatch(self):
            return
        self._serve_static("GET")

    def do_POST(self):
        if api_dispatch(self):
            return
        self._not_found()

    # ---------- 静态资源 ----------
    def _serve_static(self, method):
        parsed = urlparse(self.path)
        rel = parsed.path.lstrip("/")
        if rel == "" :
            rel = "index.html"

        # 防止路径穿越
        safe = os.path.normpath(os.path.join(FRONTEND_DIR, rel))
        if not safe.startswith(FRONTEND_DIR):
            self._not_found()
            return

        if not os.path.exists(safe) or os.path.isdir(safe):
            self._not_found()
            return

        mime = mimetypes.guess_type(safe)[0] or "application/octet-stream"
        with open(safe, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", f"{mime}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _not_found(self):
        body = b"Not Found"
        self.send_response(404)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_app() -> ThreadingHTTPServer:
    init_db()
    mimetypes.add_type("application/javascript", ".js")
    mimetypes.add_type("text/css", ".css")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    return server


def main():
    server = create_app()
    print("=" * 64)
    print("  智能数据库查询工具（含数据导出功能）")
    print("  访问地址: http://localhost:8000")
    print("  健康检查: http://localhost:8000/health")
    print("  按 Ctrl+C 停止服务")
    print("=" * 64)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止。")
        server.shutdown()


if __name__ == "__main__":
    main()
