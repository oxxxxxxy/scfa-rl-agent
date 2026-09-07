"""
Supreme Commander: Forged Alliance Rule-Based AI Package.
"""

from .config import BotConfig
from .build_order import BuildOrderManager
from .economy import EconomyManager
from .production import ProductionManager
from .expansion import ExpansionManager
from .military import MilitaryManager
from .brain import RuleBasedBot

__all__ = [
    "BotConfig",
    "BuildOrderManager",
    "EconomyManager",
    "ProductionManager",
    "ExpansionManager",
    "MilitaryManager",
    "RuleBasedBot",
]
