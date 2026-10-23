"""单实例与端口探测。

**判据是「元数据里那个端口能不能连上」**，不是「锁文件在不在」：进程崩溃会留下
锁文件，而一个连不上的端口是确定的事实。Windows 上没有好用的跨进程文件锁，
用 TCP 探测反而更稳。
"""

from __future__ import annotations

import json
import os
import socket
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


def already_running() -> dict | None:
    """已经有实例在跑就返回它的信息，否则 None。"""
    return read_instance()
