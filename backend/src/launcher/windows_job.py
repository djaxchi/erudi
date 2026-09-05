"""Windows Job Object binding child-process lifetime to this process (#341).

The parent-death watchdog (#224) and the stdin-EOF watcher both detect a dead
Electron parent from WITHIN this process and then run the FastAPI lifespan
shutdown, which stops the embedded Postgres cluster deterministically. Both
depend on this process staying alive long enough to notice and react.

That assumption breaks when the backend itself is torn down at the same time
as Electron: recent Electron versions place their spawned child processes
(this backend included) inside a Windows Job Object with
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE, so a hard-killed Electron main process
cascades an OS-level TerminateProcess onto this process within milliseconds --
faster than the 0.25s/2s poll intervals of either watchdog. Postgres and
llama-server, spawned as OUR children via plain subprocess.Popen (and, for
Postgres, deliberately given their own console by the #162 fix so a dead
CONSOLE alone never takes them down), are not members of that job and have no
mechanism at all tying their lifetime to ours in this scenario -- so they
survive orphaned indefinitely, holding the data directory and the port.

The fix mirrors the same trick one level down: create OUR OWN job with
KILL_ON_JOB_CLOSE, assign this process to it, and keep the handle open for the
life of the process. Every child this process spawns afterwards (Postgres and
its ~10 forked helpers, llama-server) automatically joins the same job unless
it explicitly requests CREATE_BREAKAWAY_FROM_JOB -- nothing in this codebase
does, so no other file needs to change. Windows nests job objects natively
(8+/Server 2012+), so this composes cleanly whether or not Electron's own job
already contains this process: whenever THIS process's last handle closes --
clean exit, watchdog-triggered shutdown, or an external TerminateProcess --
the kernel tears down every member of our job too, with no Python code
required to run at all. This is deliberately independent of (and a safety net
under) the graceful stop_postgres() shutdown path: that path still runs first
when there's time for it; this one covers the case where there isn't.

No-op on non-Windows platforms and swallowed on any failure: the app must
keep working even where job objects are unavailable or restricted (e.g. under
some sandboxes) -- it just loses this extra layer of orphan protection.
"""

from __future__ import annotations

import ctypes
import platform
from ctypes import wintypes

from src.core.logging import logger

# Kept alive for the process lifetime so the job is never closed early: closing
# our only handle to the job is exactly the "job close" event that triggers
# KILL_ON_JOB_CLOSE, so an early close would kill this process's own children
# immediately instead of only on exit.
_job_handle: int | None = None

JobObjectExtendedLimitInformation = 9
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000


class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def bind_children_to_this_process() -> bool:
    """Create a kill-on-close Job Object and assign this process to it.

    Idempotent-ish: safe to call more than once (a second call just creates
    and leaks a second job doing the same thing), but callers should only call
    it once, early at startup and before spawning Postgres/llama-server, so
    every child inherits membership from the start.

    Returns True if the job was created and assigned, False if anything about
    it failed (already logged) -- the caller never needs to branch on this,
    it exists for tests.
    """
    global _job_handle

    if platform.system() != "Windows":
        return False

    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            logger.warning(
                f"CreateJobObjectW failed (error={ctypes.get_last_error()}); "
                "Postgres/llama-server may survive a hard-killed parent (#341)"
            )
            return False

        info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE

        ok = kernel32.SetInformationJobObject(
            wintypes.HANDLE(job),
            JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        if not ok:
            logger.warning(
                f"SetInformationJobObject failed (error={ctypes.get_last_error()}); "
                "Postgres/llama-server may survive a hard-killed parent (#341)"
            )
            kernel32.CloseHandle(wintypes.HANDLE(job))
            return False

        # GetCurrentProcess() returns a pseudo-handle (-1) valid for this call
        # without needing OpenProcess/PROCESS_SET_QUOTA|PROCESS_TERMINATE rights.
        current_process = kernel32.GetCurrentProcess()
        ok = kernel32.AssignProcessToJobObject(
            wintypes.HANDLE(job), wintypes.HANDLE(current_process)
        )
        if not ok:
            logger.warning(
                f"AssignProcessToJobObject failed (error={ctypes.get_last_error()}); "
                "Postgres/llama-server may survive a hard-killed parent (#341)"
            )
            kernel32.CloseHandle(wintypes.HANDLE(job))
            return False

        _job_handle = job  # keep alive: see module docstring
        logger.info(
            "Windows job object bound: Postgres/llama-server now die with this "
            "process even on a hard kill (#341)"
        )
        return True
    except Exception as exc:
        logger.warning(f"Could not set up the Windows job object (#341): {exc}")
        return False
