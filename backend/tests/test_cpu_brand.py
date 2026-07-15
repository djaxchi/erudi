"""Unit tests for src.engines.cpu_brand.get_cpu_brand.

These replace py-cpuinfo's multiprocessing probe with direct OS-source reads
(#282). Every OS path is exercised on ANY host by monkeypatching
``platform.system`` (and, for Windows, injecting a fake ``winreg`` module).
"""
from __future__ import annotations

import builtins
import io
import platform
import sys

import pytest

from src.engines import cpu_brand


class _FakeWinreg:
    """Minimal winreg stand-in: HKEY_LOCAL_MACHINE, OpenKey, QueryValueEx."""

    HKEY_LOCAL_MACHINE = "HKLM"

    def __init__(self, value=None, error=None):
        self._value = value
        self._error = error

    def OpenKey(self, root, subkey):  # noqa: N802 - mirror winreg API
        if self._error is not None:
            raise self._error

        fake = self

        class _Key:
            def __enter__(self_inner):
                return fake

            def __exit__(self_inner, *exc):
                return False

        return _Key()

    def QueryValueEx(self, key, name):  # noqa: N802 - mirror winreg API
        return self._value, 1  # (value, REG_SZ)


@pytest.mark.unit
def test_windows_reads_processor_name_string(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setitem(
        sys.modules, "winreg", _FakeWinreg(value="AMD Ryzen 5 Pro 7535U with Radeon Graphics")
    )

    assert cpu_brand.get_cpu_brand() == "AMD Ryzen 5 Pro 7535U with Radeon Graphics"


@pytest.mark.unit
def test_windows_strips_whitespace(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setitem(sys.modules, "winreg", _FakeWinreg(value="  Intel(R) Core(TM) i7  "))

    assert cpu_brand.get_cpu_brand() == "Intel(R) Core(TM) i7"


@pytest.mark.unit
def test_windows_registry_error_returns_none(monkeypatch):
    # Documented Windows-failure behavior: a registry read error returns None.
    # We deliberately do NOT fall through to platform.processor() on Windows,
    # where it is uninformative; the callers keep their own local fallback.
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setitem(sys.modules, "winreg", _FakeWinreg(error=OSError("no such key")))

    assert cpu_brand.get_cpu_brand() is None


@pytest.mark.unit
def test_windows_missing_winreg_returns_none(monkeypatch):
    # winreg absent (e.g. patched out) must not raise: import fails -> None.
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setitem(sys.modules, "winreg", None)  # import winreg -> ImportError

    assert cpu_brand.get_cpu_brand() is None


def _patch_proc_cpuinfo(monkeypatch, content):
    real_open = builtins.open

    def fake_open(path, *args, **kwargs):
        if "cpuinfo" in str(path):
            return io.StringIO(content)
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", fake_open)


@pytest.mark.unit
def test_linux_reads_first_model_name(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    _patch_proc_cpuinfo(
        monkeypatch,
        "processor\t: 0\n"
        "vendor_id\t: GenuineIntel\n"
        "model name\t: Intel(R) Core(TM) i7-9750H CPU @ 2.60GHz\n"
        "processor\t: 1\n"
        "model name\t: Intel(R) Core(TM) i7-9750H CPU @ 2.60GHz\n",
    )

    assert cpu_brand.get_cpu_brand() == "Intel(R) Core(TM) i7-9750H CPU @ 2.60GHz"


@pytest.mark.unit
def test_linux_no_model_name_returns_none(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    _patch_proc_cpuinfo(monkeypatch, "processor\t: 0\nvendor_id\t: GenuineIntel\n")

    assert cpu_brand.get_cpu_brand() is None


@pytest.mark.unit
def test_linux_open_error_returns_none(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Linux")

    def boom(*args, **kwargs):
        raise OSError("cannot read /proc/cpuinfo")

    monkeypatch.setattr(builtins, "open", boom)

    assert cpu_brand.get_cpu_brand() is None


@pytest.mark.unit
def test_darwin_uses_processor_then_machine(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "processor", lambda: "arm")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")

    assert cpu_brand.get_cpu_brand() == "arm"


@pytest.mark.unit
def test_darwin_falls_back_to_machine_when_processor_empty(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "processor", lambda: "")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")

    assert cpu_brand.get_cpu_brand() == "arm64"


@pytest.mark.unit
def test_fallback_empty_returns_none(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "SomeOtherOS")
    monkeypatch.setattr(platform, "processor", lambda: "")
    monkeypatch.setattr(platform, "machine", lambda: "")

    assert cpu_brand.get_cpu_brand() is None


@pytest.mark.unit
def test_never_raises_on_unexpected_failure(monkeypatch):
    # Any unexpected exception inside a path must be swallowed -> None.
    monkeypatch.setattr(platform, "system", lambda: "Darwin")

    def boom():
        raise RuntimeError("platform probe exploded")

    monkeypatch.setattr(platform, "processor", boom)

    assert cpu_brand.get_cpu_brand() is None
