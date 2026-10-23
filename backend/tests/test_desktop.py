"""桌面外壳的非交互部分：自检、端口分配、参数解析。

这些用例跑在临时数据目录里（工具库断言依赖它）：自检必须能在**干净**的库上
通过，也必须在**缺工具库**时变红 —— 那正是它存在的理由。
"""

import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from app import config, desktop, instance


@pytest.fixture(autouse=True)
def no_dialog(monkeypatch):
    """测试里绝不弹模态框 —— 它会挡在屏幕上让 pytest 永远等下去。"""
    monkeypatch.setenv("STORYFORGE_NO_DIALOG", "1")


def test_selftest_passes_on_a_fresh_data_dir():
    assert desktop.selftest() == 0


def test_selftest_fails_when_the_tools_library_is_missing(tmp_path):
    """打包漏了 app/tools_lib 时 `seed_tools` 静默返回 0 —— 不比对数量就查不出来。

    **必须开子进程**：`app.db.session` 的 engine 是模块加载时按当时的数据目录
    建好的常量，同进程里改环境变量换不了库。
    """
    missing = tmp_path / "nope"
    code = (
        "import sys\n"
        "from app.services import seed_service\n"
        f"seed_service.TOOLS_LIB_DIR = __import__('pathlib').Path(r'{missing}')\n"
        "from app import desktop\n"
        "sys.exit(desktop.selftest())\n"
    )
    env = {**os.environ, "STORYFORGE_DATA_DIR": str(tmp_path / "db"), "STORYFORGE_NO_DIALOG": "1"}
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
        timeout=120,
    )

    assert result.returncode == 1, result.stderr
    assert "工具库" in result.stderr


def test_selftest_uses_a_throwaway_dir_not_the_real_one(monkeypatch, tmp_path):
    """构建时跑自检绝不能落在作者的书稿上（跑迁移、写备份、播种）。"""
    marker = tmp_path / "real"
    marker.mkdir()
    monkeypatch.setenv("STORYFORGE_DATA_DIR", str(marker))

    assert desktop.selftest_with_temp_dir() == 0

    # 真实目录里没有被动过：没有库文件。
    assert not (marker / "storyforge.db").exists()


def test_selftest_cleans_up_its_temp_dir(monkeypatch):
    """不给 --data-dir 时自己建一个临时目录，用完删掉。

    Windows 上 SQLite 文件被连接池占着就删不掉 —— 必须在删之前 dispose，
    否则每次自检都会在 %TEMP% 里留一份。
    """
    seen: dict[str, str] = {}

    def fake_selftest() -> int:
        seen["dir"] = os.environ["STORYFORGE_DATA_DIR"]
        return 0

    monkeypatch.setattr(desktop, "selftest", fake_selftest)

    assert desktop.selftest_with_temp_dir() == 0

    assert seen["dir"]
    assert not Path(seen["dir"]).exists()


def test_free_port_is_actually_free():
    port = desktop._free_port()

    assert isinstance(port, int) and port > 0
    assert instance.port_in_use(port) is False


def test_main_routes_selftest_without_opening_a_window(monkeypatch):
    called = {"selftest": 0}

    def fake_selftest(data_dir=None) -> int:
        called["selftest"] += 1
        return 0

    monkeypatch.setattr(desktop, "selftest_with_temp_dir", fake_selftest)

    assert desktop.main(["--selftest"]) == 0
    assert called["selftest"] == 1


def test_second_instance_refuses_to_start(monkeypatch):
    """已有实例在跑时不再起第二个 —— 两份进程写同一个 SQLite 会互相踩。

    先占住启动标记（等价于「第一个实例正在起或已在跑」），第二次必须被挡回来。
    正常退出会释放标记；这里模拟的是「它还在跑」。
    """
    assert instance.claim_starting() is True
    try:
        monkeypatch.setattr(desktop, "_free_port", lambda: 1 / 0)
        assert desktop.run() == 1
    finally:
        instance.release_starting()


def test_a_stale_starting_marker_does_not_block_forever():
    """崩溃留下的标记（进程已不在）要能被接管，否则应用再也起不来。"""
    config.data_dir().mkdir(parents=True, exist_ok=True)
    instance.starting_file().write_text('{"pid": 999999}', encoding="utf-8")

    assert instance.claim_starting() is True
    instance.release_starting()
