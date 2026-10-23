"""桌面外壳的非交互部分：自检、端口分配、参数解析。"""

import socket

from app import desktop, instance


def test_selftest_passes_on_a_fresh_data_dir():
    """打包产物缺 agents / tools_lib 时这里会炸 —— 正是它要抓的。"""
    assert desktop.selftest() == 0


def test_free_port_is_actually_free():
    port = desktop._free_port()

    assert isinstance(port, int) and port > 0
    assert instance.port_in_use(port) is False


def test_main_routes_selftest_without_opening_a_window(monkeypatch):
    called = {"selftest": 0}

    def fake_selftest() -> int:
        called["selftest"] += 1
        return 0

    monkeypatch.setattr(desktop, "selftest", fake_selftest)

    assert desktop.main(["--selftest"]) == 0
    assert called["selftest"] == 1


def test_second_instance_refuses_to_start(monkeypatch):
    """已有实例在跑时不再起第二个 —— 两份进程写同一个 SQLite 会互相踩。"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    instance.write_instance(port)

    try:
        # 不该走到开窗口那一步。
        monkeypatch.setattr(desktop, "_free_port", lambda: 1 / 0)
        assert desktop.run() == 1
    finally:
        server.close()
        instance.clear_instance()
