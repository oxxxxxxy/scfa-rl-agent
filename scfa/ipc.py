"""
Shared memory IPC bridge for transferring GameState and Command batches.
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class SCFAIPC:
    def __init__(self, shm_dir: str = "/dev/shm"):
        self.shm_dir = Path(shm_dir)
        self.state_file = self.shm_dir / "scfa_state.json"
        self.state_ready = self.shm_dir / "scfa_state.ready"
        self.cmd_file = self.shm_dir / "scfa_commands.json"
        self.cmd_ready = self.shm_dir / "scfa_commands.ready"
        self.stop_file = self.shm_dir / "scfa_stop.flag"
        self.config_file = self.shm_dir / "scfa_config.json"

    def write_config(self, army: int = 1, speed: int = 10, disable_ai: bool = True) -> bool:
        """Writes initial session configuration for the in-game bridge."""
        try:
            cfg = {"army": int(army), "speed": int(speed), "disable_ai": bool(disable_ai)}
            self.config_file.write_text(json.dumps(cfg))
            return True
        except OSError:
            return False

    def clean(self) -> None:
        """Removes all IPC communication files."""
        for path in [self.state_file, self.state_ready, self.cmd_file, self.cmd_ready, self.stop_file, self.config_file]:
            if path.exists():
                try:
                    path.unlink()
                except OSError:
                    pass

    def request_stop(self) -> None:
        """Signals the game loop to finish."""
        try:
            self.stop_file.write_text("1")
        except OSError:
            pass

    def wait_for_state(self, timeout_sec: Optional[float] = 10.0) -> Optional[Dict[str, Any]]:
        """Waits for in-game Lua loop to signal that a state snapshot is ready."""
        start = time.time()
        while timeout_sec is None or (time.time() - start < timeout_sec):
            if self.state_ready.exists() and self.state_file.exists():
                try:
                    content = self.state_file.read_text()
                    data = json.loads(content)
                    try:
                        self.state_ready.unlink()
                    except OSError:
                        pass
                    return data
                except (json.JSONDecodeError, OSError):
                    time.sleep(0.005)
            time.sleep(0.01)
        return None

    def send_commands(self, commands: List[Dict[str, Any]]) -> bool:
        """Atomically writes command batch and raises ready signal."""
        try:
            tmp = self.shm_dir / f"scfa_cmd_{os.getpid()}.tmp"
            tmp.write_text(json.dumps(commands))
            tmp.replace(self.cmd_file)
            self.cmd_ready.write_text("1")
            return True
        except OSError:
            return False
