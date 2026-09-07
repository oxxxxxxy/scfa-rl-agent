"""
Blueprints and Faction definitions for Supreme Commander: Forged Alliance.
"""

from enum import IntEnum
from typing import Dict


class Faction(IntEnum):
    UEF = 1
    AEON = 2
    CYBRAN = 3
    SERAPHIM = 4


# Common Blueprint Catalog for standard RTS structures and units
BLUEPRINT_CATALOG: Dict[Faction, Dict[str, str]] = {
    Faction.UEF: {
        "commander": "uel0001",
        "engineer_t1": "uel0105",
        "mex_t1": "ueb1102",
        "mex_t2": "ueb1202",
        "mex_t3": "ueb1302",
        "power_t1": "ueb1101",
        "hydro": "ueb1105",
        "power_t2": "ueb1201",
        "power_t3": "ueb1301",
        "factory_land_t1": "ueb0101",
        "factory_air_t1": "ueb0102",
        "factory_naval_t1": "ueb0103",
        "point_defense_t1": "ueb2101",
        "anti_air_t1": "ueb2104",
        "radar_t1": "ueb3101",
        "tank_t1": "uel0201",
        "scout_land_t1": "uel0101",
        "artillery_t1": "uel0103",
        "interceptor_t1": "uea0102",
        "bomber_t1": "uea0103"
    },
    Faction.AEON: {
        "commander": "ual0001",
        "engineer_t1": "ual0105",
        "mex_t1": "uab1102",
        "mex_t2": "uab1202",
        "mex_t3": "uab1302",
        "power_t1": "uab1101",
        "hydro": "uab1105",
        "power_t2": "uab1201",
        "power_t3": "uab1301",
        "factory_land_t1": "uab0101",
        "factory_air_t1": "uab0102",
        "factory_naval_t1": "uab0103",
        "point_defense_t1": "uab2101",
        "anti_air_t1": "uab2104",
        "radar_t1": "uab3101",
        "tank_t1": "ual0201",
        "scout_land_t1": "ual0101",
        "artillery_t1": "ual0103",
        "interceptor_t1": "uaa0102",
        "bomber_t1": "uaa0103"
    },
    Faction.CYBRAN: {
        "commander": "url0001",
        "engineer_t1": "url0105",
        "mex_t1": "urb1102",
        "mex_t2": "urb1202",
        "mex_t3": "urb1302",
        "power_t1": "urb1101",
        "hydro": "urb1105",
        "power_t2": "urb1201",
        "power_t3": "urb1301",
        "factory_land_t1": "urb0101",
        "factory_air_t1": "urb0102",
        "factory_naval_t1": "urb0103",
        "point_defense_t1": "urb2101",
        "anti_air_t1": "urb2104",
        "radar_t1": "urb3101",
        "tank_t1": "url0107",
        "scout_land_t1": "url0101",
        "artillery_t1": "url0103",
        "interceptor_t1": "ura0102",
        "bomber_t1": "ura0103"
    },
    Faction.SERAPHIM: {
        "commander": "xsl0001",
        "engineer_t1": "xsl0105",
        "mex_t1": "xsb1102",
        "mex_t2": "xsb1202",
        "mex_t3": "xsb1302",
        "power_t1": "xsb1101",
        "hydro": "xsb1105",
        "power_t2": "xsb1201",
        "power_t3": "xsb1301",
        "factory_land_t1": "xsb0101",
        "factory_air_t1": "xsb0102",
        "factory_naval_t1": "xsb0103",
        "point_defense_t1": "xsb2101",
        "anti_air_t1": "xsb2104",
        "radar_t1": "xsb3101",
        "tank_t1": "xsl0201",
        "scout_land_t1": "xsl0101",
        "artillery_t1": "xsl0103",
        "interceptor_t1": "xsa0102",
        "bomber_t1": "xsa0103"
    }
}


def get_blueprint(faction: Faction, name: str) -> str:
    """Returns the faction-specific blueprint ID for a given canonical structure/unit name."""
    cat = BLUEPRINT_CATALOG.get(faction, BLUEPRINT_CATALOG[Faction.CYBRAN])
    if name in cat:
        return cat[name]
    return name  # Assume raw blueprint ID if not in canonical catalog
