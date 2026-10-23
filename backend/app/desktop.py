"""桌面启动器：单实例 → 后台起后端 → 等就绪 → 开窗口。

`python -m app.desktop`（开发）或打包后的 `StoryForge.exe`。

两个非交互入口：
  --selftest   不开窗口，建库建表读一次，退出码即结论（打包后验产物用）
  --port N     指定端口（调试用）
"""

from __future__ import annotations

import argparse
import socket
import sys
import threading
import time
import urllib.error
import urllib.request

import uvicorn

from app import instance


def _free_port() -> int:
    """让系统分配一个空闲端口 —— 硬编码迟早撞车。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _wait_ready(port: int, timeout: float = 30.0) -> bool:
    """轮询 /api/health，直到通了或超时。建库与预置可能要好一会儿。"""
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/api/health"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.2)
    return False


def selftest() -> int:
    """不开窗口跑一次：建库、建表、读一次项目列表。

    打包产物有没有缺数据文件（agents / tools_lib）在这一步就会暴露。
    """
    from app.db.session import SessionLocal, init_db
    from app.services import project_service
    from app.services.seed_service import seed_agents, seed_tools

    try:
        init_db()
        with SessionLocal() as session:
            seed_agents(session)
            seed_tools(session)
            count = len(project_service.list_projects(session))
    except Exception as exc:  # noqa: BLE001 —— 自检要的是「有没有炸」，不是异常类型
        print(f"自检失败：{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"自检通过：项目 {count} 个")
    return 0


def run(port: int | None = None) -> int:
    existing = instance.already_running()
    if existing is not None:
        print(
            f"StoryForge 已经在运行（端口 {existing['port']}）。"
            f"要开第二个窗口请先关掉它。",
            file=sys.stderr,
        )
        return 1

    chosen = port or _free_port()
    # **传 app 对象，不传 "app.main:app" 字符串**：字符串形式要按名字导入模块，
    # 打包后那套 import 机制在内嵌环境里找不到它（实测报
    # 「Could not import module "app.main"」）。
    from app.main import app as fastapi_app

    uvicorn_config = uvicorn.Config(
        fastapi_app, host="127.0.0.1", port=chosen, log_level="info"
    )
    server = uvicorn.Server(uvicorn_config)
    # uvicorn 的 Server 会接管信号处理；放在后台线程跑，主线程留给窗口。
    thread = threading.Thread(target=server.run, name="uvicorn", daemon=True)
    thread.start()

    if not _wait_ready(chosen):
        server.should_exit = True
        # 把 uvicorn 自己的错误也报出来：只写「没就绪」会让人去猜数据目录，
        # 而真实原因常常是「模块导入失败」这类启动期错误。
        print(
            "后端没能在 30 秒内就绪。请查看上面的日志 —— "
            "常见原因是数据目录被占用或损坏、或打包时漏了模块。",
            file=sys.stderr,
        )
        return 1

    instance.write_instance(chosen)
    try:
        import webview  # 只有真的开窗口时才需要它
    except Exception as exc:  # noqa: BLE001
        server.should_exit = True
        instance.clear_instance()
        print(
            f"打不开桌面窗口：{type(exc).__name__}: {exc}\n"
            "Windows 10/11 通常自带 WebView2 运行时；缺失时请安装 "
            "Microsoft Edge WebView2 Runtime。",
            file=sys.stderr,
        )
        return 1

    webview.create_window(
        "StoryForge",
        f"http://127.0.0.1:{chosen}/",
        width=1400,
        height=900,
        min_size=(960, 640),
    )
    try:
        webview.start()
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        instance.clear_instance()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="storyforge", description="StoryForge 桌面外壳")
    parser.add_argument("--selftest", action="store_true", help="不开窗口跑一次自检")
    parser.add_argument("--port", type=int, default=None, help="指定后端端口（调试用）")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    return run(args.port)


if __name__ == "__main__":
    raise SystemExit(main())
