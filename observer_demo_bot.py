#!/usr/bin/env python3
"""
Observer Demo Bot for Supreme Commander: Forged Alliance.

Exact mission specification:
1. ACU builds Mass Extractor & Power Generator (to fund the base).
2. ACU builds 1 Land Factory.
3. ACU builds 3 Point Defense Turrets and 1 Anti-Air Turret.
4. Land Factory produces exactly 5 Engineers.
5. As the 5 engineers emerge from the factory, they fan out across the map
   to construct Mass Extractors on free mass spots and extract mass.
6. Runs at normal 1.0x real-time speed so the human observer can comfortably watch.
"""

import argparse
import math
import sys
import time
from typing import Dict, List, Optional, Set, Tuple

from scfa import Faction, GameState, SCFAClient, SCFAIPC, Unit


class ObserverMissionBot:
    def __init__(self, client: SCFAClient):
        self.client = client
        self.base_pos: Optional[Tuple[float, float, float]] = None
        self.spawn_pos: Optional[Tuple[float, float, float]] = None

        # Mission state trackers
        self.has_mex1 = False
        self.has_pgen1 = False
        self.has_factory = False
        self.factory_ordered = False
        self.factory_unit_id: Optional[int] = None
        self.engineers_queued = False

        self.turrets_built = 0
        self.aa_built = 0
        self.last_turret_tick = 0

        # Engineer tracking
        self.assigned_engineers: Dict[int, Tuple[float, float]] = {}  # eng_id -> (spot_x, spot_z)
        self.claimed_spots: Set[Tuple[float, float]] = set()

    def step(self, state: GameState) -> None:
        acu = state.get_commander()
        if not acu or not acu.is_alive:
            return

        if self.spawn_pos is None:
            self.spawn_pos = acu.position
            self.base_pos = acu.position
            print(f"🎯 ACU Spawn Position: ({acu.position[0]:.1f}, {acu.position[2]:.1f})")

        factories = state.get_factories("LAND")
        engineers = state.get_engineers()
        defenses = state.get_defenses()
        mexes = state.get_mexes()
        pgens = state.get_power_generators()

        # ---------------------------------------------------------------------
        # 1. FOUNDATION: Build 1 Mex and 1 PGen so construction doesn't stall
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
        # 2. FACTORY: Build 1 Land Factory
        # ---------------------------------------------------------------------
        if not self.has_factory:
            if len(factories) >= 1:
                fac = factories[0]
                self.factory_unit_id = fac.id
                if fac.is_complete:
                    self.has_factory = True
                    print(f"🏭 [Base] Land Factory #{fac.id} construction COMPLETE!")
            elif not self.factory_ordered:
                f_pos = (self.spawn_pos[0] - 9.0, 0.0, self.spawn_pos[2] - 7.0)
                if state.economy.mass.stored >= 110:
                    print(f"🏭 [ACU] Ordering Land Factory construction at ({f_pos[0]:.1f}, {f_pos[2]:.1f})")
                    self.client.build(acu, "factory_land_t1", f_pos)
                    self.factory_ordered = True
            return

        # ---------------------------------------------------------------------
        # 3. FACTORY QUEUE: Order exactly 5 Engineers from the factory
        # ---------------------------------------------------------------------
        if self.has_factory and not self.engineers_queued:
            fac = factories[0]
            if fac.is_complete:
                print(f"⚙️  [Factory] Queueing production of exactly 5 Field Engineers...")
                self.client.produce(fac, "engineer_t1", count=5)
                self.engineers_queued = True

        # ---------------------------------------------------------------------
        # 4. ACU DEFENSES: Build 3 Point Defense Turrets and 1 Anti-Air Turret
        # ---------------------------------------------------------------------
        completed_pds = [d for d in defenses if "DIRECTFIRE" in d.tags and d.is_complete]
        completed_aas = [d for d in defenses if "ANTIAIR" in d.tags and d.is_complete]

        # Check existing orders / rate-limit turret building
        if state.tick - self.last_turret_tick >= 15:
            # 3 Point Defenses
            if len(completed_pds) < 3 and state.economy.mass.stored >= 180:
                turret_offsets = [
                    (14.0, 8.0),   # Turret 1 (North-East perimeter)
                    (8.0, 14.0),   # Turret 2 (East-North perimeter)
                    (16.0, 16.0),  # Turret 3 (Frontline outpost)
                ]
                idx = len(completed_pds)
                dx, dz = turret_offsets[idx]
                pd_pos = (self.spawn_pos[0] + dx, 0.0, self.spawn_pos[2] + dz)
                print(f"🛡️  [ACU] Building Point Defense #{idx + 1}/3 at ({pd_pos[0]:.1f}, {pd_pos[2]:.1f})")
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
        # 5. EXPANSION: As engineers emerge from factory, dispatch to Mass Spots
        # ---------------------------------------------------------------------
        if engineers:
            free_spots = [
                s for s in state.mass_spots
                if s.is_free and (s.x, s.z) not in self.claimed_spots
            ]

            for eng in engineers:
                # If engineer has an active assignment, check if done
                if eng.id in self.assigned_engineers:
                    target_x, target_z = self.assigned_engineers[eng.id]
                    # Check if spot is now occupied by an ally mex
                    spot_claimed = any(
                        m.is_complete and math.hypot(m.position[0] - target_x, m.position[2] - target_z) < 5.0
                        for m in mexes
                    )
                    if not spot_claimed:
                        # Engineer is still traveling or building
                        continue
                    else:
                        # Completed! Free up engineer for next task
                        print(f"✅ [Engineer #{eng.id}] Successfully built Mass Extractor at ({target_x:.1f}, {target_z:.1f})!")
                        del self.assigned_engineers[eng.id]

                # Assign free engineer to nearest unclaimed mass spot
                if free_spots and state.economy.mass.stored >= 36:
                    closest_spot = min(
                        free_spots,
                        key=lambda s: math.hypot(s.x - eng.position[0], s.z - eng.position[2])
                    )
                    print(f"🚜 [Engineer #{eng.id}] Emerging from base -> Dispatched to Mass Spot ({closest_spot.x:.1f}, {closest_spot.z:.1f})")
                    self.client.build(eng, "mex_t1", closest_spot.position)
                    self.claimed_spots.add((closest_spot.x, closest_spot.z))
                    self.assigned_engineers[eng.id] = (closest_spot.x, closest_spot.z)
                    free_spots.remove(closest_spot)


