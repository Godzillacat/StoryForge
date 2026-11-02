"""窗口模式下 `sys.stdout` / `sys.stderr` 为 None 的回归测试。

双击启动的 PyInstaller GUI 程序没有控制台，uvicorn 的默认日志格式器会调用
`stream.isatty()`；不先把流补上，启动阶段就会崩。2026-11-02 实测过这个失败。
"""

import sys

from app import desktop


def test_none_streams_are_replaced(monkeypatch, tmp_path):
    monkeypatch.setenv("STORYFORGE_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)

    desktop._ensure_streams()

    assert sys.stdout is not None
    assert sys.stderr is not None
    assert hasattr(sys.stdout, "isatty")
    assert (tmp_path / "launcher.log").exists()

    desktop._std_stream.close()
    desktop._std_stream = None


def test_existing_streams_are_left_alone():
    before_out, before_err = sys.stdout, sys.stderr
    desktop._ensure_streams()
    assert sys.stdout is before_out
    assert sys.stderr is before_err
