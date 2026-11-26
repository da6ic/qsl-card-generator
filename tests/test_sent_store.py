"""wavelog_sent.json: robust schreiben, Kaputtes nie still überschreiben (1.3),
offene Markierungen überleben einen Neustart (2.2)."""

from __future__ import annotations

import json

import pytest

from qslcards.wavelog import sent_store

API = "https://log.example.org/index.php/api/v2"


def test_missing_file_is_empty(tmp_path):
    assert sent_store.load(tmp_path / "x.json", API) == set()
    assert sent_store.load_pending(tmp_path / "x.json", API) == []


def test_add_and_load_roundtrip_per_instance(tmp_path):
    path = tmp_path / "sent.json"
    sent_store.add(path, API, ["10", "9"])
    sent_store.add(path, "https://other/index.php/api/v2", ["1"])
    assert sent_store.load(path, API) == {"9", "10"}
    assert sent_store.load(path, "https://other/index.php/api/v2") == {"1"}
    assert json.loads(path.read_text())["version"] == 2


def test_old_format_is_still_read_and_upgraded(tmp_path):
    path = tmp_path / "sent.json"
    path.write_text(json.dumps({API: ["4", "5"]}), encoding="utf-8")
    assert sent_store.load(path, API) == {"4", "5"}
    sent_store.add(path, API, ["6"])
    assert sent_store.load(path, API) == {"4", "5", "6"}


@pytest.mark.parametrize("damage", ['{"' + API + '": ["4", ', "[1, 2]", "\x00\x01"])
def test_broken_file_is_reported_and_never_overwritten(tmp_path, damage):
    path = tmp_path / "sent.json"
    path.write_text(damage, encoding="utf-8")
    with pytest.raises(sent_store.SentStoreError):
        sent_store.load(path, API)
    with pytest.raises(sent_store.SentStoreError):
        sent_store.add(path, API, ["7"])
    assert path.read_text(encoding="utf-8") == damage  # unverändert


def test_pending_marks_roundtrip_and_leave_when_sent(tmp_path):
    path = tmp_path / "sent.json"
    sent_store.set_pending(
        path, API, [sent_store.PendingMark("10", "B"), sent_store.PendingMark("11", None)]
    )
    pending = sent_store.load_pending(path, API)
    assert [(m.qso_id, m.via) for m in pending] == [("10", "B"), ("11", None)]
    sent_store.add(path, API, ["10"])
    assert [m.qso_id for m in sent_store.load_pending(path, API)] == ["11"]
    assert sent_store.load(path, API) == {"10"}


def test_remove_allows_a_deliberate_reprint(tmp_path):
    path = tmp_path / "sent.json"
    sent_store.add(path, API, ["1", "2"])
    sent_store.remove(path, API, ["1"])
    assert sent_store.load(path, API) == {"2"}
