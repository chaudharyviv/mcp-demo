import pytest
from replay.manager import ReplayManager

def test_replay_files_exist_and_valid():
    """Verifies all 5 chip replay files exist and load valid data."""
    for chip_id in ["1", "2", "3a", "3b", "3c"]:
        replay = ReplayManager.get_replay_by_chip_id(chip_id)
        assert replay is not None, f"Replay chip {chip_id} missing"
        assert "content" in replay
        assert "trace" in replay
        assert len(replay["content"]) > 0

def test_replay_by_prompt_mapping():
    """Verifies matching prompts return correct replay recordings."""
    r1 = ReplayManager.get_replay_by_prompt("How do I restrict public network access to an Azure Storage account?")
    assert r1 is not None and r1["chip_id"] == "1"

    r2 = ReplayManager.get_replay_by_prompt("Summarise the open issues in our demo repo")
    assert r2 is not None and r2["chip_id"] == "2"

    r3a = ReplayManager.get_replay_by_prompt("How healthy is our storage estate?")
    assert r3a is not None and r3a["chip_id"] == "3a"

    r3b = ReplayManager.get_replay_by_prompt("Grow the payments database volume by 200 GB.")
    assert r3b is not None and r3b["chip_id"] == "3b"

    r3c = ReplayManager.get_replay_by_prompt("Change number is CHG0012345.")
    assert r3c is not None and r3c["chip_id"] == "3c"

def test_all_chips_acceptance_criteria():
    """Verifies acceptance criteria for each chip per docs/spec.md §5."""
    r1 = ReplayManager.get_replay_by_chip_id("1")
    assert "learn.microsoft.com" in r1["content"]

    r2 = ReplayManager.get_replay_by_chip_id("2")
    assert "payments_db" in r2["content"] or "urgent" in r2["content"].lower()

    r3a = ReplayManager.get_replay_by_chip_id("3a")
    assert "aggr_a01" in r3a["content"]
    assert "91" in r3a["content"]
    assert "vol_legacy_ftp" in r3a["content"]
    assert "offline" in r3a["content"]
    assert "vol_reports" in r3a["content"]

    r3b = ReplayManager.get_replay_by_chip_id("3b")
    assert "Change Request" in r3b["content"] or "CHG" in r3b["content"]

    r3c = ReplayManager.get_replay_by_chip_id("3c")
    assert "executed: false" in r3c["content"].lower() or "no storage changes" in r3c["content"].lower()
    assert "aggr_a02" in r3c["content"]
