"""Read the CPU brand string straight from OS-native sources.

py-cpuinfo's ``get_cpu_info()`` spawns a multiprocessing worker to probe the
CPU. In a PyInstaller-frozen build that worker is a full re-exec of the whole
``backend.exe``; under cold EDR scanning on Windows first boot each respawn
costs ~1.5-2 min and blows the startup budget (#282). py-cpuinfo only wraps the
same OS-native sources we read here, so we read them directly: no subprocess,
no multiprocessing, no re-exec.

OS branching belongs in the engines layer (per CLAUDE.md), which is why this
lives beside the concrete engines rather than in ``utils``.

Behavior contract:
    - Windows: registry key
      ``HKLM\\HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0\\ProcessorNameString``
      (verified on the field machine to return the identical string py-cpuinfo
      produced, in 0.0 ms). A registry failure returns ``None`` -- callers keep
      their own local fallback (``platform.processor()`` etc.); we do not fall
      through to ``platform.processor()`` here because it is uninformative on
      Windows anyway.
    - Linux: first ``model name`` line of ``/proc/cpuinfo``.
    - Darwin / anything else: ``platform.processor()`` then ``platform.machine()``.
    - Any failure on any path returns ``None`` -- this function never raises.
"""

from __future__ import annotations

import platform
from typing import Optional


def _brand_windows() -> Optional[str]:
    """Read ProcessorNameString from the CentralProcessor registry key."""
    import winreg

    with winreg.OpenKey(
        winreg.HKEY_LOCAL_MACHINE,
        r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
    ) as key:
        value, _ = winreg.QueryValueEx(key, "ProcessorNameString")
    return value


def _brand_linux() -> Optional[str]:
    """Return the first ``model name`` value from /proc/cpuinfo."""
    with open("/proc/cpuinfo", "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("model name"):
                _, _, value = line.partition(":")
                return value
    return None


def _brand_fallback() -> Optional[str]:
    """Best-effort brand from stdlib for Darwin and any other platform."""
    return platform.processor() or platform.machine()


def get_cpu_brand() -> Optional[str]:
    """Return the CPU brand string from OS sources, or ``None`` on any failure.

    Never raises: every OS path is wrapped so callers can treat a missing brand
    as "fall back to whatever you already had".
    """
    system = platform.system()
    try:
        if system == "Windows":
            brand = _brand_windows()
        elif system == "Linux":
            brand = _brand_linux()
        else:
            brand = _brand_fallback()
    except Exception:
        return None

    if brand is None:
        return None
    brand = brand.strip()
    return brand or None
