"""Unit tests for the shared launcher/lifespan event emitter."""

import json
import re

import pytest

from src.launcher.events import emit_event, emit_phase

UTC_TS_PATTERN = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z"


@pytest.mark.unit
def test_emit_event_prints_single_json_line(capsys):
    emit_event({"event": "starting", "port": 8765})
    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if line.strip()]
    assert len(lines) == 1
    payload = json.loads(lines[0])
    ts = payload.pop("ts")
    assert re.fullmatch(UTC_TS_PATTERN, ts)
    assert payload == {"event": "starting", "port": 8765}


@pytest.mark.unit
def test_emit_event_does_not_mutate_caller_payload(capsys):
    payload = {"event": "ready", "port": 27182}
    emit_event(payload)
    capsys.readouterr()
    assert payload == {"event": "ready", "port": 27182}


@pytest.mark.unit
def test_emit_phase_emits_phase_event_with_ts(capsys):
    emit_phase("preparing_database")
    out = capsys.readouterr().out
    payload = json.loads(out.strip())
    ts = payload.pop("ts")
    assert re.fullmatch(UTC_TS_PATTERN, ts)
    assert payload == {"event": "phase", "phase": "preparing_database"}
