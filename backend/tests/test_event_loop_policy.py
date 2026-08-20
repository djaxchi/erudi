"""The test harness must run under production's asyncio event loop policy (#335).

`run.py:set_event_loop_policy` installs `WindowsSelectorEventLoopPolicy` on
Windows, because psycopg refuses to run in async mode on a `ProactorEventLoop`
(`InterfaceError: Psycopg cannot use the 'ProactorEventLoop'`). The harness did
not do the same, so pytest-asyncio built its loops on Windows' default Proactor
policy and every test touching the async checkpointer or the vector store died
on a configuration the shipped app never runs in.

These tests pin the harness to production's choice. They are meaningful on both
platforms: on Windows they go red the moment `conftest.py` stops calling
`run.set_event_loop_policy()`, on POSIX they assert that the call stays the
no-op it is supposed to be there.
"""

import asyncio
import platform

import pytest


@pytest.mark.unit
def test_harness_policy_is_the_one_run_py_installs():
    """conftest must have already installed production's policy at import time.

    Calling `run.set_event_loop_policy()` again is idempotent, so the policy
    type cannot change unless the harness never applied it in the first place.
    """
    import run

    before = type(asyncio.get_event_loop_policy())
    run.set_event_loop_policy()
    after = type(asyncio.get_event_loop_policy())

    assert after is before


@pytest.mark.unit
def test_policy_is_selector_on_windows_and_untouched_elsewhere():
    """Windows gets the selector policy; POSIX keeps whatever asyncio picked."""
    policy_name = type(asyncio.get_event_loop_policy()).__name__

    if platform.system() == "Windows":
        assert policy_name == "WindowsSelectorEventLoopPolicy"
    else:
        assert "Selector" not in policy_name  # no Windows-only policy leaked in


@pytest.mark.unit
async def test_running_loop_is_psycopg_compatible():
    """The loop tests actually run on must never be a ProactorEventLoop.

    This is the property psycopg checks: it raises `InterfaceError` on a
    Proactor loop regardless of which policy produced it.
    """
    loop_name = type(asyncio.get_running_loop()).__name__

    assert "Proactor" not in loop_name
