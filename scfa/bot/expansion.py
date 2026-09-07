"""
Expansion & Engineer Dispatcher for Supreme Commander: Forged Alliance.

Manages autonomous engineer tasks:
1. Dispatching to unoccupied Mass Spots (nearest first).
2. Constructing perimeter Point Defenses and Radars.
3. Assisting primary factories to accelerate unit throughput.
"""

import math
from typing import Dict, List, Optional, Set, Tuple
from ..state import GameState, Unit, MassSpot
from ..client import SCFAClient
from .config import BotConfig


class ExpansionManager:
    """
    Coordinates field engineers and territorial expansion.
    """

    def __init__(self, config: Optional[BotConfig] = None):
        self.config = config or BotConfig()
        self._assigned_engineers: Dict[int, int] = {}  # engineer_id -> last_task_tick
        self._claimed_spots: Set[Tuple[float, float]] = set()
        self._last_defense_tick: int = 0

    def reset(self) -> None:
        self._assigned_engineers.clear()
        self._claimed_spots.clear()
        self._last_defense_tick = 0

    def dispatch(
        self,
        state: GameState,
        client: SCFAClient,
        available_engineers: List[Unit],
        base_pos: Tuple[float, float, float],
        enemy_pos: Optional[Tuple[float, float, float]] = None
    ) -> None:
        """
        Dispatches available engineers to expansion, fortification, or factory assistance.
        """
        if not available_engineers:
            return

        # Clean up dead or outdated assignments
        current_ids = {e.id for e in available_engineers}
        self._assigned_engineers = {
            eid: tick for eid, tick in self._assigned_engineers.items()
            if eid in current_ids and state.tick - tick < 25  # Re-evaluate every 25 sim ticks (2.5s)
        }

        # Identify free mass spots
        free_spots = [
            s for s in state.mass_spots
            if s.is_free and (s.x, s.z) not in self._claimed_spots
        ]

        factories = state.get_factories()
        defenses = state.get_defenses()
        radars = state.get_radars()

        for eng in available_engineers:
            if eng.id in self._assigned_engineers:
                continue

            # 1. PRIORITY 1: Expand to Unclaimed Mass Spots
            if free_spots and state.economy.mass.stored >= self.config.min_mass_for_mex:
                # Find closest spot to this specific engineer
                closest_spot = min(
                    free_spots,
                    key=lambda s: math.hypot(s.x - eng.position[0], s.z - eng.position[2])
                )
                dist = math.hypot(closest_spot.x - base_pos[0], closest_spot.z - base_pos[2])
                if dist <= self.config.max_safe_expansion_dist:
                    client.build(eng, "mex_t1", closest_spot.position)
                    self._claimed_spots.add((closest_spot.x, closest_spot.z))
                    free_spots.remove(closest_spot)
                    self._assigned_engineers[eng.id] = state.tick
                    continue

            # 2. PRIORITY 2: Perimeter Point Defense
            if (
                len(defenses) < self.config.base_defense_count
                and state.economy.mass.stored >= 150.0
                and (state.tick - self._last_defense_tick > 20)
            ):
                target_dir_x = (enemy_pos[0] - base_pos[0]) if enemy_pos else 15.0
                target_dir_z = (enemy_pos[2] - base_pos[2]) if enemy_pos else 15.0
                mag = max(math.hypot(target_dir_x, target_dir_z), 1.0)
                pd_x = base_pos[0] + (target_dir_x / mag) * (18.0 + len(defenses) * 6.0)
                pd_z = base_pos[2] + (target_dir_z / mag) * (18.0 + len(defenses) * 6.0)

                client.build(eng, "point_defense_t1", (pd_x, 0.0, pd_z))
                self._assigned_engineers[eng.id] = state.tick
                self._last_defense_tick = state.tick
                continue

            # 3. PRIORITY 3: Radar Vision Coverage
            if len(radars) == 0 and state.economy.mass.stored >= 60.0:
                radar_pos = (base_pos[0] + 6.0, 0.0, base_pos[2] + 6.0)
                client.build(eng, "radar_t1", radar_pos)
                self._assigned_engineers[eng.id] = state.tick
                continue

            # 4. PRIORITY 4: Assist Primary Factory
            if factories:
                primary_fac = factories[0]
                client.guard(eng, primary_fac)
                self._assigned_engineers[eng.id] = state.tick
