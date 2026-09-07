"""
Subprocess manager for Supreme Commander: Forged Alliance on Linux.
"""

import logging
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class SCFAGameProcess:
    def __init__(
        self,
        launchwrapper_path: str = "/run/media/pyot/newdisk/faf-linux/launchwrapper",
        game_binary: str = "/run/media/pyot/newdisk/.faforever/bin/ForgedAlliance.exe",
        init_file: str = "/run/media/pyot/newdisk/.faforever/bin/init_faf.lua",
        map_name: str = "SCMP_009",
        ai_type: str = "medium",
        faction: int = 3,  # 1: UEF, 2: Aeon, 3: Cybran, 4: Seraphim
        headless: bool = True
    ):
        self.launchwrapper_path = Path(launchwrapper_path)
        self.game_binary = Path(game_binary)
        self.init_file = Path(init_file)
        self.map_name = map_name
        self.ai_type = ai_type
        self.faction = faction
        self.headless = headless
        self.process: Optional[subprocess.Popen] = None

    def start(self) -> subprocess.Popen:
        """Launches the accelerated Forged Alliance match in the background."""
        if self.is_alive():
            self.terminate()

        cmd = [
            str(self.launchwrapper_path),
            str(self.game_binary),
            "/nobugreport",
            "/nosound",
            "/exitongameover",
            "/init", str(self.init_file),
            "/map", self.map_name,
            "/ai", self.ai_type,
            "/faction", str(self.faction)
        ]

        env = os.environ.copy()
        # Set Wine Virtual Desktop so game window stays bounded and does not grab desktop
        if self.headless:
            env["WINEDEBUG"] = "-all"

        logger.info(f"Starting SCFA game process: {' '.join(cmd)}")
        self.process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid
        )
        return self.process

    def is_alive(self) -> bool:
        """Returns True if the game process is still active."""
        if self.process is None:
            return False
        return self.process.poll() is None

    def terminate(self, timeout_sec: float = 3.0) -> None:
        """Safely stops the game process group."""
        if not self.is_alive():
            self.process = None
            return

        try:
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            start_wait = time.time()
            while self.is_alive() and time.time() - start_wait < timeout_sec:
                time.sleep(0.1)

            if self.is_alive():
                logger.warning("SCFA process did not terminate gracefully, sending SIGKILL...")
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                self.process.wait()
        except (ProcessLookupError, OSError):
            pass
        finally:
            self.process = None
