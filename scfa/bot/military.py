"""
Military Platoon Coordinator & Tactical Combat Manager for Supreme Commander: Forged Alliance.

Coordinates:
1. Rally point staging (force concentration before assault).
2. Base defense (intercepting hostiles near ACU / factories).
3. Coordinated offensive waves (attack-move into enemy territory).
4. ACU survival & combat micro (retreat under fire, Overcharge).
5. Scout patrol paths.
"""

import math
from typing import List, Optional, Tuple
from ..state import GameState, Unit
from ..client import SCFAClient
from .config import BotConfig


class MilitaryManager:
    """
    Manages combat units, scouts, platoons, and ACU tactical defense.
    """

    def __init__(self, config: Optional[BotConfig] = None):
        self.config = config or BotConfig()
        self._last_order_tick: int = 0
        self._last_scout_tick: int = 0

    def update(
        self,
        state: GameState,
        client: SCFAClient,
        base_pos: Tuple[float, float, float],
        estimated_enemy_pos: Tuple[float, float, float]
    ) -> None:
        """
        Main military tactical loop called each tick.
        """
        acu = state.get_commander()
        combat_units = state.get_combat_units()
        scouts = state.get_scouts()
        enemies = state.get_enemy_units()

        # 1. ACU Self-Preservation & Micro
        if acu and acu.is_alive:
            self._handle_acu_tactics(state, client, acu, base_pos, enemies)

        # 2. Scout Reconnaissance Patrols
        if scouts and (state.tick - self._last_scout_tick >= 20):
            self._handle_scout_recon(state, client, scouts, estimated_enemy_pos)
            self._last_scout_tick = state.tick

        # 3. Platoon Assembly & Combat Orders
        if not combat_units:
            return

        if state.tick - self._last_order_tick < 6:
            return
        self._last_order_tick = state.tick

        # Calculate Rally Point (staged 25m towards enemy)
        dir_x = estimated_enemy_pos[0] - base_pos[0]
        dir_z = estimated_enemy_pos[2] - base_pos[2]
        mag = max(math.hypot(dir_x, dir_z), 1.0)
        rally_pos = (base_pos[0] + (dir_x / mag) * 25.0, 0.0, base_pos[2] + (dir_z / mag) * 25.0)

        # Check for immediate threats near base
        base_threats = [
            e for e in enemies
            if math.hypot(e.position[0] - base_pos[0], e.position[2] - base_pos[2]) <= self.config.base_threat_alert_dist
        ]

        if base_threats:
            # DEFENSE MODE: Intercept nearest hostile to base
            target = min(
                base_threats,
                key=lambda e: math.hypot(e.position[0] - base_pos[0], e.position[2] - base_pos[2])
            )
            client.attack(combat_units, target)
            return

        # Platoon staging vs Assault wave
        if len(combat_units) < self.config.min_platoon_size:
            # Gather units at rally point
            client.move(combat_units, rally_pos)
        else:
            # ATTACK MODE: Platoon is formed, launch offensive wave
            threat_center = state.get_threat_center()
            if threat_center:
                # Attack towards visible enemy concentration
                client.attack_move(combat_units, threat_center)
            else:
                # Attack-move towards estimated enemy base
                client.attack_move(combat_units, estimated_enemy_pos)

    def _handle_acu_tactics(
        self,
        state: GameState,
        client: SCFAClient,
        acu: Unit,
        base_pos: Tuple[float, float, float],
        enemies: List[Unit]
    ) -> None:
        """Manages ACU safety, retreat, and Overcharge usage."""
        # Check ACU health ratio
        if acu.health_ratio < self.config.acu_retreat_health_ratio:
            # Critical health -> Retreat to base center
            client.move(acu, base_pos)
            return

        # Check nearby enemies
        close_enemies = [
            e for e in enemies
            if math.hypot(e.position[0] - acu.position[0], e.position[2] - acu.position[2]) <= self.config.acu_combat_engage_dist
        ]

        if close_enemies:
            target = close_enemies[0]
            # If high energy, fire Overcharge
            if state.economy.energy.stored >= self.config.acu_overcharge_energy_min:
                client.overcharge(acu, target.position)
            else:
                client.attack(acu, target)

    def _handle_scout_recon(
        self,
        state: GameState,
        client: SCFAClient,
        scouts: List[Unit],
        target_pos: Tuple[float, float, float]
    ) -> None:
        """Sends scouts on patrol across key map vantage points."""
        patrol_target = (
            target_pos[0] * 0.7 + (state.map_width * 0.3 * 0.5),
            0.0,
            target_pos[2] * 0.7 + (state.map_height * 0.3 * 0.5)
        )
        client.patrol(scouts, patrol_target)
