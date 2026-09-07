"""
Supreme Commander: Forged Alliance — Python Programmatic API (SCFA API)
"""

from .blueprints import Faction, get_blueprint
from .client import GameSession, SCFAClient
from .commands import (
    AttackCommand,
    AttackMoveCommand,
    BuildFactoryCommand,
    BuildMobileCommand,
    Command,
    CommandBuffer,
    GuardCommand,
    MoveCommand,
    OverchargeCommand,
    PatrolCommand,
    ReclaimCommand,
    SetSpeedCommand,
    StopCommand,
    UpgradeCommand,
)
from .ipc import SCFAIPC
from .launcher import GameLauncher
from .state import EconomyState, GameState, MassSpot, ResourceRate, Unit

__all__ = [
    "SCFAClient",
    "GameSession",
    "GameState",
    "Unit",
    "MassSpot",
    "EconomyState",
    "ResourceRate",
    "Faction",
    "get_blueprint",
    "SCFAIPC",
    "GameLauncher",
    "Command",
    "CommandBuffer",
    "MoveCommand",
    "AttackMoveCommand",
    "AttackCommand",
    "GuardCommand",
    "PatrolCommand",
    "StopCommand",
    "BuildMobileCommand",
    "BuildFactoryCommand",
    "UpgradeCommand",
    "ReclaimCommand",
    "OverchargeCommand",
    "SetSpeedCommand",
]
