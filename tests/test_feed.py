"""Tests for alert-feed parsing, classification and failover.
Run: QT_QPA_PLATFORM=offscreen python -m pytest tests/ -q"""
import os, sys, json, types
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest, requests
import red_alert as ra


# ── classification ────────────────────────────────────────────
@pytest.mark.parametrize("data,kind", [
    ({"cat": "1", "title": "ירי רקטות וטילים"}, "alert"),
    ({"cat": "6", "title": "חדירת כלי טיס עוין"}, "alert"),
    ({"cat": "101", "title": "בדיקה"}, "drill"),
    ({"cat": "103", "title": "תרגיל רעידת אדמה"}, "drill"),
    ({"cat": "1", "title": "תרגיל - ירי רקטות"}, "drill"),
    ({"cat": "10", "title": "בדקות הקרובות צפויות להתקבל התרעות באזורך"}, "early_warning"),
    ({"cat": "10", "title": "האירוע הסתיים"}, "event_ended"),
    ({"cat": "10", "title": "ירי רקטות וטילים - האירוע הסתיים"}, "event_ended"),
    ({"cat": "10", "title": "עדכון", "desc": "ניתן לצאת מהמרחב המוגן"}, "event_ended"),
    ({"cat": "10", "title": "מבזק"}, "notice"),
])
def test_classify(data, kind):
    assert ra.classify_oref(data) == kind


# ── primary parsing: failures must raise, never look "quiet" ──
def test_quiet_responses():
    for t in ["", "﻿", "  \r\n", "{}", "null", "﻿\r\n"]:
        assert ra.parse_oref_response(200, t) is None

def test_alert_response():
    body = "﻿" + json.dumps({"id": "1", "cat": "1", "title": "x", "data": ["a"]})
    assert ra.parse_oref_response(200, body)["id"] == "1"

@pytest.mark.parametrize("code,text", [
    (403, "<html>Access Denied</html>"), (500, ""), (200, "<html>error</html>"),
    (200, "not json"), (200, "[1,2]"),
])
def test_primary_errors_raise(code, text):
    with pytest.raises(ra.FeedError):
        ra.parse_oref_response(code, text)


# ── backup parsing ────────────────────────────────────────────
def test_backup_quiet_and_drill():
    assert ra.parse_backup_response(200, "[]") is None
    assert ra.parse_backup_response(200, json.dumps(
        [{"notificationId": "n", "time": 1, "threat": 0, "isDrill": True, "cities": ["a"]}])) is None

def test_backup_alert_merges():
    d = ra.parse_backup_response(200, json.dumps([
        {"notificationId": "a", "time": 1, "threat": 0, "isDrill": False, "cities": ["x", "y"]},
        {"notificationId": "b", "time": 2, "threat": 5, "isDrill": False, "cities": ["y", "z"]},
    ]))
    assert d["data"] == ["y", "z", "x"] and d["cat"] == "2" and d["id"].startswith("backup-")
    assert ra.classify_oref(d) == "alert"

def test_backup_errors():
    for code, t in [(502, ""), (200, "<html>"), (200, "{}")]:
        with pytest.raises(ra.FeedError):
            ra.parse_backup_response(code, t)


# ── worker loop with fake network ─────────────────────────────
class FakeResp:
    def __init__(self, code, text): self.status_code, self.text = code, text

class Cfg:
    def __init__(self, locs=()): self.d = {"locations": list(locs), "poll_interval": 0}
    def get(self, k, d=None): return self.d.get(k, d)

def run_worker(primary_seq, backup_seq, locs=()):
    """Run the worker for len(primary_seq) polls. Items are FakeResp or Exception."""
    w = ra.AlertWorker(Cfg(locs))
    events = []
    w.new_alert.connect(lambda d: events.append(("alert", d.get("id"))))
    w.alert_cleared.connect(lambda: events.append(("clear",)))
    w.feed_status.connect(lambda lvl, m: events.append(("feed", lvl)))
    w.new_notice.connect(lambda k, d: events.append(("notice", k)))
    p, b = list(primary_seq), list(backup_seq)
    n = len(p)
    def fake_get(self, url, timeout=None):
        src = p if url == ra.OREF_URL else b
        item = src.pop(0) if src else FakeResp(200, "")
        if url == ra.OREF_URL and not p: w._running = False
        if isinstance(item, Exception): raise item
        return item
    orig = requests.Session.get
    requests.Session.get = fake_get
    try: w.run()
    finally: requests.Session.get = orig
    return events

ALERT = FakeResp(200, json.dumps({"id": "A1", "cat": "1", "title": "ירי רקטות וטילים", "data": ["תל אביב"]}))
QUIET = FakeResp(200, "﻿")
BLOCK = FakeResp(403, "<html>Access Denied</html>")

def test_geoblock_is_not_quiet_and_warns():
    ev = run_worker([ALERT] + [BLOCK] * 5, [requests.exceptions.ConnectionError()] * 5)
    assert ("alert", "A1") in ev
    assert ("clear",) not in ev           # an outage must not produce an all-clear
    assert ("feed", "down") in ev

def test_single_blip_no_warning():
    ev = run_worker([QUIET, requests.exceptions.ReadTimeout(), QUIET], [])
    assert not any(e[0] == "feed" for e in ev)

def test_failover_to_backup_and_back():
    bk = FakeResp(200, json.dumps([{"notificationId": "n1", "time": 5, "threat": 0,
                                     "isDrill": False, "cities": ["תל אביב"]}]))
    ev = run_worker([BLOCK, BLOCK, BLOCK, BLOCK, QUIET], [bk, bk])
    assert ("feed", "backup") in ev and ("alert", "backup-n1") in ev
    assert ev[-1] == ("feed", "ok") or ("feed", "ok") in ev

def test_early_warning_not_alarm():
    ew = FakeResp(200, json.dumps({"id": "N1", "cat": "10",
        "title": "בדקות הקרובות צפויות להתקבל התרעות באזורך", "data": ["תל אביב"]}))
    ev = run_worker([ew, ew, QUIET], [], locs=["תל אביב"])
    assert ev.count(("notice", "early_warning")) == 1
    assert not any(e[0] == "alert" for e in ev)

def test_event_ended_not_alarm_and_filtered_by_city():
    ee = FakeResp(200, json.dumps({"id": "N2", "cat": "10", "title": "האירוע הסתיים", "data": ["חיפה"]}))
    ev = run_worker([ee], [], locs=["תל אביב"])
    assert ev == []
