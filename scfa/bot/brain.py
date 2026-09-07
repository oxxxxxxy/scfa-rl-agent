"""
Central Rule-Based AI Coordinator for Supreme Commander: Forged Alliance.

Integrates Build Order FSM, Streaming Economy Balancing, Factory Production,
Territorial Expansion, and Military Tactical Coordination into a unified agent.
"""

import time
from typing import List, Optional, Tuple

from ..client import SCFAClient
from ..state import GameState, Unit
from .build_order import BuildOrderManager
from .config import BotConfig
from .economy import EconomyManager
from .expansion import ExpansionManager
from .military import MilitaryManager
from .production import ProductionManager


class RuleBasedBot:
    """
    Expert system AI bot for Supreme Commander: Forged Alliance.
    """

    def __init__(self, client: SCFAClient, config: Optional[BotConfig] = None):
        self.client = client
        self.config = config or BotConfig()

        # Modular Subsystems
        self.build_order = BuildOrderManager(self.config)
        self.economy = EconomyManager(self.config)
        self.production = ProductionManager(self.config)
        self.expansion = ExpansionManager(self.config)
        self.military = MilitaryManager(self.config)

        # Strategic Memory
        self.base_pos: Optional[Tuple[float, float, float]] = None
        self.estimated_enemy_pos: Optional[Tuple[float, float, float]] = None

    def reset(self) -> None:
        """Resets bot internal memory and state machines for a new match."""
        self.build_order.reset()
        self.expansion.reset()
        self.base_pos = None
        self.estimated_enemy_pos = None

    def step(self, state: GameState) -> None:
        """
        Executes one decision step of the rule-based AI on the given GameState.
        """
        if state.is_over:
            return

        acu = state.get_commander()
        if not acu or not acu.is_alive:
            return

        # 1. Initialize Base and Enemy Coordinates on first tick
        if self.base_pos is None:
            self.base_pos = acu.position
            # Estimate enemy spawn symmetrically mirrored across the map center
            self.estimated_enemy_pos = (
                max(30.0, min(state.map_width - self.base_pos[0], state.map_width - 30.0)),
                0.0,
                max(30.0, min(state.map_height - self.base_pos[2], state.map_height - 30.0))
            )

        # 2. Early-Game Build Order Execution
        in_opening = False
        if not self.build_order.is_completed:
            in_opening = self.build_order.update(state, self.client)

        # 3. Identify Available Builder Units
        engineers = state.get_engineers()
        available_builders: List[Unit] = list(engineers)
        # Only assign free-form tasks to ACU if opening build order is finished
        if self.build_order.is_completed:
            available_builders.append(acu)

        # 4. Economy Balancing (Energy stalling mitigation & Tech upgrades)
        self.economy.balance(state, self.client, available_builders, self.base_pos)

        # 5. Factory Production Queues
        is_stalling = self.economy.is_mass_stalling(state) or self.economy.is_energy_stalling(state)
        self.production.update(state, self.client, is_stalling=is_stalling)

        # 6. Territorial Expansion & Engineer Dispatch
        self.expansion.dispatch(
            state=state,
            client=self.client,
            available_engineers=engineers,
            base_pos=self.base_pos,
            enemy_pos=self.estimated_enemy_pos
        )

        # 7. Military Tactical Coordination & Base Defense
        self.military.update(
            state=state,
            client=self.client,
            base_pos=self.base_pos,
            estimated_enemy_pos=self.estimated_enemy_pos
        )

    def run(self, max_steps: Optional[int] = None, step_delay: float = 0.0) -> None:
        """
        Runs the bot main loop against the simulation client.
        """
        print("=== Rule-Based SCFA Bot Started ===")
        step_count = 0

        while True:
            step_count += 1
            if max_steps and step_count > max_steps:
                print(f"Reached maximum steps limit ({max_steps}). Stopping bot.")
                break

            # 1. Receive state snapshot
            state = self.client.get_state()
            if state.is_over:
                print("Game session marked as over. Terminating loop.")
                break

            # 2. Log periodic telemetry
            if step_count % 10 == 1 or step_count <= 5:
                acu = state.get_commander()
                hp_str = f"{acu.health:.0f}/{acu.max_health:.0f}" if acu else "DEAD"
                m_net = state.economy.mass.income - state.economy.mass.usage
                e_net = state.economy.energy.income - state.economy.energy.usage
                print(
                    f"[{step_count:4d}] Time: {state.time:5.1f}s | "
                    f"M: {state.economy.mass.stored:4.0f} ({m_net:+4.1f}/s) | "
                    f"E: {state.economy.energy.stored:5.0f} ({e_net:+5.1f}/s) | "
                    f"ACU: {hp_str} | "
                    f"Facs: {len(state.get_factories())} | "
                    f"Engs: {len(state.get_engineers())} | "
                    f"Army: {len(state.get_combat_units())} | "
                    f"Enemies: {len(state.get_enemy_units())}"
                )

            # 3. Compute and buffer bot actions
            self.step(state)

            # 4. Flush actions and advance simulation
            self.client.step()

            if step_delay > 0:
                time.sleep(step_delay)

        print("=== Rule-Based SCFA Bot Finished ===")
