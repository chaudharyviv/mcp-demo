"""
Replay Manager for loading recorded chip responses and traces.
"""
import json
from pathlib import Path
from typing import Dict, Any, Optional

REPLAY_DIR = Path(__file__).parent

CHIP_MAP = {
    "1": "1_docs.json",
    "2": "2_github.json",
    "3a": "3a_health.json",
    "3b": "3b_resize.json",
    "3c": "3c_approve.json"
}

class ReplayManager:
    @staticmethod
    def get_replay_by_chip_id(chip_id: str) -> Optional[Dict[str, Any]]:
        filename = CHIP_MAP.get(chip_id)
        if not filename:
            return None

        file_path = REPLAY_DIR / filename
        if not file_path.exists():
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def get_replay_by_prompt(prompt: str) -> Optional[Dict[str, Any]]:
        prompt_lower = prompt.lower()
        if "azure storage" in prompt_lower or "public network access" in prompt_lower:
            return ReplayManager.get_replay_by_chip_id("1")
        elif "open issues" in prompt_lower or "demo repo" in prompt_lower:
            return ReplayManager.get_replay_by_chip_id("2")
        elif "healthy" in prompt_lower or "storage estate" in prompt_lower:
            return ReplayManager.get_replay_by_chip_id("3a")
        elif "grow the payments database" in prompt_lower or "200 gb" in prompt_lower:
            return ReplayManager.get_replay_by_chip_id("3b")
        elif "chg0012345" in prompt_lower or "change number" in prompt_lower:
            return ReplayManager.get_replay_by_chip_id("3c")
        return None
