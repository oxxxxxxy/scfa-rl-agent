"""
Main programmatic client and GameSession for Supreme Commander: Forged Alliance.
"""

import time
from typing import Any, Dict, List, Optional, Tuple, Union

from .blueprints import Faction, get_blueprint
from .commands import (
    AttackCommand,
    AttackMoveCommand,
    BuildFactoryCommand,
    BuildMobileCommand,
    CommandBuffer,
    EnhanceCommand,
    GuardCommand,
    MoveCommand,
    OverchargeCommand,
    PatrolCommand,
    ReclaimCommand,
    SetArmyCommand,
    SetSpeedCommand,
    StopCommand,
    UpgradeCommand,
)
from .ipc import SCFAIPC
from .launcher import GameLauncher
from .state import GameState, Unit


class SCFAClient:
    """
    Programmatic Client API for Supreme Commander: Forged Alliance.
    Provides complete state observation and unit manipulation methods.
    """

    def __init__(self, ipc: Optional[SCFAIPC] = None, faction: Faction = Faction.CYBRAN):
        self.ipc = ipc or SCFAIPC()
        self.faction = faction
        self.buffer = CommandBuffer()
        self._last_state: Optional[GameState] = None

    def get_state(self, timeout_sec: Optional[float] = 10.0) -> GameState:
        """
        Retrieves the latest complete game state snapshot from the simulation.
        Blocks until the in-game loop emits a new state or timeout occurs.
        """
        raw_data = self.ipc.wait_for_state(timeout_sec=timeout_sec)
        if raw_data is None:
            if self._last_state is not None:
                return self._last_state
            raise TimeoutError("Timed out waiting for game state from Supreme Commander.")

        self._last_state = GameState.from_dict(raw_data, client=self)
        return self._last_state

    def step(self, seconds: float = 1.0, timeout_sec: Optional[float] = 10.0) -> GameState:
        """
        Flushes all buffered commands to the game and advances the simulation.
        Returns the new GameState after the step.
        """
        # 1. Flush buffered commands
        commands = self.buffer.flush()
        self.ipc.send_commands(commands)

        # 2. Wait for next state update
        return self.get_state(timeout_sec=timeout_sec)

    # -------------------------------------------------------------------------
    # Unit Command Methods
    # -------------------------------------------------------------------------

    def _resolve_unit_ids(self, units: Union[int, Unit, List[Union[int, Unit]]]) -> List[int]:
        if isinstance(units, (int, Unit)):
            units = [units]
        return [u.id if isinstance(u, Unit) else int(u) for u in units]

    def move(
        self,
        units: Union[int, Unit, List[Union[int, Unit]]],
        target: Tuple[float, float, float]
    ) -> None:
        """Orders units to move to target coordinates."""
        unit_ids = self._resolve_unit_ids(units)
        self.buffer.add(MoveCommand(units=unit_ids, target=target))

    def attack_move(
        self,
        units: Union[int, Unit, List[Union[int, Unit]]],
        target: Tuple[float, float, float]
    ) -> None:
        """Orders units to aggressive-move towards target coordinates, engaging enemies en route."""
        unit_ids = self._resolve_unit_ids(units)
        self.buffer.add(AttackMoveCommand(units=unit_ids, target=target))

    def attack(
        self,
        units: Union[int, Unit, List[Union[int, Unit]]],
        target: Union[int, Unit]
    ) -> None:
        """Orders units to focus-fire a specific target unit."""
        unit_ids = self._resolve_unit_ids(units)
        target_id = target.id if isinstance(target, Unit) else int(target)
        self.buffer.add(AttackCommand(units=unit_ids, target_id=target_id))

    def guard(
        self,
        units: Union[int, Unit, List[Union[int, Unit]]],
        target: Union[int, Unit]
    ) -> None:
        """Orders units to escort, assist, or protect a friendly unit."""
        unit_ids = self._resolve_unit_ids(units)
        target_id = target.id if isinstance(target, Unit) else int(target)
        self.buffer.add(GuardCommand(units=unit_ids, target_id=target_id))

    def patrol(
        self,
        units: Union[int, Unit, List[Union[int, Unit]]],
        target: Tuple[float, float, float]
    ) -> None:
        """Orders units to establish a patrol loop to the target position."""
        unit_ids = self._resolve_unit_ids(units)
        self.buffer.add(PatrolCommand(units=unit_ids, target=target))

    def stop(self, units: Union[int, Unit, List[Union[int, Unit]]]) -> None:
        """Cancels all active orders and stops the given units."""
        unit_ids = self._resolve_unit_ids(units)
        self.buffer.add(StopCommand(units=unit_ids))

    def build(
        self,
        builder: Union[int, Unit],
        blueprint: str,
        target: Tuple[float, float, float]
    ) -> None:
        """Orders an engineer, ACU, or SACU to construct a structure at the target location."""
        builder_id = builder.id if isinstance(builder, Unit) else int(builder)
        actual_bp = get_blueprint(self.faction, blueprint)
        self.buffer.add(BuildMobileCommand(builder=builder_id, blueprint=actual_bp, target=target))

    def produce(
        self,
        factory: Union[int, Unit],
        blueprint: str,
        count: int = 1
    ) -> None:
        """Queues production of units or experimentals inside a factory."""
        factory_id = factory.id if isinstance(factory, Unit) else int(factory)
        actual_bp = get_blueprint(self.faction, blueprint)
        self.buffer.add(BuildFactoryCommand(factory=factory_id, blueprint=actual_bp, count=count))

    def upgrade(
        self,
        unit: Union[int, Unit],
        blueprint: str
    ) -> None:
        """Orders a factory, mex, or radar to upgrade to next tier (T1->T2->T3)."""
        unit_id = unit.id if isinstance(unit, Unit) else int(unit)
        actual_bp = get_blueprint(self.faction, blueprint)
        self.buffer.add(UpgradeCommand(unit=unit_id, blueprint=actual_bp))

    def enhance(
        self,
        unit: Union[int, Unit],
        enhancement_name: str
    ) -> None:
        """Orders an enhancement on ACU or SACU (e.g. Gunnery, RAS, Stealth, Shield)."""
        unit_id = unit.id if isinstance(unit, Unit) else int(unit)
        self.buffer.add(EnhanceCommand(unit=unit_id, enhancement=enhancement_name))

    def reclaim(
        self,
        builder: Union[int, Unit],
        target: Optional[Tuple[float, float, float]] = None,
        target_id: Optional[int] = None
    ) -> None:
        """Orders an engineer or ACU to reclaim nearby props/wreckage or a specific target."""
        builder_id = builder.id if isinstance(builder, Unit) else int(builder)
        self.buffer.add(ReclaimCommand(builder=builder_id, target=target, target_id=target_id))

    def overcharge(
        self,
        commander: Union[int, Unit],
        target: Tuple[float, float, float]
    ) -> None:
        """Fires Commander Overcharge weapon at target coordinates."""
        commander_id = commander.id if isinstance(commander, Unit) else int(commander)
        self.buffer.add(OverchargeCommand(commander=commander_id, target=target))

    def set_game_speed(self, speed: int) -> None:
        """Adjusts in-game simulation speed (-10 to +10)."""
        self.buffer.add(SetSpeedCommand(speed=speed))

    def set_army(self, army_index: int) -> None:
        """Switches controlled bot army (e.g. 1, 2)."""
        self.buffer.add(SetArmyCommand(army=army_index))

    def configure(self, army: int = 1, speed: int = 10, disable_ai: bool = True) -> None:
        """Configures the in-game bridge parameters via config file and live command buffer."""
        self.ipc.write_config(army=army, speed=speed, disable_ai=disable_ai)
        self.set_army(army)
        self.set_speed(speed)


