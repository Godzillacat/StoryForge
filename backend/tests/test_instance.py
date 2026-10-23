"""单实例元数据：写了能读回、端口没了就当没有、坏文件不炸。"""

import json
import socket

import pytest

from app import config, instance


@pytest.fixture()
def listening():
    """起一个真在监听的 socket，返回它的端口。"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    yield server.getsockname()[1]
    server.close()


@pytest.fixture()
def free_port() -> int:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


def test_write_then_read(listening):
    instance.write_instance(listening)

    assert instance.read_instance()["port"] == listening


def test_no_file_means_not_running():
    assert instance.read_instance() is None


def test_a_stale_file_for_a_dead_port_counts_as_not_running(free_port):
    """进程崩了会留下元数据；连不上就不能认为它在跑。"""
    instance.write_instance(free_port)

    assert instance.read_instance() is None
    # 顺手清掉，不用每次再探一次。
    assert not instance.instance_file().exists()


def test_a_corrupted_file_is_ignored():
    config.data_dir().mkdir(parents=True, exist_ok=True)
    instance.instance_file().write_text("not json", encoding="utf-8")

    assert instance.read_instance() is None


def test_clear_removes_the_file(listening):
    instance.write_instance(listening)

    instance.clear_instance()

    assert not instance.instance_file().exists()


def test_port_in_use_detects_a_listener(listening, free_port):
    assert instance.port_in_use(listening) is True
    assert instance.port_in_use(free_port) is False


def test_already_running_returns_the_metadata(listening):
    instance.write_instance(listening)

    running = instance.already_running()

    assert running is not None and running["port"] == listening
