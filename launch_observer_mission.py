#!/usr/bin/env python3
"""
One-click Automated Launcher for Observer Mission in Supreme Commander: Forged Alliance.

Launches the game directly into a match on SCMP_009 (Finn's Revenge) with:
- Windowed visible display on the user's screen.
- /nofog flag for full observer / spectator map vision.
- Real-time simulation speed (1.0x).
- Autonomous mission execution:
  1. ACU builds foundation (Mex + PGen).
  2. ACU builds Land Factory.
  3. ACU builds 3 Point Defense turrets + 1 Anti-Air turret.
  4. Land Factory produces 5 Engineers.
  5. As the 5 engineers emerge from the factory, they fan out across the map
     to construct Mass Extractors on free mass spots and extract mass.
"""

import math
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from scfa import Faction, GameState, SCFAClient, SCFAIPC, Unit


class ObserverMissionBot:
    def __init__(self, client: SCFAClient):
        self.client = client
        self.spawn_pos: Optional[Tuple[float, float, float]] = None

        # Mission state flags
        self.has_mex1 = False
        self.has_pgen1 = False
        self.has_factory = False
        self.factory_ordered = False
        self.engineers_queued = False

        self.last_action_tick = 0
        self.last_turret_tick = 0

        # Engineer tracking
        self.assigned_engineers: Dict[int, Tuple[float, float]] = {}
        self.claimed_spots: Set[Tuple[float, float]] = set()

    def step(self, state: GameState) -> None:
        acu = state.get_commander()
        if not acu or not acu.is_alive:
            return

        if self.spawn_pos is None:
            self.spawn_pos = acu.position
            print(f"\n[MISSION START] ACU spawn coordinates: ({acu.position[0]:.1f}, {acu.position[2]:.1f})")

        factories = state.get_factories("LAND")
        engineers = state.get_engineers()
        defenses = state.get_defenses()
        mexes = state.get_mexes()
        pgens = state.get_power_generators()

        # ---------------------------------------------------------------------
        # 1. BASELINE ECONOMY: Build 1 Mex and 1 PGen so we don't stall
        # ---------------------------------------------------------------------
        if not self.has_mex1:
            if len(mexes) >= 1:
                self.has_mex1 = True
            else:
                spot = state.get_nearest_free_mex(self.spawn_pos)
                if spot and state.economy.mass.stored >= 36:
                    print(f"🏗️  [ACU] Building Initial Mass Extractor at ({spot.x:.1f}, {spot.z:.1f})")
                    self.client.build(acu, "mex_t1", spot.position)
                    self.claimed_spots.add((spot.x, spot.z))
                return

        if not self.has_pgen1:
            if len(pgens) >= 1:
                self.has_pgen1 = True
            else:
                p_pos = (self.spawn_pos[0] + 5.0, 0.0, self.spawn_pos[2] + 4.0)
                if state.economy.mass.stored >= 60:
                    print(f"⚡ [ACU] Building Initial Power Generator at ({p_pos[0]:.1f}, {p_pos[2]:.1f})")
                    self.client.build(acu, "power_t1", p_pos)
                return

        # ---------------------------------------------------------------------
        # 2. LAND FACTORY: Build Land Factory
        # ---------------------------------------------------------------------
        if not self.has_factory:
            if len(factories) >= 1 and factories[0].is_complete:
                self.has_factory = True
                print(f"🏭 [Base] Land Factory construction COMPLETE!")
            elif not self.factory_ordered:
                f_pos = (self.spawn_pos[0] - 9.0, 0.0, self.spawn_pos[2] - 7.0)
                if state.economy.mass.stored >= 110:
                    print(f"🏭 [ACU] Ordering Land Factory construction at ({f_pos[0]:.1f}, {f_pos[2]:.1f})")
                    self.client.build(acu, "factory_land_t1", f_pos)
                    self.factory_ordered = True
            return

        # ---------------------------------------------------------------------
        # 3. FACTORY PRODUCTION: Queue exactly 5 Engineers
        # ---------------------------------------------------------------------
        if self.has_factory and not self.engineers_queued:
            fac = factories[0]
            if fac.is_complete:
                print(f"⚙️  [Factory] Queueing production of exactly 5 Field Engineers...")
                self.client.produce(fac, "engineer_t1", count=5)
                self.engineers_queued = True

        # ---------------------------------------------------------------------
        # 4. DEFENSES: Build 3 Point Defense turrets and 1 Anti-Air turret
        # ---------------------------------------------------------------------
        completed_pds = [d for d in defenses if "DIRECTFIRE" in d.tags and d.is_complete]
        completed_aas = [d for d in defenses if "ANTIAIR" in d.tags and d.is_complete]

        if state.tick - self.last_turret_tick >= 15:
            # 3 Point Defenses
            if len(completed_pds) < 3 and state.economy.mass.stored >= 180:
                turret_offsets = [
                    (14.0, 8.0),   # Turret 1 (North-East)
                    (8.0, 14.0),   # Turret 2 (East-North)
                    (16.0, 16.0),  # Turret 3 (Forward outpost)
                ]
                idx = len(completed_pds)
                dx, dz = turret_offsets[idx]
                pd_pos = (self.spawn_pos[0] + dx, 0.0, self.spawn_pos[2] + dz)
                print(f"🛡️  [ACU] Building Point Defense Turret #{idx + 1}/3 at ({pd_pos[0]:.1f}, {pd_pos[2]:.1f})")
                self.client.build(acu, "point_defense_t1", pd_pos)
                self.last_turret_tick = state.tick
                return

            # 1 Anti-Air Defense
            elif len(completed_pds) >= 3 and len(completed_aas) < 1 and state.economy.mass.stored >= 150:
                aa_pos = (self.spawn_pos[0] - 6.0, 0.0, self.spawn_pos[2] + 12.0)
                print(f"🚀 [ACU] Building Anti-Air Turret at ({aa_pos[0]:.1f}, {aa_pos[2]:.1f})")
                self.client.build(acu, "anti_air_t1", aa_pos)
                self.last_turret_tick = state.tick
                return

        # ---------------------------------------------------------------------
        # 5. EXPANSION: As 5 engineers emerge, dispatch to free Mass Spots
        # ---------------------------------------------------------------------
        if engineers:
            free_spots = [
                s for s in state.mass_spots
                if s.is_free and (s.x, s.z) not in self.claimed_spots
            ]

            for eng in engineers:
                # Check if this engineer has an ongoing task
                if eng.id in self.assigned_engineers:
                    target_x, target_z = self.assigned_engineers[eng.id]
                    # Has an extractor been built at the target location?
                    spot_claimed = any(
                        m.is_complete and math.hypot(m.position[0] - target_x, m.position[2] - target_z) < 5.0
                        for m in mexes
                    )
                    if not spot_claimed:
                        continue
                    else:
                        print(f"✅ [Engineer #{eng.id}] Built Mass Extractor at ({target_x:.1f}, {target_z:.1f})! Seeking next spot...")
                        del self.assigned_engineers[eng.id]

                # Assign free engineer to nearest free mass spot
                if free_spots and state.economy.mass.stored >= 36:
                    closest_spot = min(
                        free_spots,
                        key=lambda s: math.hypot(s.x - eng.position[0], s.z - eng.position[2])
                    )
                    print(f"🚜 [Engineer #{eng.id}] Emerging from Factory -> Dispatched to Mass Spot ({closest_spot.x:.1f}, {closest_spot.z:.1f})")
                    self.client.build(eng, "mex_t1", closest_spot.position)
                    self.claimed_spots.add((closest_spot.x, closest_spot.z))
                    self.assigned_engineers[eng.id] = (closest_spot.x, closest_spot.z)
                    free_spots.remove(closest_spot)


