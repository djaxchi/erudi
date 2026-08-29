"""Download destinations must stay inside the model directory (#405).

The downloader builds every destination from file names LISTED BY THE HUB
(``HfApi.list_repo_files``). Any repository can be downloaded by link, so a
hostile repo whose file list carries ``../../x``, an absolute path, a Windows
drive or UNC form, a backslash or a NUL byte would have written outside
``models/<id>/``.

The rule is refuse, never normalise: the loaders (mlx-vlm, llama-server)
expect the repo's own names and subfolders, so rewriting a name would silently
produce a broken model and hide a hostile repo. ``resolve_member_path`` is a
pure helper checked with ``PurePosixPath``/``PureWindowsPath`` explicitly so
it behaves the same on the three CI legs. No network anywhere in this file.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.core import config
from src.core.exceptions import InvalidInputException
from src.domains.llms import services as llm_services
from src.domains.llms.services import download_files_concurrent, resolve_member_path


REJECTED_MEMBERS = [
    pytest.param("", id="empty"),
    pytest.param("\x00", id="nul-only"),
    pytest.param("config\x00.json", id="nul-inside"),
    pytest.param("..", id="dotdot-only"),
    pytest.param("../x", id="dotdot-leading"),
    pytest.param("../../x", id="dotdot-twice"),
    pytest.param("a/../x", id="dotdot-middle"),
    pytest.param("x/..", id="dotdot-trailing"),
    pytest.param(".", id="dot-only"),
    pytest.param("./x", id="dot-leading"),
    pytest.param("a/./x", id="dot-middle"),
    pytest.param("/etc/passwd", id="posix-absolute"),
    pytest.param("/x", id="posix-root-child"),
    pytest.param("C:\\x", id="windows-drive-backslash"),
    pytest.param("C:/x", id="windows-drive-slash"),
    pytest.param("C:x", id="windows-drive-relative"),
    pytest.param("\\\\server\\share\\x", id="windows-unc-backslash"),
    pytest.param("//server/share/x", id="windows-unc-slash"),
    pytest.param("a\\b", id="backslash-separator"),
    pytest.param("a//b", id="empty-segment"),
    pytest.param("a/", id="trailing-slash"),
    pytest.param("/", id="slash-only"),
]

ACCEPTED_MEMBERS = [
    pytest.param("config.json", id="flat"),
    pytest.param("model-00001-of-00004.safetensors", id="shard"),
    pytest.param("snapshots/abc/config.json", id="nested"),
    pytest.param("a.b/c-d_e.json", id="dots-and-dashes"),
    pytest.param(".gitattributes", id="dotfile"),
    pytest.param("..foo", id="two-dots-prefix-is-a-name"),
    pytest.param("dir/...", id="three-dots-is-a-name"),
]


@pytest.mark.unit
class TestResolveMemberPath:

    @pytest.mark.parametrize("member", REJECTED_MEMBERS)
    def test_rejects_every_escaping_form(self, tmp_path, member):
        with pytest.raises(InvalidInputException) as exc:
            resolve_member_path(tmp_path, member)
        message = str(exc.value)
        assert message.isascii(), message
        # Nothing was created on disk while checking.
        assert list(tmp_path.iterdir()) == []

    @pytest.mark.parametrize("member", ACCEPTED_MEMBERS)
    def test_accepts_the_hub_layout_unchanged(self, tmp_path, member):
        dest = resolve_member_path(tmp_path, member)
        assert dest == tmp_path / member
        assert dest.resolve().is_relative_to(tmp_path.resolve())
        # Refuse, never normalise: the Hub name is reproduced verbatim.
        assert dest.relative_to(tmp_path).as_posix() == member

    def test_message_names_the_offender_truncated_and_ascii(self, tmp_path):
        member = "../" + ("\u00e9" * 300)
        with pytest.raises(InvalidInputException) as exc:
            resolve_member_path(tmp_path, member)
        message = str(exc.value)
        assert message.isascii()
        assert "../" in message
        assert len(message) < 400

    def test_root_may_be_a_string(self, tmp_path):
        dest = resolve_member_path(str(tmp_path), "config.json")
        assert dest == tmp_path / "config.json"

    def test_symlinked_root_still_contains(self, tmp_path):
        real = tmp_path / "real"
        real.mkdir()
        link = tmp_path / "link"
        try:
            link.symlink_to(real, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("symlinks unavailable on this host")
        dest = resolve_member_path(link, "sub/config.json")
        assert dest.resolve().is_relative_to(real.resolve())


# =====================================================================
# UNIT - download_files_concurrent refuses before opening anything
# =====================================================================

@pytest.mark.unit
class TestDownloadFilesConcurrentContainment:

    async def test_escaping_shard_is_refused_before_any_transfer(self, tmp_path):
        requested: list[str] = []

        class Fs:
            def get_file(self, remote, dest, cb):
                requested.append(remote)

        tasks = [("org/model", "ok.safetensors"), ("org/model", "../../evil.safetensors")]
        with pytest.raises(InvalidInputException):
            await download_files_concurrent(Fs(), MagicMock(), tasks, str(tmp_path / "temp_1"))

        assert requested == []
        assert not (tmp_path / "evil.safetensors").exists()
        assert not (tmp_path.parent / "evil.safetensors").exists()


# =====================================================================
# UNIT - download_llm validates the WHOLE selection before fetching a byte
# =====================================================================

def _fake_api(files):
    api = MagicMock()
    api.repo_info.return_value = SimpleNamespace(
        siblings=[SimpleNamespace(rfilename=f, size=16) for f in files]
    )
    api.list_repo_files.return_value = list(files)
    return api


@pytest.mark.unit
class TestDownloadLlmFailsFastOnHostileListing:

    @pytest.mark.parametrize(
        "hostile",
        [
            pytest.param("../../evil.safetensors", id="shard-escapes"),
            pytest.param("../evil.json", id="misc-escapes"),
            pytest.param("/etc/passwd", id="absolute"),
        ],
    )
    async def test_nothing_is_fetched_and_the_job_fails(self, monkeypatch, tmp_path, hostile):
        monkeypatch.setattr(
            config, "LLM_Engine",
            SimpleNamespace(is_runnable=lambda link: True, USES_GGUF=False),
        )
        files = ["config.json", "model-00001-of-00002.safetensors", hostile]
        monkeypatch.setattr(llm_services, "HfApi", lambda token=None: _fake_api(files))

        requested: list[str] = []

        class Fs:
            def get_file(self, remote, dest, cb):
                requested.append(remote)

        monkeypatch.setattr(llm_services, "HfFileSystem", lambda token=None: Fs())

        temp_dir = tmp_path / "temp_1"
        final_dir = tmp_path / "1"
        with pytest.raises(InvalidInputException) as exc:
            await llm_services.download_llm(
                model_link="org/model", model_id=1,
                temp_save_dir=str(temp_dir), final_save_dir=str(final_dir), job_id=None,
            )

        # The message the job-failure path stores names the offending member.
        assert hostile.split("/")[-1] in str(exc.value)
        # Not a single byte was requested, even for the legitimate files.
        assert requested == []
        # The temp dir is still empty and nothing landed outside it.
        assert list(temp_dir.iterdir()) == []
        assert not (tmp_path / "evil.safetensors").exists()
        assert not (tmp_path / "evil.json").exists()
