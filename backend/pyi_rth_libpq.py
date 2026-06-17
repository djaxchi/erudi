# PyInstaller runtime hook — resolve the libpq collision between psycopg and
# pgserver in the frozen bundle.
#
# psycopg[binary] >= 3.2 (required by langgraph-checkpoint-postgres) needs
# libpq >= 17 (it calls PQcancelBlocking). It ships its OWN libpq inside
# psycopg_binary/.dylibs. pgserver bundles an OLDER libpq (PostgreSQL 16.2).
# In the frozen app both expose `@rpath/libpq.5.dylib`, and psycopg's pq
# extension ends up binding to pgserver's older one -> "Symbol not found:
# _PQcancelBlocking" and the backend dies at import.
#
# Fix: preload psycopg's own libpq with RTLD_GLOBAL before psycopg is imported.
# macOS dyld dedups loaded images by install name, so the subsequent
# `@rpath/libpq.5.dylib` request reuses the (newer) image we loaded here.
# pgserver's client tools run as separate subprocesses and keep using their own
# libpq, which is fine for them.
import ctypes
import glob
import os
import sys

if getattr(sys, "frozen", False):
    base = sys._MEIPASS  # the unpacked _internal dir
    patterns = [
        os.path.join(base, "psycopg_binary", ".dylibs", "libpq*.dylib"),  # macOS
        os.path.join(base, "psycopg_binary.libs", "libpq*.so*"),          # Linux
        os.path.join(base, "psycopg_binary", "libpq*.so*"),               # Linux (alt)
    ]
    mode = getattr(ctypes, "RTLD_GLOBAL", 0)
    for pattern in patterns:
        for lib in glob.glob(pattern):
            try:
                ctypes.CDLL(lib, mode=mode)
            except OSError:
                pass
