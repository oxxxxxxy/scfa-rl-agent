"""
Game process launcher and lifecycle manager for Supreme Commander: Forged Alliance on Linux.
"""

import logging
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Optional

from .blueprints import Faction

logger = logging.getLogger(__name__)


class GameLauncher:
    DEFAULT_LAUNCHWRAPPER = "/run/media/pyot/newdisk/faf-linux/launchwrapper"
    DEFAULT_BINARY = "/run/media/pyot/newdisk/.faforever/bin/ForgedAlliance.exe"
    DEFAULT_INIT = "/run/media/pyot/newdisk/.faforever/bin/init_faf.lua"

    def __init__(
        self,
        launchwrapper_path: Optional[str] = None,
        game_binary: Optional[str] = None,
        init_file: Optional[str] = None
    ):
        self.launchwrapper_path = Path(launchwrapper_path or self.DEFAULT_LAUNCHWRAPPER)
        self.game_binary = Path(game_binary or self.DEFAULT_BINARY)
        self.init_file = Path(init_file or self.DEFAULT_INIT)
        self.process: Optional[subprocess.Popen] = None

    def launch(
        self,
        map_name: str = "SCMP_009",
        faction: Faction = Faction.CYBRAN,
        enemy_ai: str = "medium",
        game_speed: int = 10,
        headless: bool = True
    ) -> subprocess.Popen:
        """Starts a game session with the PyAgent mod enabled."""
        if self.is_alive():
            self.terminate()

        cmd = [
            str(self.launchwrapper_path),
            str(self.game_binary),
            "/nobugreport",
            "/nosound",
            "/exitongameover",
            "/init", str(self.init_file),
            "/map", map_name,
            "/ai", enemy_ai,
            "/faction", str(int(faction))
        ]

        env = os.environ.copy()
        if headless:
            env["WINEDEBUG"] = "-all"

        logger.info(f"Launching SCFA instance: {' '.join(cmd)}")
        self.process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid
        )
        return self.process

    def is_alive(self) -> bool:
        if self.process is None:
            return False
        return self.process.poll() is None

    def terminate(self, timeout_sec: float = 3.0) -> None:
        if not self.is_alive():
            self.process = None
            return

        try:
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            start_wait = time.time()
            while self.is_alive() and time.time() - start_wait < timeout_sec:
                time.sleep(0.1)

            if self.is_alive():
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                self.process.wait()
        except (ProcessLookupError, OSError):
            pass
        finally:
            self.process = None
