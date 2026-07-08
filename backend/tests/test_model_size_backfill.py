"""One-shot backfill of already-downloaded models' displayed size (#220).

``Database_Seeder.backfill_local_model_sizes`` rewrites ``metadata.size`` /
``disk_size_gb`` for local (local==1) rows whose weights exist, from the REAL
on-disk footprint, and skips rows whose directory is missing (orphans are
legitimate since #225/#208) without crashing. Runs against the real test
cluster so the SQLAlchemy query + commit path is exercised end to end.
"""
import pytest

from src.database.seed import Database_Seeder
from src.entities.Llm import Llm
from src.utils.hf_model_metadata import measure_dir_size_gb

pytestmark = pytest.mark.integration


def _make_local_model(db, tmp_path, name, size_line):
    """Create a downloaded (local==1) model with a small on-disk artifact."""
    d = tmp_path / name
    d.mkdir()
    (d / "model-q4_k_m.gguf").write_bytes(b"\x00" * 4096)
    llm = Llm(
        name=name, local=1, type="qwen", param_size=7.0, link=str(d),
        model_metadata=f"Model ID: org/{name}\n{size_line}\nParameters: 7B",
    )
    db.add(llm)
    db.commit()
    db.refresh(llm)
    return llm


def test_backfill_corrects_stale_size_for_existing_dir(test_db_session, tmp_path):
    llm = _make_local_model(test_db_session, tmp_path, "good", "Size: ~40.2 GB")

    corrected = Database_Seeder().backfill_local_model_sizes(test_db_session)
    test_db_session.refresh(llm)

    assert corrected >= 1
    # The catalog guess is replaced by the measured on-disk size + numeric field.
    assert "40.2" not in llm.model_metadata
    measured = measure_dir_size_gb(llm.link)
    assert f"Disk Size GB: {measured:.2f}" in llm.model_metadata
    assert f"Size: ~{measured:.1f} GB" in llm.model_metadata
    # Unrelated metadata lines are preserved.
    assert "Parameters: 7B" in llm.model_metadata


def test_backfill_skips_missing_dir_without_crashing(test_db_session, tmp_path):
    original = "Model ID: org/orphan\nSize: ~40.2 GB\nParameters: 7B"
    orphan = Llm(
        name="orphan", local=1, type="qwen", param_size=7.0,
        link=str(tmp_path / "gone"), model_metadata=original,
    )
    test_db_session.add(orphan)
    test_db_session.commit()
    test_db_session.refresh(orphan)

    # Missing weights dir: skipped silently, metadata untouched, no exception.
    Database_Seeder().backfill_local_model_sizes(test_db_session)
    test_db_session.refresh(orphan)

    assert orphan.model_metadata == original


def test_backfill_is_idempotent_on_stable_size(test_db_session, tmp_path):
    llm = _make_local_model(test_db_session, tmp_path, "stable", "Size: ~40.2 GB")

    Database_Seeder().backfill_local_model_sizes(test_db_session)
    test_db_session.refresh(llm)
    after_first = llm.model_metadata

    # A second pass over an already-correct row rewrites nothing further.
    Database_Seeder().backfill_local_model_sizes(test_db_session)
    test_db_session.refresh(llm)
    assert llm.model_metadata == after_first
