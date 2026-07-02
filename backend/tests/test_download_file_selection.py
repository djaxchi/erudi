"""Tests for download file selection (_select_download_files) and total-size accuracy.

Covers issue #170: for GGUF repos the download total must be computed from the
files actually downloaded (single best quant + mmproj + small aux), not from the
whole repository. The selection logic is a pure helper so it can be tested
without mocking HuggingFace.

All HuggingFace API calls are mocked; no network access occurs.
"""
import pytest
from unittest.mock import patch, MagicMock

from src.core import config
from src.domains.llms.services import _select_download_files, download_llm


TEN_MB = 10 * 1024 * 1024


class Fake_GGUF_Engine:
    """Minimal engine stand-in: GGUF-based, everything runnable."""

    USES_GGUF = True

    @classmethod
    def is_runnable(cls, model_link: str) -> bool:
        return True


class TestSelectDownloadFilesGguf:
    """GGUF repos: only the best quant + mmproj + small aux files are selected."""

    def setup_method(self):
        self.file_sizes = {
            "model-F16.gguf": 8_000_000_000,
            "model-Q8_0.gguf": 3_000_000_000,
            "model-Q4_K_M.gguf": 800_000_000,
            "mmproj-model-f16.gguf": 600_000_000,
            "config.json": 2_000,
            "README.md": 5_000,
            "tokenizer.model": 15 * 1024 * 1024,  # aux >= 10 MB -> excluded
        }
        self.all_repo_files = list(self.file_sizes.keys())

    def test_picks_best_quant_plus_mmproj_plus_small_aux(self):
        """Selection is exactly best gguf + mmproj + aux files under 10 MB."""
        selection = _select_download_files(self.all_repo_files, self.file_sizes, uses_gguf=True)

        assert selection.best_gguf == "model-Q4_K_M.gguf"
        assert selection.mmproj_files == ["mmproj-model-f16.gguf"]
        assert set(selection.small_aux) == {"config.json", "README.md"}
        assert set(selection.files) == {
            "model-Q4_K_M.gguf",
            "mmproj-model-f16.gguf",
            "config.json",
            "README.md",
        }

    def test_total_from_selection_differs_from_whole_repo_sum(self):
        """The size computed from the selection must NOT be the whole-repo sum (#170)."""
        selection = _select_download_files(self.all_repo_files, self.file_sizes, uses_gguf=True)

        selected_total = sum(self.file_sizes.get(f, 0) for f in selection.files)
        whole_repo_total = sum(self.file_sizes.values())

        assert selected_total == 800_000_000 + 600_000_000 + 2_000 + 5_000
        assert selected_total != whole_repo_total

    def test_mmproj_included_and_counted_in_total(self):
        """mmproj gguf files ride along with the main quant and count in the total."""
        selection = _select_download_files(self.all_repo_files, self.file_sizes, uses_gguf=True)

        assert "mmproj-model-f16.gguf" in selection.files
        selected_total = sum(self.file_sizes.get(f, 0) for f in selection.files)
        assert selected_total >= 600_000_000

    def test_aux_boundary_10mb_excluded_below_included(self):
        """Aux file of exactly 10 MB is excluded; 10 MB - 1 byte is included."""
        file_sizes = {
            "model-Q4_0.gguf": 500_000_000,
            "at_limit.bin": TEN_MB,
            "under_limit.bin": TEN_MB - 1,
        }
        selection = _select_download_files(list(file_sizes.keys()), file_sizes, uses_gguf=True)

        assert "under_limit.bin" in selection.files
        assert "at_limit.bin" not in selection.files

    def test_no_gguf_returns_empty_selection(self):
        """Contract: with no .gguf in the repo the helper signals it via best_gguf=None."""
        file_sizes = {"config.json": 2_000, "model.safetensors": 4_000_000_000}
        selection = _select_download_files(list(file_sizes.keys()), file_sizes, uses_gguf=True)

        assert selection.best_gguf is None
        assert selection.files == []


class TestSelectDownloadFilesNonGguf:
    """Non-GGUF repos: every repo file with a known size is selected."""

    def test_selects_all_files_present_in_file_sizes(self):
        """All files present in file_sizes are selected; exclusions are respected."""
        all_repo_files = [
            "model-00001-of-00002.safetensors",
            "model-00002-of-00002.safetensors",
            "config.json",
            "consolidated.safetensors",  # in FILES_TO_EXCLUDE -> absent from file_sizes
        ]
        file_sizes = {
            "model-00001-of-00002.safetensors": 5_000_000_000,
            "model-00002-of-00002.safetensors": 5_000_000_000,
            "config.json": 2_000,
        }
        selection = _select_download_files(all_repo_files, file_sizes, uses_gguf=False)

        assert set(selection.files) == set(file_sizes.keys())
        assert "consolidated.safetensors" not in selection.files


class TestDownloadLlmNoGgufError:
    """download_llm still raises the documented exception when a GGUF repo has no .gguf."""

    async def test_download_llm_raises_exact_message(self, tmp_path):
        """The exact 'No .gguf files found in repo <id>' message surfaces from download_llm."""
        repo_id = "fake-org/fake-gguf-repo"
        sibling = MagicMock()
        sibling.rfilename = "config.json"
        sibling.size = 2_000
        repo_info = MagicMock()
        repo_info.siblings = [sibling]

        mock_api = MagicMock()
        mock_api.repo_info.return_value = repo_info
        mock_api.list_repo_files.return_value = ["config.json"]

        with patch("src.domains.llms.services.HfApi", return_value=mock_api), \
             patch("src.domains.llms.services.HfFileSystem", return_value=MagicMock()), \
             patch.object(config, "LLM_Engine", Fake_GGUF_Engine):
            with pytest.raises(Exception, match=f"No .gguf files found in repo {repo_id}"):
                await download_llm(
                    model_link=repo_id,
                    model_id=1,
                    temp_save_dir=str(tmp_path / "temp"),
                    final_save_dir=str(tmp_path / "final"),
                    job_id=None,
                )
