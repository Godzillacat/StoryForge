"""桌面启动器：单实例 → 后台起后端 → 等就绪 → 开窗口。

`python -m app.desktop`（开发）或打包后的 `StoryForge.exe`。

两个非交互入口：
  --selftest   不开窗口，建库建表读一次，退出码即结论（打包后验产物用）
  --port N     指定端口（调试用）
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request

import uvicorn

from app import instance

# 内置工具库的份数。**只在自检里用**：`seed_tools` 在目录缺失时静默返回 0，
# 不比对数量就查不出「打包漏了 tools_lib」。
EXPECTED_TOOLS = 25


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
    """不开窗口跑一次：建库、建表、预置、读一次项目列表。

    打包产物有没有缺数据文件（尤其是 `app/tools_lib`）在这一步就会暴露 ——
    **但必须断言数量**：`seed_tools` 在目录缺失时静默返回 0，不报错，
    只看「没抛异常」是查不出漏打包的。
    """
    try:
        from app.db.session import SessionLocal, init_db
        from app.services import project_service
        from app.services.seed_service import seed_agents, seed_tools

        init_db()
        with SessionLocal() as session:
            agents = seed_agents(session)
            tools = seed_tools(session)
            projects = len(project_service.list_projects(session))
            # 重新数一遍库里的行数 —— 预置是幂等的，第二次跑 created 会是 0，
            # 但库里该有的东西一个都不能少。
            from sqlalchemy import func, select

            from app.db.models import Agent, ToolTemplate

            total_agents = session.scalar(select(func.count()).select_from(Agent))
            total_tools = session.scalar(select(func.count()).select_from(ToolTemplate))
    except Exception as exc:  # noqa: BLE001 —— 自检要的是「有没有炸」，不是异常类型
        _report(f"自检失败：{type(exc).__name__}: {exc}")
        return 1

    if not total_agents:
        _report("自检失败：一个智能体都没有 —— 预置阵容没打进去或没跑起来")
        return 1
    if total_tools != EXPECTED_TOOLS:
        _report(
            f"自检失败：内置工具库应有 {EXPECTED_TOOLS} 份，实际 {total_tools} 份 —— "
            "app/tools_lib 大概没打进产物"
        )
        return 1
    _report(
        f"自检通过：项目 {projects} 个 · 智能体 {total_agents} 个 · 工具库 {total_tools} 份"
        f"（本次新建 智能体 {agents} / 工具 {tools}）"
    )
    return 0


def _report(message: str, title: str = "StoryForge") -> None:
    """把消息同时写到 stderr 与一个消息框。

    `console=False` 的打包产物在资源管理器里双击时**没有 stderr** —— 只 print
    的话作者什么也看不到，与「双击没反应」无异。

    `STORYFORGE_NO_DIALOG=1` 时不弹框：测试与构建脚本要的是退出码，
    一个挡在屏幕上的模态框会让它们永远等下去。
    """
    print(message, file=sys.stderr)
    if sys.platform == "win32" and not os.environ.get("STORYFORGE_NO_DIALOG"):
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, message, title, 0x40)
        except Exception:  # noqa: BLE001 —— 弹不出框不该让调用方失败
            pass


def run(port: int | None = None) -> int:
    # **先抢「正在启动」的标记，再起后端**：起后端要建库、跑迁移、播种，
    # 几秒钟；这期间第二次双击看不到 instance.json，会再起一个后端、
    # 再开一个 SQLite 写者。
    if not instance.claim_starting():
        existing = instance.already_running()
        where = f"（端口 {existing['port']}）" if existing else "（正在启动）"
        _report(f"StoryForge 已经在运行{where}。要开第二个窗口请先关掉它。")
        return 1
    try:
        return _run_locked(port)
    finally:
        instance.release_starting()


def _run_locked(port: int | None) -> int:
    # 标记抢到了，但可能上一个实例还活着而标记是崩溃遗留的 —— 再确认一次端口。
    running = instance.already_running()
    if running is not None:
        _report(
            f"StoryForge 已经在运行（端口 {running['port']}）。"
            f"要开第二个窗口请先关掉它。"
        )
        return 1

    chosen = port or _free_port()
    try:
        # **传 app 对象，不传 "app.main:app" 字符串**：字符串形式要按名字导入模块，
        # 打包后那套 import 机制在内嵌环境里找不到它（实测报
        # 「Could not import module "app.main"」）。
        from app.main import app as fastapi_app
    except Exception as exc:  # noqa: BLE001
        _report(f"后端加载失败：{type(exc).__name__}: {exc}")
        return 1

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
        _report(
            "后端没能在 30 秒内就绪。常见原因是数据目录被占用或损坏、"
            "或打包时漏了模块。"
        )
        return 1

    instance.write_instance(chosen)
    try:
        import webview  # 只有真的开窗口时才需要它
    except Exception as exc:  # noqa: BLE001
        server.should_exit = True
        instance.clear_instance()
        _report(
            f"打不开桌面窗口：{type(exc).__name__}: {exc}\n"
            "Windows 10/11 通常自带 WebView2 运行时；缺失时请安装 "
            "Microsoft Edge WebView2 Runtime。"
        )
        return 1

    try:
        webview.create_window(
            "StoryForge",
            f"http://127.0.0.1:{chosen}/",
            width=1400,
            height=900,
            min_size=(960, 640),
        )
        webview.start()
    except Exception as exc:  # noqa: BLE001
        _report(f"窗口异常退出：{type(exc).__name__}: {exc}")
        return 1
    finally:
        # 无论正常关窗还是异常，后端与元数据都要收干净 ——
        # 否则下一次启动会以为还有一个实例在跑。
        server.should_exit = True
        thread.join(timeout=5)
        instance.clear_instance()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="storyforge", description="StoryForge 桌面外壳")
    parser.add_argument("--selftest", action="store_true", help="不开窗口跑一次自检")
    parser.add_argument("--port", type=int, default=None, help="指定后端端口（调试用）")
    parser.add_argument(
        "--data-dir",
        default=None,
        help="自检用的数据目录（不给就在系统临时目录里建一个，用完删掉）",
    )
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest_with_temp_dir(args.data_dir)
    return run(args.port)


def selftest_with_temp_dir(data_dir: str | None = None) -> int:
    """自检**绝不碰作者的真实数据目录**。

    构建脚本会调它；若走默认数据目录，一次打包就会在作者的书稿上跑迁移、
    写迁移前备份、还往里面播种预置 —— 构建不该改动作品数据。
    """
    import os
    import shutil
    import tempfile

    cleanup = data_dir is None
    target = data_dir or tempfile.mkdtemp(prefix="storyforge-selftest-")
    previous = os.environ.get("STORYFORGE_DATA_DIR")
    os.environ["STORYFORGE_DATA_DIR"] = target
    try:
        return selftest()
    finally:
        if previous is None:
            os.environ.pop("STORYFORGE_DATA_DIR", None)
        else:
            os.environ["STORYFORGE_DATA_DIR"] = previous
        if cleanup:
            # **先关连接池再删**：Windows 上被打开的文件删不掉，不 dispose 的话
            # 临时目录会一直留在 %TEMP% 里。
            try:
                from app.db.session import dispose_engine

                dispose_engine()
            except Exception:  # noqa: BLE001 —— 清理失败不该改变自检结论
                pass
            shutil.rmtree(target, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
