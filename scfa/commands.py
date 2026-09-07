"""
Command models and CommandBuffer for Supreme Commander: Forged Alliance.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union


@dataclass
class Command:
    def to_dict(self) -> Dict[str, Any]:
        raise NotImplementedError


@dataclass
class MoveCommand(Command):
    units: List[int]
    target: Tuple[float, float, float]

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "move", "units": self.units, "target": list(self.target)}


@dataclass
class AttackMoveCommand(Command):
    units: List[int]
    target: Tuple[float, float, float]

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "attack_move", "units": self.units, "target": list(self.target)}


@dataclass
class AttackCommand(Command):
    units: List[int]
    target_id: int

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "attack", "units": self.units, "target_id": self.target_id}


@dataclass
class GuardCommand(Command):
    units: List[int]
    target_id: int

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "guard", "units": self.units, "target_id": self.target_id}


@dataclass
class PatrolCommand(Command):
    units: List[int]
    target: Tuple[float, float, float]

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "patrol", "units": self.units, "target": list(self.target)}


@dataclass
class StopCommand(Command):
    units: List[int]

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "stop", "units": self.units}


@dataclass
class BuildMobileCommand(Command):
    builder: int
    blueprint: str
    target: Tuple[float, float, float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "build_mobile",
            "builder": self.builder,
            "blueprint": self.blueprint,
            "target": list(self.target)
        }


@dataclass
class BuildFactoryCommand(Command):
    factory: int
    blueprint: str
    count: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "build_factory",
            "factory": self.factory,
            "blueprint": self.blueprint,
            "count": self.count
        }


@dataclass
class UpgradeCommand(Command):
    unit: int
    blueprint: str

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "upgrade", "unit": self.unit, "blueprint": self.blueprint}


@dataclass
class ReclaimCommand(Command):
    builder: int
    target: Optional[Tuple[float, float, float]] = None
    target_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        data = {"type": "reclaim", "builder": self.builder}
        if self.target_id is not None:
            data["target_id"] = self.target_id
        if self.target is not None:
            data["target"] = list(self.target)
        return data


@dataclass
class OverchargeCommand(Command):
    commander: int
    target: Tuple[float, float, float]

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "overcharge", "commander": self.commander, "target": list(self.target)}


@dataclass
class SetSpeedCommand(Command):
    speed: int

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "set_speed", "speed": self.speed}


class CommandBuffer:
    """Accumulates commands before flushing to the in-game Lua loop."""

    def __init__(self):
        self._commands: List[Command] = []

    def add(self, command: Command) -> None:
        self._commands.append(command)

    def is_empty(self) -> bool:
        return len(self._commands) == 0

    def flush(self) -> List[Dict[str, Any]]:
        cmds = [c.to_dict() for c in self._commands]
        self._commands.clear()
        return cmds

    def clear(self) -> None:
        self._commands.clear()
