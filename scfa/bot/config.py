"""
Configuration parameters for Rule-Based Bot in Supreme Commander: Forged Alliance.
"""

from dataclasses import dataclass


@dataclass
class BotConfig:
    # --- Economy Parameters ---
    min_energy_reserve: float = 120.0
    energy_income_ratio: float = 1.15
    mass_stall_threshold: float = 20.0
    mass_overflow_ratio: float = 0.80
    min_mass_for_factory: float = 120.0
    min_mass_for_pgen: float = 60.0
    min_mass_for_mex: float = 36.0

    # --- Engineer & Expansion Parameters ---
    max_expansion_engineers: int = 4
    max_safe_expansion_dist: float = 220.0
    base_defense_count: int = 2

    # --- Factory & Military Composition ---
    min_platoon_size: int = 8
    target_engineers: int = 3
    target_scouts: int = 1
    target_tanks_ratio: float = 0.60
    target_arty_ratio: float = 0.25
    target_aa_ratio: float = 0.15

    # --- ACU & Tactical Parameters ---
    acu_retreat_health_ratio: float = 0.45
    acu_overcharge_energy_min: float = 2500.0
    acu_combat_engage_dist: float = 25.0
    base_threat_alert_dist: float = 65.0
