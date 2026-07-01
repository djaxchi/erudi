"""Unit tests for the shared launcher/lifespan event emitter."""

import json

import pytest

from src.launcher.events import emit_event, emit_phase


@pytest.mark.unit
def test_emit_event_prints_single_json_line(capsys):
    emit_event({"event": "starting", "port": 8765})
    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if line.strip()]
    assert len(lines) == 1
    assert json.loads(lines[0]) == {"event": "starting", "port": 8765}


@pytest.mark.unit
def test_emit_phase_emits_phase_event(capsys):
    emit_phase("preparing_database")
    out = capsys.readouterr().out
    assert json.loads(out.strip()) == {"event": "phase", "phase": "preparing_database"}
