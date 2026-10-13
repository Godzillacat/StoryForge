"""Windows DPAPI 密钥加密（D-01：密钥只在本机加密存储）。

非 Windows 平台降级为明文存储并返回 is_encryption_available() == False，
以便在开发机上跑通测试；打包产物只在 Windows 运行。
"""

from __future__ import annotations

import base64
import ctypes
import json
import sys
from ctypes import wintypes

from app import config

_IS_WINDOWS = sys.platform == "win32"
_CRYPTPROTECT_UI_FORBIDDEN = 0x01
_ENTROPY = b"StoryForge-v1"


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(data: bytes) -> _DataBlob:
    buf = ctypes.create_string_buffer(data, len(data))
    return _DataBlob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))


def is_encryption_available() -> bool:
    return _IS_WINDOWS


def _protect(plaintext: str) -> str:
    data = plaintext.encode("utf-8")
    if not _IS_WINDOWS:
        return "plain:" + base64.b64encode(data).decode("ascii")
    out = _DataBlob()
    ok = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(_blob(data)),
        "StoryForge",
        ctypes.byref(_blob(_ENTROPY)),
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out),
    )
    if not ok:
        raise OSError("CryptProtectData 失败，无法加密密钥")
    try:
        raw = ctypes.string_at(out.pbData, out.cbData)
        return "dpapi:" + base64.b64encode(raw).decode("ascii")
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


def _unprotect(stored: str) -> str:
    scheme, _, payload = stored.partition(":")
    raw = base64.b64decode(payload)
    if scheme == "plain":
        return raw.decode("utf-8")
    if scheme != "dpapi":
        raise ValueError(f"无法识别的密钥存储格式: {scheme}")
    out = _DataBlob()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(_blob(raw)),
        None,
        ctypes.byref(_blob(_ENTROPY)),
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out),
    )
    if not ok:
        raise OSError("CryptUnprotectData 失败，密钥可能来自其他机器或用户")
    try:
        return ctypes.string_at(out.pbData, out.cbData).decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


def _read_store() -> dict[str, str]:
    path = config.secrets_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _write_store(store: dict[str, str]) -> None:
    config.secrets_path().write_text(
        json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def set_secret(ref: str, value: str) -> None:
    store = _read_store()
    store[ref] = _protect(value)
    _write_store(store)


def get_secret(ref: str) -> str | None:
    stored = _read_store().get(ref)
    return None if stored is None else _unprotect(stored)


def delete_secret(ref: str) -> bool:
    store = _read_store()
    if ref not in store:
        return False
    del store[ref]
    _write_store(store)
    return True


def list_refs() -> list[str]:
    return sorted(_read_store().keys())


def mask(value: str) -> str:
    """界面只回显屏蔽态，绝不回显明文。"""
    if not value:
        return ""
    if len(value) <= 4:
        return "****"
    head = "sk-" if value.startswith("sk-") else ""
    return f"{head}****{value[-4:]}"
