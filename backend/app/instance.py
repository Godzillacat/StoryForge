"""单实例与端口探测。

**判据是「元数据里那个端口能不能连上」**，不是「锁文件在不在」：进程崩溃会留下
锁文件，而一个连不上的端口是确定的事实。Windows 上没有好用的跨进程文件锁，
用 TCP 探测反而更稳。
"""

from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path

from app import config


def instance_file() -> Path:
    return config.data_dir() / "instance.json"


def port_in_use(port: int, host: str = "127.0.0.1", timeout: float = 0.3) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(timeout)
        return probe.connect_ex((host, port)) == 0


def read_instance() -> dict | None:
    """读出上一次运行的 {port, pid}；文件不在、坏了、端口连不上都当作没有。"""
    path = instance_file()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        port = int(data["port"])
        pid = int(data.get("pid", 0))
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not port_in_use(port):
        # 进程已经没了，元数据是遗留 —— 顺手清掉，免得每次都要探一次。
        clear_instance()
        return None
    return {"port": port, "pid": pid}


def write_instance(port: int) -> None:
    config.data_dir().mkdir(parents=True, exist_ok=True)
    instance_file().write_text(
        json.dumps({"port": port, "pid": os.getpid()}), encoding="utf-8"
    )


def clear_instance() -> None:
    instance_file().unlink(missing_ok=True)


def claim_starting() -> bool:
    """在起后端**之前**抢一个「正在启动」的标记。

    `write_instance` 要等端口就绪才写，而启动包含建库、跑迁移、播种预置 ——
    几秒钟。这期间第二次双击看不到 instance.json，会再起一个后端、再开一个
    SQLite 写者。所以先原子地占位：`O_CREAT | O_EXCL` 只成功一次。

    返回 True 表示抢到了；False 表示已有实例（在启动或已在跑）。
    """
    path = starting_file()
    config.data_dir().mkdir(parents=True, exist_ok=True)
    try:
        handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        # 上一次可能是崩溃留下的：发起的进程没了就当作没占。
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            pid = int(data.get("pid", 0))
        except (OSError, ValueError, TypeError):
            pid = 0
        if pid and _pid_alive(pid):
            return False
        path.unlink(missing_ok=True)
        try:
            handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return False
    with os.fdopen(handle, "w", encoding="utf-8") as stream:
        json.dump({"pid": os.getpid()}, stream)
    return True


def release_starting() -> None:
    starting_file().unlink(missing_ok=True)


def starting_file() -> Path:
    return config.data_dir() / "instance.starting"


def _pid_alive(pid: int) -> bool:
    """Windows 上没有可靠的 `os.kill(pid, 0)` 语义，用任务列表问一次。"""
    if pid <= 0:
        return False
    if sys.platform != "win32":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    import subprocess

    try:
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=0x08000000,  # CREATE_NO_WINDOW：别给双击的用户闪一个黑框
        ).stdout
    except (OSError, subprocess.SubprocessError):
        # 问不出来就当它还活着 —— 宁可拒绝第二次启动，也别开第二个写者。
        return True
    return str(pid) in out


def already_running() -> dict | None:
    """已经有实例在跑就返回它的信息，否则 None。"""
    return read_instance()
