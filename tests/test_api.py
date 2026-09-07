"""
Unit tests for SCFA Python Programmatic API.
"""

from scfa.blueprints import Faction, get_blueprint
from scfa.client import SCFAClient
from scfa.ipc import SCFAIPC
from scfa.state import GameState


def test_blueprint_resolution():
    assert get_blueprint(Faction.CYBRAN, "mex_t1") == "urb1102"
    assert get_blueprint(Faction.UEF, "mex_t1") == "ueb1102"
    assert get_blueprint(Faction.AEON, "factory_land_t1") == "uab0101"
    assert get_blueprint(Faction.SERAPHIM, "commander") == "xsl0001"


def test_gamestate_and_unit_queries():
    sample_data = {
        "step": 5,
        "army_index": 1,
        "game_time": 25.0,
        "game_tick": 250,
        "game_speed": 10.0,
        "is_over": False,
        "map": {"width": 512, "height": 512},
        "economy": {
            "mass": {"stored": 1200, "capacity": 2000, "income": 45.5, "usage": 30.0, "requested": 30.0, "trend": 15.5},
            "energy": {"stored": 8000, "capacity": 10000, "income": 550.0, "usage": 400.0, "requested": 400.0, "trend": 150.0}
        },
        "units": [
            {
                "id": 1,
                "bp": "url0001",
                "pos": [100.0, 15.0, 120.0],
                "hp": 12000.0,
                "max_hp": 12000.0,
                "fraction": 1.0,
                "tags": ["COMMANDER", "LAND", "DIRECTFIRE"],
                "mass_in": 1.0,
                "mass_out": 0.0,
                "energy_in": 20.0,
                "energy_out": 0.0,
                "build_rate": 10.0
            },
            {
                "id": 2,
                "bp": "url0105",
                "pos": [105.0, 15.0, 125.0],
                "hp": 260.0,
                "max_hp": 260.0,
                "fraction": 1.0,
                "tags": ["ENGINEER", "LAND", "TECH1"],
                "mass_in": 0.0,
                "mass_out": 2.0,
                "energy_in": 0.0,
                "energy_out": 10.0,
                "build_rate": 5.0
            },
            {
                "id": 3,
                "bp": "urb0101",
                "pos": [90.0, 15.0, 110.0],
                "hp": 3200.0,
                "max_hp": 3200.0,
                "fraction": 1.0,
                "tags": ["FACTORY", "STRUCTURE", "LAND", "TECH1"],
                "mass_in": 0.0,
                "mass_out": 15.0,
                "energy_in": 0.0,
                "energy_out": 50.0,
                "build_rate": 20.0
            },
            {
                "id": 4,
                "bp": "url0107",
                "pos": [150.0, 15.0, 180.0],
                "hp": 290.0,
                "max_hp": 290.0,
                "fraction": 1.0,
                "tags": ["LAND", "DIRECTFIRE", "TECH1"]
            },
            {
                "id": 5,
                "bp": "url0301",
                "pos": [110.0, 15.0, 130.0],
                "hp": 10000.0,
                "max_hp": 10000.0,
                "fraction": 1.0,
                "tags": ["SUBCOMMANDER", "LAND", "DIRECTFIRE"]
            },
            {
                "id": 6,
                "bp": "urb3101",
                "pos": [80.0, 15.0, 100.0],
                "hp": 500.0,
                "max_hp": 500.0,
                "fraction": 1.0,
                "tags": ["RADAR", "STRUCTURE", "TECH1"]
            },
            {
                "id": 7,
                "bp": "url0402",
                "pos": [160.0, 15.0, 190.0],
                "hp": 45000.0,
                "max_hp": 45000.0,
                "fraction": 1.0,
                "tags": ["EXPERIMENTAL", "LAND", "DIRECTFIRE"]
            }
        ],
        "enemies": [
            {
                "id": 99,
                "bp": "uel0201",
                "pos": [400.0, 15.0, 420.0],
                "hp": 300.0,
                "max_hp": 300.0,
                "tags": ["LAND", "DIRECTFIRE", "TECH1"]
            }
        ],
        "mass_spots": [
            {"x": 108.0, "z": 128.0, "status": "free"},
            {"x": 120.0, "z": 140.0, "status": "ally"},
            {"x": 395.0, "z": 415.0, "status": "enemy"}
        ]
    }

    client = SCFAClient()
    state = GameState.from_dict(sample_data, client=client)

    # Test Economy Queries
    assert state.economy.mass.stored == 1200.0
    assert state.economy.mass.income == 45.5
    assert state.economy.energy.stored == 8000.0

    # Test Unit Helper Queries
    acu = state.get_commander()
    assert acu is not None
    assert acu.id == 1
    assert acu.is_commander
    assert acu.mass_in == 1.0
    assert acu.energy_in == 20.0
    assert acu.build_rate == 10.0

    engineers = state.get_engineers()
    assert len(engineers) == 1
    assert engineers[0].mass_out == 2.0

    factories = state.get_factories()
    assert len(factories) == 1
    assert factories[0].build_rate == 20.0

    combat = state.get_combat_units()
    assert len(combat) == 2  # Unit 4 and Unit 7 (experimental)
    assert not any(u.is_commander for u in combat)

    sacus = state.get_subcommanders()
    assert len(sacus) == 1
    assert sacus[0].id == 5

    radars = state.get_radars()
    assert len(radars) == 1
    assert radars[0].id == 6

    exps = state.get_experimentals()
    assert len(exps) == 1
    assert exps[0].id == 7

    # Test Mass Spots Queries
    nearest_mex = state.get_nearest_free_mex(acu.position)
    assert nearest_mex is not None
    assert nearest_mex.x == 108.0
    assert nearest_mex.is_free

    # Test Enemies Queries
    enemies = state.get_enemy_units()
    assert len(enemies) == 1
    assert enemies[0].id == 99

    # Test Fluent Commands
    acu.move((150.0, 0.0, 160.0))
    acu.enhance("CoolingUpgrade")
    engineers[0].build("mex_t1", nearest_mex.position)
    factories[0].queue("tank_t1", count=5)
    combat[0].attack(enemies[0])
    client.set_army(2)

    # Check that commands accumulated in client buffer
    cmds = client.buffer.flush()
    assert len(cmds) == 6
    assert cmds[0]["type"] == "move"
    assert cmds[1]["type"] == "enhance"
    assert cmds[1]["unit"] == 1
    assert cmds[1]["enhancement"] == "CoolingUpgrade"
    assert cmds[2]["type"] == "build_mobile"
    assert cmds[2]["builder"] == 2
    assert cmds[3]["type"] == "build_factory"
    assert cmds[4]["type"] == "attack"
    assert cmds[5]["type"] == "set_army"
    assert cmds[5]["army"] == 2
