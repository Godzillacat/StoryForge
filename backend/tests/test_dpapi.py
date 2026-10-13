import pytest

from app.crypto import dpapi


def test_set_then_get_roundtrip():
    dpapi.set_secret("provider:openai", "sk-test-1234567890")
    assert dpapi.get_secret("provider:openai") == "sk-test-1234567890"


def test_get_missing_ref_returns_none():
    assert dpapi.get_secret("provider:nope") is None


def test_delete_removes_secret():
    dpapi.set_secret("provider:temp", "sk-temp")
    assert dpapi.delete_secret("provider:temp") is True
    assert dpapi.get_secret("provider:temp") is None
    assert dpapi.delete_secret("provider:temp") is False


def test_overwrite_replaces_value():
    dpapi.set_secret("provider:x", "first")
    dpapi.set_secret("provider:x", "second")
    assert dpapi.get_secret("provider:x") == "second"


def test_list_refs_never_leaks_values():
    dpapi.set_secret("provider:a", "sk-aaaa")
    refs = dpapi.list_refs()
    assert "provider:a" in refs
    assert all("sk-" not in r for r in refs)


def test_secrets_file_does_not_contain_plaintext():
    from app import config

    dpapi.set_secret("provider:plain", "sk-SUPER-SECRET-VALUE")
    raw = config.secrets_path().read_bytes()
    assert b"SUPER-SECRET-VALUE" not in raw


def test_mask_keeps_only_tail():
    assert dpapi.mask("sk-1234567890abcdef") == "sk-****cdef"
    assert dpapi.mask("ab") == "****"


def test_mask_of_empty_is_empty():
    assert dpapi.mask("") == ""
