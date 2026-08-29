"""Cancelling a download must stop the transfer, not merely flag it (#377).

Cancellation is signal-and-check by design (see #372): `cancel_download_job`
flips `DownloadTracker._cancelled` and returns. Before this fix nothing on the
download side ever looked at that flag until every shard had been transferred
to the end, so a 3 GB model cancelled at 25 % kept downloading for minutes,
and the endpoint then logged "completed successfully" for a cancelled job.

Three guarantees are pinned here:
  1. the shard loop does not start a shard once the tracker is cancelled;
  2. the per-chunk fsspec callback aborts the in-flight transfer;
  3. the endpoint's completion log reflects the real outcome.
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.core import config
from src.domains.llms import endpoints as llm_endpoints
from src.domains.llms import repository as llm_repo_mod
from src.domains.llms import services as llm_services
from src.domains.llms.services import DownloadCancelled, DownloadTracker, make_callback
from src.entities.DownloadJob import DownloadJobModel

SHARDS = [f"model-0000{i}-of-00003.safetensors" for i in (1, 2, 3)]


def _tracker(total: int) -> DownloadTracker:
    tracker = DownloadTracker()
    tracker.total_bytes = total
    return tracker


# =====================================================================
# UNIT - the shard loop stops scheduling once cancelled
# =====================================================================

@pytest.mark.unit
class TestShardLoopHonoursCancel:

    async def test_remaining_shards_are_never_requested_after_cancel(self, tmp_path):
        tracker = _tracker(3 * 16)
        callback = make_callback(tracker)
        requested: list[str] = []

        class Fs:
            def get_file(self, remote, dest, cb):
                # The cancel lands while this (first) shard is in flight; it
                # finishes on its own, the others must never be started.
                requested.append(remote)
                tracker.cancel()
                Path(dest).write_bytes(b"\x00" * 16)

        # One worker so the shards run strictly one after the other; the
        # assertion is about scheduling, not about how many threads there are.
        asyncio.get_running_loop().set_default_executor(ThreadPoolExecutor(max_workers=1))

        with pytest.raises(DownloadCancelled):
            await llm_services.download_files_concurrent(
                Fs(), callback, [("org/m", s) for s in SHARDS], str(tmp_path), tracker=tracker
            )

        assert requested == ["org/m/" + SHARDS[0]]
        assert not (tmp_path / SHARDS[1]).exists()
        assert not (tmp_path / SHARDS[2]).exists()

    async def test_already_cancelled_tracker_requests_nothing(self, tmp_path):
        tracker = _tracker(16)
        tracker.cancel()
        fs = MagicMock()

        with pytest.raises(DownloadCancelled):
            await llm_services.download_files_concurrent(
                fs, make_callback(tracker), [("org/m", SHARDS[0])], str(tmp_path), tracker=tracker
            )

        fs.get_file.assert_not_called()


# =====================================================================
# UNIT - the per-chunk callback aborts the in-flight transfer
# =====================================================================

@pytest.mark.unit
class TestChunkCallbackHonoursCancel:

    def test_callback_counts_until_cancel_then_raises(self):
        tracker = _tracker(100)
        callback = make_callback(tracker)

        callback.relative_update(10)
        assert tracker.downloaded_bytes == 10

        tracker.cancel()
        with pytest.raises(DownloadCancelled):
            callback.relative_update(10)

    async def test_in_flight_transfer_exits_promptly(self, tmp_path):
        tracker = _tracker(100)
        served: list[int] = []

        class Fs:
            def get_file(self, remote, dest, cb):
                for i in range(100):
                    served.append(i)
                    if i == 2:
                        tracker.cancel()
                    cb.relative_update(1)

        with pytest.raises(DownloadCancelled):
            await llm_services.download_files_concurrent(
                Fs(), make_callback(tracker), [("org/m", SHARDS[0])], str(tmp_path), tracker=tracker
            )

        # Three chunks were served (the third is the one that noticed), not 100.
        assert served == [0, 1, 2]


# =====================================================================
# UNIT - download_llm turns the abort into a clean early return
# =====================================================================

def _fake_api(files):
    api = MagicMock()
    api.repo_info.return_value = SimpleNamespace(
        siblings=[SimpleNamespace(rfilename=f, size=16) for f in files]
    )
    api.list_repo_files.return_value = list(files)
    return api


@pytest.mark.unit
class TestDownloadLlmCancelledMidTransfer:

    async def test_cancel_mid_shard_stops_transfer_and_skips_finalization(
        self, monkeypatch, tmp_path, caplog
    ):
        monkeypatch.setattr(
            config, "LLM_Engine",
            SimpleNamespace(is_runnable=lambda link: True, USES_GGUF=False),
        )
        files = ["config.json", *SHARDS]
        monkeypatch.setattr(llm_services, "HfApi", lambda token=None: _fake_api(files))

        async def instant_eta(self, interval=20.0):
            return None

        monkeypatch.setattr(DownloadTracker, "monitor_eta", instant_eta)
        # The DB progress thread is covered in test_llms_gaps; keep it out of here.
        monkeypatch.setattr(llm_services, "update_db_with_progress", lambda *a, **k: None)

        requested: list[str] = []

        class Fs:
            def get_file(self, remote, dest, cb):
                requested.append(remote)
                Path(dest).parent.mkdir(parents=True, exist_ok=True)
                Path(dest).write_bytes(b"\x00" * 16)
                if remote.endswith(SHARDS[0]):
                    # User hits cancel while the first shard is streaming.
                    llm_services.get_active_download_tracker(42).cancel()
                cb.relative_update(16)

        monkeypatch.setattr(llm_services, "HfFileSystem", lambda token=None: Fs())
        asyncio.get_running_loop().set_default_executor(ThreadPoolExecutor(max_workers=1))

        temp_dir = tmp_path / "temp_1"
        final_dir = tmp_path / "1"
        with caplog.at_level(logging.INFO, logger="erudi"):
            result = await llm_services.download_llm(
                model_link="org/model", model_id=1,
                temp_save_dir=str(temp_dir), final_save_dir=str(final_dir), job_id=42,
            )

        assert result == str(temp_dir)
        # Only config.json and the in-flight shard were ever requested.
        assert requested == ["org/model/config.json", "org/model/" + SHARDS[0]]
        # Nothing was promoted to the final directory.
        assert not any(final_dir.iterdir())
        messages = [r.message for r in caplog.records]
        assert any("job 42" in m and "cancelled" in m for m in messages)
        assert not any("All shards downloaded" in m for m in messages)
        # Tracker is unregistered on the way out, like every other exit path.
        assert llm_services.get_active_download_tracker(42) is None


# =====================================================================
# UNIT - the endpoint logs the real outcome
# =====================================================================

def _session_with(monkeypatch, job_row, llm_row):
    session = MagicMock()

    def query(model):
        q = MagicMock()
        q.get.return_value = job_row if model is DownloadJobModel else llm_row
        return q

    session.query.side_effect = query
    monkeypatch.setattr(llm_endpoints, "SessionLocal", lambda: session)
    return session


@pytest.mark.unit
class TestRunDownloadTaskOutcomeLog:

    def _arm(self, monkeypatch, *, ends_as: str):
        job = SimpleNamespace(status="pending", error_message=None, updated_at=None, progress=0.0)
        llm = SimpleNamespace(link="/models/1", model_metadata=None, local=2)
        session = _session_with(monkeypatch, job, llm)

        async def download(**kwargs):
            # The cancel endpoint flips the row while the transfer runs.
            job.status = ends_as

        monkeypatch.setattr(llm_endpoints, "download_llm", download)
        monkeypatch.setattr(config, "LLM_Engine", SimpleNamespace())  # no validator
        monkeypatch.setattr(llm_endpoints, "measure_dir_size_bytes", lambda p: 0)
        for name in ("detect_supports_tools", "detect_wire_tools", "detect_supports_vision"):
            monkeypatch.setattr(llm_repo_mod, name, lambda p: None)
        return job, session

    def test_cancelled_job_is_not_logged_as_completed(self, monkeypatch, caplog):
        job, _ = self._arm(monkeypatch, ends_as="cancelled")

        with caplog.at_level(logging.INFO, logger="erudi"):
            llm_endpoints._run_download_task("org/model", 1, "/tmp/t", "/tmp/f", job_id=7)

        messages = [r.message for r in caplog.records]
        assert not any("completed successfully" in m for m in messages)
        assert any("job 7" in m and "cancelled" in m for m in messages)
        assert job.status == "cancelled"

    def test_completed_job_still_logs_success(self, monkeypatch, caplog):
        job, _ = self._arm(monkeypatch, ends_as="running")

        with caplog.at_level(logging.INFO, logger="erudi"):
            llm_endpoints._run_download_task("org/model", 1, "/tmp/t", "/tmp/f", job_id=8)

        messages = [r.message for r in caplog.records]
        assert any("Download job 8 completed successfully" in m for m in messages)
        assert job.status == "completed"
