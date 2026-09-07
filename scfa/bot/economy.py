"""
Streaming Economy Regulator for Supreme Commander: Forged Alliance.

Prevents catastrophic energy stalls, dampens mass fluctuations, and
triggers tier upgrades (T1 -> T2 -> T3) when resources overflow.
"""

import math
from typing import List, Optional, Tuple
from ..state import GameState, Unit
from ..client import SCFAClient
from .config import BotConfig


class EconomyManager:
    """
    Manages continuous resource flow and prevents economic stalling.
    """

    def __init__(self, config: Optional[BotConfig] = None):
        self.config = config or BotConfig()
        self._pgen_offset_idx: int = 0
        self._last_pgen_tick: int = 0
        self._last_upgrade_tick: int = 0

    def is_energy_stalling(self, state: GameState) -> bool:
        """Returns True if energy reserves or net income are dangerously low."""
        econ = state.economy.energy
        if econ.stored < self.config.min_energy_reserve:
            return True
        if econ.income < econ.usage * self.config.energy_income_ratio and econ.stored < 400.0:
            return True
        return False

    def is_mass_stalling(self, state: GameState) -> bool:
        """Returns True if mass reserves are critically low with negative net income."""
        econ = state.economy.mass
        net_flow = econ.income - econ.usage
        return econ.stored < self.config.mass_stall_threshold and net_flow < -1.0

    def is_mass_overflowing(self, state: GameState) -> bool:
        """Returns True if mass storage is near full capacity and income is healthy."""
        econ = state.economy.mass
        return econ.ratio >= self.config.mass_overflow_ratio and econ.income >= 10.0

    def balance(self, state: GameState, client: SCFAClient, available_builders: List[Unit], base_pos: Tuple[float, float, float]) -> None:
        """
        Main economic balancing routine called every simulation step.
        """
        if not available_builders:
            return

        # 1. PRIORITY 1: Emergency Energy Generation
        if self.is_energy_stalling(state) and (state.tick - self._last_pgen_tick >= 10):
            if state.economy.mass.stored >= self.config.min_mass_for_pgen:
                builder = available_builders[0]
                build_pos = self._get_next_pgen_pos(base_pos)
                client.build(builder, "power_t1", build_pos)
                self._last_pgen_tick = state.tick
                return

        # 2. PRIORITY 2: Mass Overflow Upgrades (T1 -> T2 Mex)
        if self.is_mass_overflowing(state) and (state.tick - self._last_upgrade_tick >= 15):
            # Check T1 mexes that are complete and not already upgrading
            t1_mexes = [m for m in state.get_mexes() if m.is_complete and "TECH1" in m.tags]
            if t1_mexes:
                target_mex = t1_mexes[0]
                client.upgrade(target_mex, "mex_t2")
                self._last_upgrade_tick = state.tick
                return

            # Check T1 factories for T2 upgrade
            t1_factories = [f for f in state.get_factories() if f.is_complete and "TECH1" in f.tags]
            if t1_factories and state.economy.mass.stored > 280.0 and state.economy.energy.stored > 500.0:
                client.upgrade(t1_factories[0], "factory_land_t2")
                self._last_upgrade_tick = state.tick
                return

    def _get_next_pgen_pos(self, base_pos: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """Calculates non-overlapping coordinates in a cluster around the base."""
        # Spiral pattern offsets
        offsets = [
            (5.0, 4.0), (-5.0, 4.0), (5.0, -4.0), (-5.0, -4.0),
            (10.0, 0.0), (-10.0, 0.0), (0.0, 10.0), (0.0, -10.0),
            (10.0, 8.0), (-10.0, 8.0), (10.0, -8.0), (-10.0, -8.0),
            (15.0, 4.0), (-15.0, 4.0), (15.0, -4.0), (-15.0, -4.0)
        ]
        dx, dz = offsets[self._pgen_offset_idx % len(offsets)]
        self._pgen_offset_idx += 1
        return (base_pos[0] + dx, 0.0, base_pos[2] + dz)
