"""Windows compatibility helpers for import-time runtime issues."""

from __future__ import annotations

import os
import platform
import sys
from collections import namedtuple


def patch_platform_machine_for_windows() -> None:
    """Avoid Python 3.13 WMI hangs when libraries import platform helpers on Windows."""
    if sys.platform != "win32":
        return

    fallback_arch = os.getenv("PROCESSOR_ARCHITEW6432") or os.getenv("PROCESSOR_ARCHITECTURE") or "AMD64"
    fallback_release = os.getenv("OS", "Windows_NT")
    uname_result = namedtuple("uname_result", ["system", "node", "release", "version", "machine", "processor"])

    def _safe_machine() -> str:
        return fallback_arch

    def _safe_system() -> str:
        return "Windows"

    def _safe_win32_ver(release="", version="", csd="", ptype=""):
        return (release or fallback_release, version or "", csd or "", ptype or fallback_arch)

    def _safe_uname():
        return uname_result(
            system="Windows",
            node=os.getenv("COMPUTERNAME", "localhost"),
            release=fallback_release,
            version=os.getenv("PROCESSOR_REVISION", ""),
            machine=fallback_arch,
            processor=fallback_arch,
        )

    platform.machine = _safe_machine
    platform.system = _safe_system
    platform.win32_ver = _safe_win32_ver
    platform.uname = _safe_uname
