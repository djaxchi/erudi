"""By-link downloads are refused up front when the repo has nothing this engine runs.

Since the hardware-aware catalog (#95/#108) Erudi only ever downloads pre-built
artefacts: MLX repos on Apple Silicon, GGUF files on CPU/CUDA. There is no local
conversion any more (#408), so a Hugging Face repo pasted by the user that ships
neither (e.g. plain safetensors) must be rejected with an explicit
``InvalidInputException`` BEFORE any byte is transferred -- not downloaded in
full and then left unloadable on disk.

All HuggingFace API calls are mocked; no network access occurs.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.core import config
from src.core.exceptions import InvalidInputException
from src.domains.llms import services as llm_services


class Fake_GGUF_Engine:
    """llama.cpp stand-in (CPU/CUDA): consumes .gguf files."""

    USES_GGUF = True
    FORMAT_TAG = "gguf"

    @classmethod
    def is_runnable(cls, model_link: str) -> bool:
        return True


class Fake_MLX_Engine:
    """MLX stand-in (Apple Silicon): consumes repos tagged ``mlx``."""

    USES_GGUF = False
    FORMAT_TAG = "mlx"

    @classmethod
    def is_runnable(cls, model_link: str) -> bool:
        return True


def _fake_api(files, *, tags=(), library_name=None):
    api = MagicMock()
    api.repo_info.return_value = SimpleNamespace(
        siblings=[SimpleNamespace(rfilename=f, size=16) for f in files],
        tags=list(tags),
        library_name=library_name,
    )
    api.list_repo_files.return_value = list(files)
    return api


class _RecordingFs:
    """Fake HfFileSystem that records every transfer request."""

    def __init__(self):
        self.requested = []

    def get_file(self, remote, dest, callback):
        from pathlib import Path

        self.requested.append(remote)
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(b"\x00" * 16)
        callback.relative_update(16)


@pytest.fixture
def instant_eta(monkeypatch):
    async def _instant(self, interval=20.0):
        return None

    monkeypatch.setattr(llm_services.DownloadTracker, "monitor_eta", _instant)


async def _run_download(tmp_path, link="org/model"):
    return await llm_services.download_llm(
        model_link=link,
        model_id=1,
        temp_save_dir=str(tmp_path / "temp_1"),
        final_save_dir=str(tmp_path / "1"),
        job_id=None,
    )


@pytest.mark.unit
class TestAssertRepoHasEngineArtifact:
    """The pure check, independent of the download pipeline."""

    def test_gguf_engine_accepts_repo_with_a_gguf(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_Engine", Fake_GGUF_Engine)
        info = SimpleNamespace(tags=["gguf"], library_name=None)
        llm_services._assert_repo_has_engine_artifact(
            "org/model-GGUF", info, ["README.md", "model-Q4_K_M.gguf"]
        )

    def test_gguf_engine_rejects_mmproj_only_repo(self, monkeypatch):
        # mmproj-*.gguf is a vision projector, never the text model itself.
        monkeypatch.setattr(config, "LLM_Engine", Fake_GGUF_Engine)
        info = SimpleNamespace(tags=["gguf"], library_name=None)
        with pytest.raises(InvalidInputException, match="no gguf artefact"):
            llm_services._assert_repo_has_engine_artifact(
                "org/model", info, ["mmproj-model-f16.gguf", "config.json"]
            )

    def test_gguf_engine_rejects_plain_safetensors_repo(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_Engine", Fake_GGUF_Engine)
        info = SimpleNamespace(tags=["transformers", "safetensors"], library_name="transformers")
        with pytest.raises(InvalidInputException) as exc_info:
            llm_services._assert_repo_has_engine_artifact(
                "google/gemma-3-1b-it", info, ["config.json", "model.safetensors"]
            )
        message = str(exc_info.value.message)
        assert "google/gemma-3-1b-it" in message
        assert "no gguf artefact" in message
        assert "Fake_GGUF_Engine" in message

    def test_mlx_engine_accepts_repo_tagged_mlx(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_Engine", Fake_MLX_Engine)
        info = SimpleNamespace(tags=["mlx", "safetensors"], library_name="mlx")
        llm_services._assert_repo_has_engine_artifact(
            "mlx-community/model-4bit", info, ["config.json", "model.safetensors"]
        )

    def test_mlx_engine_accepts_repo_by_library_name_alone(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_Engine", Fake_MLX_Engine)
        info = SimpleNamespace(tags=[], library_name="mlx")
        llm_services._assert_repo_has_engine_artifact(
            "mlx-community/model-4bit", info, ["config.json", "model.safetensors"]
        )

    def test_mlx_engine_rejects_plain_safetensors_repo(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_Engine", Fake_MLX_Engine)
        info = SimpleNamespace(tags=["transformers", "safetensors"], library_name="transformers")
        with pytest.raises(InvalidInputException) as exc_info:
            llm_services._assert_repo_has_engine_artifact(
                "google/gemma-3-1b-it", info, ["config.json", "model.safetensors"]
            )
        message = str(exc_info.value.message)
        assert "google/gemma-3-1b-it" in message
        assert "no mlx artefact" in message
        assert "Fake_MLX_Engine" in message

    def test_mlx_engine_rejects_gguf_only_repo(self, monkeypatch):
        # A GGUF repo is the other engine family's format, not MLX's.
        monkeypatch.setattr(config, "LLM_Engine", Fake_MLX_Engine)
        info = SimpleNamespace(tags=["gguf"], library_name=None)
        with pytest.raises(InvalidInputException, match="no mlx artefact"):
            llm_services._assert_repo_has_engine_artifact(
                "org/model-GGUF", info, ["model-Q4_K_M.gguf"]
            )

    def test_repo_info_without_tags_is_not_a_crash(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_Engine", Fake_MLX_Engine)
        info = SimpleNamespace(tags=None, library_name=None)
        with pytest.raises(InvalidInputException, match="no mlx artefact"):
            llm_services._assert_repo_has_engine_artifact("org/model", info, ["model.safetensors"])


@pytest.mark.unit
class TestDownloadLlmRefusesBeforeTransfer:
    """download_llm raises before HfFileSystem is ever asked for a file."""

    async def test_gguf_engine_plain_safetensors_repo_downloads_nothing(
        self, monkeypatch, tmp_path, instant_eta
    ):
        monkeypatch.setattr(config, "LLM_Engine", Fake_GGUF_Engine)
        api = _fake_api(
            ["config.json", "model.safetensors"],
            tags=["transformers", "safetensors"],
            library_name="transformers",
        )
        fs = _RecordingFs()
        monkeypatch.setattr(llm_services, "HfApi", lambda token=None: api)
        monkeypatch.setattr(llm_services, "HfFileSystem", lambda token=None: fs)

        with pytest.raises(InvalidInputException, match="no gguf artefact"):
            await _run_download(tmp_path, link="google/gemma-3-1b-it")

        assert fs.requested == []
        assert not any((tmp_path / "temp_1").iterdir())

    async def test_mlx_engine_plain_safetensors_repo_downloads_nothing(
        self, monkeypatch, tmp_path, instant_eta
    ):
        monkeypatch.setattr(config, "LLM_Engine", Fake_MLX_Engine)
        api = _fake_api(
            ["config.json", "model.safetensors"],
            tags=["transformers", "safetensors"],
            library_name="transformers",
        )
        fs = _RecordingFs()
        monkeypatch.setattr(llm_services, "HfApi", lambda token=None: api)
        monkeypatch.setattr(llm_services, "HfFileSystem", lambda token=None: fs)

        with pytest.raises(InvalidInputException, match="no mlx artefact"):
            await _run_download(tmp_path, link="google/gemma-3-1b-it")

        assert fs.requested == []
        assert not any((tmp_path / "temp_1").iterdir())

    async def test_gguf_engine_gguf_repo_still_downloads(self, monkeypatch, tmp_path, instant_eta):
        monkeypatch.setattr(config, "LLM_Engine", Fake_GGUF_Engine)
        api = _fake_api(["config.json", "model-Q4_K_M.gguf"], tags=["gguf"], library_name=None)
        fs = _RecordingFs()
        monkeypatch.setattr(llm_services, "HfApi", lambda token=None: api)
        monkeypatch.setattr(llm_services, "HfFileSystem", lambda token=None: fs)

        await _run_download(tmp_path, link="org/model-GGUF")

        assert "org/model-GGUF/model-Q4_K_M.gguf" in fs.requested
        assert (tmp_path / "1" / "model-Q4_K_M.gguf").exists()

    async def test_mlx_engine_mlx_repo_still_downloads(self, monkeypatch, tmp_path, instant_eta):
        monkeypatch.setattr(config, "LLM_Engine", Fake_MLX_Engine)
        api = _fake_api(["config.json", "model.safetensors"], tags=["mlx"], library_name="mlx")
        fs = _RecordingFs()
        monkeypatch.setattr(llm_services, "HfApi", lambda token=None: api)
        monkeypatch.setattr(llm_services, "HfFileSystem", lambda token=None: fs)

        await _run_download(tmp_path, link="mlx-community/model-4bit")

        assert "mlx-community/model-4bit/model.safetensors" in fs.requested
        assert (tmp_path / "1" / "model.safetensors").exists()
