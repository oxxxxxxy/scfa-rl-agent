#!/usr/bin/env python3
"""
Launcher and Real-Time Monitor for Supreme Commander Observer Mission.
- Launches game with windowed spectator view (/nofog)
- PyAgent Autonomous Controller executes build order:
    1. ACU builds T1 Land Factory
    2. ACU builds 2 Mass Extractors
    3. ACU builds 4 Power Generators
    4. ACU builds 2 Mass Extractors
    5. ACU builds 4 Power Generators
    6. Land Factory builds 5 Engineers
    7. Eng 1: Builds Anti-Air (AA)
    8. Eng 2: Builds Point Defense (PD)
    9. Eng 3: Builds Walls around PD
    10. Eng 4: Builds Walls around AA
    11. Eng 5: Reclaims trees & rocks around base
- Monitors game.log in real time and prints status updates
"""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def main():
    root_dir = Path("/run/media/pyot/newdisk/scfa-rl-agent")
    game_cwd = Path("/run/media/pyot/newdisk/.faforever/bin")
    game_binary = str(game_cwd / "ForgedAlliance.exe")
    launchwrapper = "/run/media/pyot/newdisk/faf-linux/launchwrapper"
    log_file = root_dir / "game.log"

    print("=" * 70)
    print("Supreme Commander: Forged Alliance — Observer Mission Runner")
    print("=" * 70)
    print("Map: SCMP_009 (Finn's Revenge) | Faction: Cybran | Vision: /nofog")
    print("Objective:")
    print("  • ACU: Factory -> 2 Mex -> 4 PGens -> 2 Mex -> 4 PGens")
    print("  • Factory: 5 Engineers")
    print("  • Eng 1: Anti-Air (AA)")
    print("  • Eng 2: Point Defense (PD)")
    print("  • Eng 3: Walls surrounding Point Defense")
    print("  • Eng 4: Walls surrounding Anti-Air")
    print("  • Eng 5: Reclaim trees and rocks around the base")
    print("=" * 70)

    # Clean old log
    if log_file.exists():
        try:
            log_file.unlink()
        except OSError:
            pass

    cmd = [
        launchwrapper,
        game_binary,
        "/init", "init.lua",
        "/nobugreport",
        "/log", f"z:{log_file}",
        "/map", "SCMP_009",
        "/nofog",
        "/faction", "3"
    ]

    print(f"\n🚀 Launching game...")
    print(f"Command: {' '.join(cmd)}")

    env = os.environ.copy()
    game_proc = subprocess.Popen(
        cmd,
        cwd=str(game_cwd),
        env=env,
        stdin=subprocess.DEVNULL
    )

    print(f"\n⏳ Game process PID {game_proc.pid} started. Waiting for 3D simulation to start...")

    # Wait for game.log to appear and monitor lines
    start_time = time.time()
    last_pos = 0
    state_count = 0
    mission_events = []

    try:
        while True:
            # Check if game process is still alive
            if game_proc.poll() is not None:
                print(f"\nGame process exited with code {game_proc.returncode}")
                break

            if not log_file.exists():
                time.sleep(0.5)
                continue

            with open(log_file, "r", errors="ignore") as f:
                f.seek(last_pos)
                new_lines = f.readlines()
                last_pos = f.tell()

            for line in new_lines:
                line_str = line.strip()

                # Check for PyAgent Mission events
                if "PyAgent Mission:" in line_str or "PyAgent:" in line_str:
                    msg = line_str.split("info:")[-1].strip()
                    print(f"🎯 [{time.strftime('%H:%M:%S')}] {msg}")
                    mission_events.append(msg)

                # Check for state snapshots
                elif "##PYAGENT_STATE##" in line_str:
                    state_count += 1
                    json_str = line_str.split("##PYAGENT_STATE##")[-1]
                    try:
                        st = json.loads(json_str)
                        if state_count % 5 == 1:
                            m_stored = st.get("economy", {}).get("mass", {}).get("stored", 0)
                            m_inc = st.get("economy", {}).get("mass", {}).get("income", 0)
                            e_stored = st.get("economy", {}).get("energy", {}).get("stored", 0)
                            e_inc = st.get("economy", {}).get("energy", {}).get("income", 0)
                            gtime = st.get("game_time", 0)
                            units = st.get("units", [])
                            unit_count = len(units)

                            print(
                                f"📊 [T+{gtime:4.0f}s] Units: {unit_count:2d} | "
                                f"Mass: {m_stored:5.0f} (+{m_inc:3.1f}/s) | "
                                f"Energy: {e_stored:5.0f} (+{e_inc:4.1f}/s)"
                            )
                    except Exception:
                        pass

            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\nStopping monitor by user...")
    finally:
        print("\nMatch run completed.")


if __name__ == "__main__":
    main()