def main():
    parser = argparse.ArgumentParser(description="Observer Demo Bot for Supreme Commander")
    parser.add_argument("--army", type=int, default=1, help="Army index to control (default: 1)")
    parser.add_argument("--faction", default="cybran", choices=["cybran", "uef", "aeon", "seraphim"])
    parser.add_argument("--speed", type=int, default=0, help="Game speed: 0 for normal 1.0x real-time (default: 0)")
    args = parser.parse_args()

    faction_map = {
        "cybran": Faction.CYBRAN,
        "uef": Faction.UEF,
        "aeon": Faction.AEON,
        "seraphim": Faction.SERAPHIM
    }
    faction = faction_map[args.faction]

    print("=" * 65)
    print("Supreme Commander: Forged Alliance — Observer Mission Runner")
    print(f"Controlled Army: {args.army} | Faction: {faction.name} | Speed: {args.speed} (Real-time)")
    print("=" * 65)

    ipc = SCFAIPC()
    ipc.write_config(army=args.army, speed=args.speed, disable_ai=True)

    client = SCFAClient(ipc=ipc, faction=faction)
    client.set_army(args.army)
    client.set_speed(args.speed)

    print("\n⏳ Waiting for the match to launch (in game window)...")
    print("Instructions for the user:")
    print(" 1. In the Supreme Commander window, go to Skirmish (or LAN).")
    print(f" 2. Set Slot {args.army} as an AI or open slot (PyAgent will take control).")
    print(" 3. Set your own player slot to 'Observer' (Наблюдатель) or team Observer.")
    print(" 4. Click Launch / Старт!")
    print(" 5. Watch the bot execute the exact construction sequence!")

    while True:
        try:
            state = client.get_state(timeout_sec=5.0)
            acu = state.get_commander()
            hp = f"{acu.health:.0f}/{acu.max_health:.0f}" if acu else "N/A"
            print(f"\n🎮 Match detected! Session started. ACU HP: {hp}")
            break
        except TimeoutError:
            print("  ⏳ Still waiting for match start in lobby / map loading...")
        except KeyboardInterrupt:
            print("\nAborted by user.")
            sys.exit(0)

    bot = ObserverMissionBot(client)
    step_num = 0

    print("\n🚀 Beginning autonomous construction mission...\n")
    try:
        while True:
            step_num += 1
            state = client.get_state()
            if state.is_over:
                print("🏁 Match has ended.")
                break

            # Run decision logic
            bot.step(state)

            # Periodic status telemetry
            if step_num % 5 == 1:
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
                    f"[{step_num:4d}] Time: {state.time:4.1f}s | "
                    f"Mass: {m_stored:4.0f} ({m_net:+3.1f}/s) | "
                    f"Energy: {e_stored:5.0f} ({e_net:+4.1f}/s) | "
                    f"Factory: {facs}/1 | "
                    f"Engs: {engs}/5 | "
                    f"PDs: {pds}/3 | "
                    f"AA: {aas}/1 | "
                    f"Mexes: {mexs}"
                )

            # Flush orders to simulation
            client.step()

    except KeyboardInterrupt:
        print("\nSession paused by user.")


if __name__ == "__main__":
    main()