class GameSession:
    """
    High-level manager to launch, control, and shut down a Supreme Commander match.
    """

    def __init__(
        self,
        map_name: str = "SCMP_009",
        faction: Faction = Faction.CYBRAN,
        enemy_ai: str = "medium",
        game_speed: int = 10,
        headless: bool = True
    ):
        self.map_name = map_name
        self.faction = faction
        self.enemy_ai = enemy_ai
        self.game_speed = game_speed
        self.headless = headless

        self.launcher = GameLauncher()
        self.ipc = SCFAIPC()
        self.client = SCFAClient(ipc=self.ipc, faction=self.faction)

    def start(self, wait_initial_state: bool = True, timeout_sec: float = 30.0) -> SCFAClient:
        """Starts the game process and returns the connected SCFAClient."""
        self.ipc.clean()
        self.ipc.write_config(army=1, speed=self.game_speed, disable_ai=False)
        self.launcher.launch(
            map_name=self.map_name,
            faction=self.faction,
            enemy_ai=self.enemy_ai,
            game_speed=self.game_speed,
            headless=self.headless
        )

        if wait_initial_state:
            self.client.get_state(timeout_sec=timeout_sec)

        return self.client

    def stop(self) -> None:
        """Terminates the match and cleans up IPC handles."""
        self.ipc.request_stop()
        time.sleep(0.1)
        self.launcher.terminate()
        self.ipc.clean()

    def __enter__(self) -> SCFAClient:
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()
