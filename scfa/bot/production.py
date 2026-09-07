"""
Factory Production Queue Manager for Supreme Commander: Forged Alliance.

Maintains unit compositions across factories, prioritizing early engineers
and scouts, followed by an optimal ratio of main battle tanks, mobile artillery, and anti-air.
"""

import random
from typing import Optional
from ..state import GameState
from ..client import SCFAClient
from .config import BotConfig


class ProductionManager:
    """
    Manages production orders across Land, Air, and Naval factories.
    """

    def __init__(self, config: Optional[BotConfig] = None):
        self.config = config or BotConfig()
        self._last_produce_tick: int = 0
        self._unit_counter: int = 0

    def update(self, state: GameState, client: SCFAClient, is_stalling: bool = False) -> None:
        """
        Updates factory production queues across all active factories.
        """
        factories = [f for f in state.get_factories() if f.is_complete]
        if not factories:
            return

        # Throttle production queue checks (every 5 ticks)
        if state.tick - self._last_produce_tick < 5:
            return
        self._last_produce_tick = state.tick

        engineers = state.get_engineers()
        scouts = state.get_scouts()

        for fac in factories:
            # 1. PRIORITY 1: Ensure baseline expansion engineers
            if len(engineers) < self.config.target_engineers:
                client.produce(fac, "engineer_t1", count=1)
                engineers.append(fac)  # optimistic counter
                continue

            # 2. PRIORITY 2: Ensure baseline recon scouts
            if len(scouts) < self.config.target_scouts:
                client.produce(fac, "scout_land_t1", count=1)
                scouts.append(fac)
                continue

            # 3. PRIORITY 3: Continuous Combat Unit Production
            if is_stalling and state.economy.mass.stored < 15.0:
                # When stalling hard, avoid excessive queueing
                continue

            # Cycle unit types to respect composition ratios (60% tank, 25% arty, 15% aa)
            self._unit_counter += 1
            idx = self._unit_counter % 20

            if idx < 12:
                # 60% Main Battle Tanks
                client.produce(fac, "tank_t1", count=2)
            elif idx < 17:
                # 25% Mobile Artillery
                client.produce(fac, "artillery_t1", count=1)
            else:
                # 15% Mobile Anti-Air / Assault
                client.produce(fac, "tank_t1", count=1)
