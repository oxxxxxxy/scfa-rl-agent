"""
Opening Build Order Finite State Machine (FSM) for Supreme Commander: Forged Alliance.

Executes the proven competitive opening build order:
1. ACU builds Mex 1 (closest mass spot to spawn)
2. ACU builds Mex 2 (second closest mass spot)
3. ACU builds PGen 1 (adjacent to planned factory site)
4. ACU builds Land Factory 1
5. ACU builds PGen 2
6. ACU builds remaining nearby Mexes (Mex 3 & 4)
7. ACU builds Radar T1
8. Hand off to Mid-Game Dynamic Systems
"""

import math
from typing import List, Optional, Tuple
from ..state import GameState, Unit, MassSpot
from ..client import SCFAClient
from .config import BotConfig


class BuildOrderManager:
    """
    Finite State Machine managing early-game base establishment.
    """

    def __init__(self, config: Optional[BotConfig] = None):
        self.config = config or BotConfig()
        self.step_index: int = 0
        self.is_completed: bool = False
        self.spawn_pos: Optional[Tuple[float, float, float]] = None
        self._target_pos: Optional[Tuple[float, float, float]] = None
        self._last_order_tick: int = 0
        self._targeted_mex_spots: List[Tuple[float, float]] = []

    def reset(self) -> None:
        self.step_index = 0
        self.is_completed = False
        self.spawn_pos = None
        self._target_pos = None
        self._last_order_tick = 0
        self._targeted_mex_spots.clear()

    def update(self, state: GameState, client: SCFAClient) -> bool:
        """
        Advances the build order FSM if not yet completed.
        Returns True if the FSM handled orders for this tick, False if opening is finished.
        """
        if self.is_completed:
            return False

        acu = state.get_commander()
        if not acu or not acu.is_alive:
            self.is_completed = True
            return False

        if self.spawn_pos is None:
            self.spawn_pos = acu.position

        # Rate-limit orders to avoid command buffer flooding
        if state.tick - self._last_order_tick < 3:
            return True

        # Check existing structures to see if steps can be auto-advanced
        mexes = state.get_mexes()
        pgens = state.get_power_generators()
        factories = state.get_factories()
        radars = state.get_radars()

        # Step 0: Mex 1
        if self.step_index == 0:
            if len(mexes) >= 1:
                self.step_index = 1
            else:
                spot = self._get_closest_free_mex(self.spawn_pos, state)
                if spot and state.economy.mass.stored >= self.config.min_mass_for_mex:
                    client.build(acu, "mex_t1", spot.position)
                    self._targeted_mex_spots.append((spot.x, spot.z))
                    self._last_order_tick = state.tick
            return True

        # Step 1: Mex 2
        elif self.step_index == 1:
            if len(mexes) >= 2:
                self.step_index = 2
            else:
                spot = self._get_closest_free_mex(self.spawn_pos, state)
                if spot and state.economy.mass.stored >= self.config.min_mass_for_mex:
                    client.build(acu, "mex_t1", spot.position)
                    self._targeted_mex_spots.append((spot.x, spot.z))
                    self._last_order_tick = state.tick
            return True

        # Step 2: PGen 1
        elif self.step_index == 2:
            if len(pgens) >= 1:
                self.step_index = 3
            else:
                p_pos = (self.spawn_pos[0] + 5.0, 0.0, self.spawn_pos[2] + 4.0)
                if state.economy.mass.stored >= self.config.min_mass_for_pgen:
                    client.build(acu, "power_t1", p_pos)
                    self._last_order_tick = state.tick
            return True

        # Step 3: Land Factory 1
        elif self.step_index == 3:
            if len(factories) >= 1:
                self.step_index = 4
            else:
                f_pos = (self.spawn_pos[0] - 9.0, 0.0, self.spawn_pos[2] - 7.0)
                if state.economy.mass.stored >= self.config.min_mass_for_factory:
                    client.build(acu, "factory_land_t1", f_pos)
                    self._last_order_tick = state.tick
            return True

        # Step 4: PGen 2
        elif self.step_index == 4:
            if len(pgens) >= 2:
                self.step_index = 5
            else:
                p_pos = (self.spawn_pos[0] - 9.0, 0.0, self.spawn_pos[2] - 12.0)
                if state.economy.mass.stored >= self.config.min_mass_for_pgen:
                    client.build(acu, "power_t1", p_pos)
                    self._last_order_tick = state.tick
            return True

        # Step 5: Nearby Mex 3 & 4 (within 50m of base)
        elif self.step_index == 5:
            nearby_spots = [
                s for s in state.mass_spots
                if s.is_free
                and math.hypot(s.x - self.spawn_pos[0], s.z - self.spawn_pos[2]) <= 50.0
                and (s.x, s.z) not in self._targeted_mex_spots
            ]
            if len(nearby_spots) > 0:
                spot = nearby_spots[0]
                if state.economy.mass.stored >= self.config.min_mass_for_mex:
                    client.build(acu, "mex_t1", spot.position)
                    self._targeted_mex_spots.append((spot.x, spot.z))
                    self._last_order_tick = state.tick
            else:
                # No more immediate nearby mexes, proceed to radar
                self.step_index = 6
            return True

        # Step 6: Radar T1
        elif self.step_index == 6:
            if len(radars) >= 1:
                self.step_index = 7
                self.is_completed = True
                return False
            else:
                r_pos = (self.spawn_pos[0] + 6.0, 0.0, self.spawn_pos[2] - 6.0)
                if state.economy.mass.stored >= 50.0:
                    client.build(acu, "radar_t1", r_pos)
                    self._last_order_tick = state.tick
            return True

        # Step 7: Completed
        else:
            self.is_completed = True
            return False

    def _get_closest_free_mex(self, from_pos: Tuple[float, float, float], state: GameState) -> Optional[MassSpot]:
        free_spots = [
            s for s in state.mass_spots
            if s.is_free and (s.x, s.z) not in self._targeted_mex_spots
        ]
        if not free_spots:
            return None
        return min(free_spots, key=lambda s: math.hypot(s.x - from_pos[0], s.z - from_pos[2]))