def main():
    map_name = "SCMP_009"
    faction = Faction.CYBRAN
    speed = 0  # 1.0x Real-time

    print("=" * 65)
    print("Supreme Commander: Forged Alliance — Automated Match Runner")
    print(f"Map: {map_name} | Faction: {faction.name} | View: Observer (/nofog)")
    print("=" * 65)

    ipc = SCFAIPC()
    ipc.clean()
    ipc.write_config(army=1, speed=speed, disable_ai=False)

    launchwrapper_path = "/run/media/pyot/newdisk/faf-linux/launchwrapper"
    game_binary = "/run/media/pyot/newdisk/.faforever/bin/ForgedAlliance.exe"
    init_file = "init.lua"
    game_cwd = "/run/media/pyot/newdisk/.faforever/bin"

    cmd = [
        launchwrapper_path,
        game_binary,
        "/init", init_file,
        "/nobugreport",
        "/map", map_name,
        "/nofog",
        "/faction", str(int(faction))
    ]

    print(f"\n🚀 Launching Supreme Commander windowed process...")
    print(f"Command: {' '.join(cmd)}")

    env = os.environ.copy()
    game_proc = subprocess.Popen(
        cmd,
        cwd=game_cwd,
        env=env,
        preexec_fn=os.setsid
    )

    client = SCFAClient(ipc=ipc, faction=faction)
    client.set_army(1)
    client.set_speed(speed)

    print("\n⏳ Waiting for 3D simulation to start and load map...")
    start_wait = time.time()
    state = None
    while time.time() - start_wait < 60.0:
        try:
            state = client.get_state(timeout_sec=5.0)
            if state is not None:
                acu = state.get_commander()
                hp = f"{acu.health:.0f}/{acu.max_health:.0f}" if acu else "N/A"
                print(f"🎮 Simulation live! Game Time: {state.time:.1f}s | ACU HP: {hp}")
                break
        except TimeoutError:
            print("  ⏳ Loading 3D terrain and assets...")

    if state is None:
        print("❌ Timed out waiting for simulation state.")
        try:
            os.killpg(os.getpgid(game_proc.pid), signal.SIGTERM)
        except OSError:
            pass
        sys.exit(1)

    bot = ObserverMissionBot(client)
    step_count = 0

    print("\n🎬 Mission underway! Watch the game window on your screen.\n")
    try:
        while True:
            step_count += 1
            state = client.get_state(timeout_sec=15.0)
            if state.is_over:
                print("\n🏁 Match finished.")
                break

            bot.step(state)

            if step_count % 5 == 1:
                acu = state.get_commander()
                hp_str = f"{acu.health:.0f}" if acu else "DEAD"
                m_stored = state.economy.mass.stored
                m_net = state.economy.mass.income - state.economy.mass.usage
                e_stored = state.economy.energy.stored
                e_net = state.economy.energy.income - state.economy.energy.usage
                facs = len(state.get_factories())
                engs = len(state.get_engineers())
                pds = len([d for d in state.get_defenses() if "DIRECTFIRE" in d.tags])
                aas = len([d for d in state.get_defenses() if "ANTIAIR" in d.tags])
                mexs = len(state.get_mexes())

                print(
                    f"[{step_count:4d}] Time: {state.time:4.1f}s | "
                    f"Mass: {m_stored:4.0f} ({m_net:+4.1f}/s) | "
                    f"Energy: {e_stored:5.0f} ({e_net:+5.1f}/s) | "
                    f"Factory: {facs}/1 | "
                    f"Engs: {engs}/5 | "
                    f"PDs: {pds}/3 | "
                    f"AA: {aas}/1 | "
                    f"Mexes: {mexs}"
                )

            client.step()

    except KeyboardInterrupt:
        print("\nMatch interrupted by user.")
    finally:
        print("\nCleaning up...")
        try:
            os.killpg(os.getpgid(game_proc.pid), signal.SIGTERM)
        except OSError:
            pass
        ipc.clean()


if __name__ == "__main__":
    main()
