"""
High-performance IPC bridge between Python and Supreme Commander: Forged Alliance Lua via /dev/shm.
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


class SCFAIPCBridge:
    def __init__(self, shm_dir: str = "/dev/shm"):
        self.shm_dir = Path(shm_dir)
        self.obs_file = self.shm_dir / "scfa_obs.json"
        self.obs_ready = self.shm_dir / "scfa_obs.ready"
        self.act_file = self.shm_dir / "scfa_action.json"
        self.act_ready = self.shm_dir / "scfa_action.ready"
        self.stop_flag = self.shm_dir / "scfa_stop.flag"
        self.current_step = 0

    def clean(self) -> None:
        """Removes existing IPC communication flags and files."""
        for path in [self.obs_file, self.obs_ready, self.act_file, self.act_ready, self.stop_flag]:
            if path.exists():
                try:
                    path.unlink()
                except OSError:
                    pass

    def request_stop(self) -> None:
        """Signals the in-game Lua loop to terminate."""
        self.stop_flag.write_text("1")

    def wait_for_observation(self, timeout_sec: float = 10.0) -> Optional[Dict[str, Any]]:
        """
        Waits for the in-game Lua loop to signal a new observation.
        Returns parsed observation dictionary or None if timed out.
        """
        start_time = time.time()
        while time.time() - start_time < timeout_sec:
            if self.obs_ready.exists() and self.obs_file.exists():
                try:
                    content = self.obs_file.read_text()
                    obs = json.loads(content)
                    # Remove ready flag after reading
                    try:
                        self.obs_ready.unlink()
                    except OSError:
                        pass
                    self.current_step = obs.get("step", self.current_step)
                    return obs
                except (json.JSONDecodeError, OSError):
                    # Incomplete write, retry briefly
                    time.sleep(0.005)
            time.sleep(0.01)
        return None

    def send_action(self, action_id: int, target: Optional[Tuple[float, float, float]] = None) -> bool:
        """
        Atomically writes action to /dev/shm and signals the in-game Lua loop.
        """
        action_data = {
            "step": self.current_step,
            "action": int(action_id),
            "target": list(target) if target is not None else None
        }
        try:
            # Write action data
            temp_file = self.shm_dir / f"scfa_action_{os.getpid()}.tmp"
            temp_file.write_text(json.dumps(action_data))
            temp_file.replace(self.act_file)

            # Signal ready
            self.act_ready.write_text("1")
            return True
        except OSError:
            return False
