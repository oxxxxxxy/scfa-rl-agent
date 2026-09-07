"""
Unit tests for Supreme Commander: Forged Alliance Rule-Based AI Bot subsystems.
"""

from scfa import Faction, GameState, SCFAClient, SCFAIPC
from scfa.bot import (
    BotConfig,
    BuildOrderManager,
    EconomyManager,
    ExpansionManager,
    MilitaryManager,
    ProductionManager,
    RuleBasedBot,
)
from scfa.commands import (
    AttackCommand,
    AttackMoveCommand,
    BuildFactoryCommand,
    BuildMobileCommand,
    GuardCommand,
    MoveCommand,
    OverchargeCommand,
    UpgradeCommand,
)
from scfa.state import EconomyState, MassSpot, ResourceRate, Unit


def create_mock_state(
    tick: int = 10,
    mass_stored: float = 200.0,
    energy_stored: float = 1000.0,
    mass_income: float = 15.0,
    energy_income: float = 60.0,
    mass_usage: float = 10.0,
    energy_usage: float = 40.0,
    acu_hp: float = 12000.0,
    units=None,
    enemies=None,
    mass_spots=None
) -> GameState:
    econ = EconomyState(
        mass=ResourceRate(stored=mass_stored, capacity=1000.0, income=mass_income, usage=mass_usage),
        energy=ResourceRate(stored=energy_stored, capacity=5000.0, income=energy_income, usage=energy_usage)
    )
    unit_map = {}
    if units:
        for u in units:
            unit_map[u.id] = u

    enemy_map = {}
    if enemies:
        for e in enemies:
            enemy_map[e.id] = e

    spots = mass_spots if mass_spots is not None else [
        MassSpot(x=10.0, z=10.0, status="free"),
        MassSpot(x=20.0, z=20.0, status="free"),
        MassSpot(x=60.0, z=60.0, status="free"),
    ]

    return GameState(
        step=1,
        army_index=1,
        time=1.0,
        tick=tick,
        speed=10.0,
        is_over=False,
        map_width=256.0,
        map_height=256.0,
        economy=econ,
        units=unit_map,
        enemies=enemy_map,
        mass_spots=spots
    )


def test_build_order_manager_fsm():
    config = BotConfig()
    bo = BuildOrderManager(config)
    client = SCFAClient(ipc=SCFAIPC(shm_dir="/tmp/test_shm_bo"), faction=Faction.CYBRAN)

    acu = Unit(
        id=1,
        blueprint_id="url0001",
        position=(50.0, 0.0, 50.0),
        health=12000.0,
        max_health=12000.0,
        tags=["COMMANDER"]
    )

    # Step 0: Should order Mex 1 on closest mass spot (60, 60)
    state = create_mock_state(tick=10, units=[acu])
    assert bo.step_index == 0
    res = bo.update(state, client)
    assert res is True
    cmds = client.buffer.flush()
    assert len(cmds) == 1
    assert cmds[0]["type"] == "build_mobile"
    assert cmds[0]["blueprint"] == "urb1102"  # Cybran T1 Mex
    assert cmds[0]["target"] == [60.0, 0.0, 60.0]

    # After Mex 1 is built, should advance to Mex 2 (20, 20)
    mex1 = Unit(id=2, blueprint_id="urb1102", position=(60.0, 0.0, 60.0), health=600.0, max_health=600.0, tags=["STRUCTURE", "MASSEXTRACTION", "TECH1"])
    state = create_mock_state(tick=20, units=[acu, mex1])
    bo.update(state, client)
    assert bo.step_index == 1
    bo.update(state, client)
    cmds = client.buffer.flush()
    assert any(c["type"] == "build_mobile" and c["target"] == [20.0, 0.0, 20.0] for c in cmds)


def test_economy_manager_stalling_and_upgrades():
    config = BotConfig()
    econ_mgr = EconomyManager(config)
    client = SCFAClient(ipc=SCFAIPC(shm_dir="/tmp/test_shm_econ"), faction=Faction.CYBRAN)

    eng = Unit(id=5, blueprint_id="url0105", position=(50.0, 0.0, 50.0), health=200.0, max_health=200.0, tags=["ENGINEER", "TECH1"])

    # Test Energy Stalling: stored energy = 50 (< min 120)
    stalling_state = create_mock_state(tick=10, energy_stored=50.0, energy_income=10.0, energy_usage=50.0, units=[eng])
    assert econ_mgr.is_energy_stalling(stalling_state) is True
    econ_mgr.balance(stalling_state, client, available_builders=[eng], base_pos=(50.0, 0.0, 50.0))
    cmds = client.buffer.flush()
    assert len(cmds) == 1
    assert cmds[0]["type"] == "build_mobile"
    assert cmds[0]["blueprint"] == "urb1101"  # Cybran T1 PGen

    # Test Mass Overflow Upgrades: mass stored = 900 / 1000 (90% >= 80%)
    mex = Unit(id=10, blueprint_id="urb1102", position=(10.0, 0.0, 10.0), health=600.0, max_health=600.0, fraction_complete=1.0, tags=["STRUCTURE", "MASSEXTRACTION", "TECH1"])
    overflow_state = create_mock_state(tick=30, mass_stored=900.0, mass_income=25.0, units=[mex, eng])
    assert econ_mgr.is_mass_overflowing(overflow_state) is True
    econ_mgr.balance(overflow_state, client, available_builders=[eng], base_pos=(50.0, 0.0, 50.0))
    cmds = client.buffer.flush()
    assert len(cmds) == 1
    assert cmds[0]["type"] == "upgrade"
    assert cmds[0]["unit"] == 10
    assert cmds[0]["blueprint"] == "urb1202"  # Cybran T2 Mex


def test_production_manager_queues():
    config = BotConfig()
    prod_mgr = ProductionManager(config)
    client = SCFAClient(ipc=SCFAIPC(shm_dir="/tmp/test_shm_prod"), faction=Faction.CYBRAN)

    factory = Unit(
        id=20,
        blueprint_id="urb0101",
        position=(40.0, 0.0, 40.0),
        health=2500.0,
        max_health=2500.0,
        fraction_complete=1.0,
        tags=["STRUCTURE", "FACTORY", "LAND", "TECH1"]
    )

    # 1. When 0 engineers exist, should prioritize engineer
    state_no_eng = create_mock_state(tick=10, units=[factory])
    prod_mgr.update(state_no_eng, client)
    cmds = client.buffer.flush()
    assert len(cmds) == 1
    assert cmds[0]["type"] == "build_factory"
    assert cmds[0]["blueprint"] == "url0105"  # Cybran T1 Engineer

    # 2. When engineers exist but 0 scouts, should produce scout
    eng1 = Unit(id=21, blueprint_id="url0105", position=(40.0, 0.0, 40.0), health=200.0, max_health=200.0, tags=["ENGINEER"])
    eng2 = Unit(id=22, blueprint_id="url0105", position=(40.0, 0.0, 40.0), health=200.0, max_health=200.0, tags=["ENGINEER"])
    eng3 = Unit(id=23, blueprint_id="url0105", position=(40.0, 0.0, 40.0), health=200.0, max_health=200.0, tags=["ENGINEER"])

    state_no_scout = create_mock_state(tick=20, units=[factory, eng1, eng2, eng3])
    prod_mgr.update(state_no_scout, client)
    cmds = client.buffer.flush()
    assert len(cmds) == 1
    assert cmds[0]["type"] == "build_factory"
    assert cmds[0]["blueprint"] == "url0101"  # Cybran Land Scout

    # 3. When engineers and scouts exist, should produce combat tanks
    scout = Unit(id=24, blueprint_id="url0101", position=(40.0, 0.0, 40.0), health=40.0, max_health=40.0, tags=["LAND", "SCOUT"])
    state_combat = create_mock_state(tick=30, units=[factory, eng1, eng2, eng3, scout])
    prod_mgr.update(state_combat, client)
    cmds = client.buffer.flush()
    assert len(cmds) == 1
    assert cmds[0]["type"] == "build_factory"
    assert cmds[0]["blueprint"] == "url0107"  # Cybran Mantis T1 Tank


def test_expansion_manager_dispatch():
    config = BotConfig()
    exp_mgr = ExpansionManager(config)
    client = SCFAClient(ipc=SCFAIPC(shm_dir="/tmp/test_shm_exp"), faction=Faction.CYBRAN)

    eng1 = Unit(id=31, blueprint_id="url0105", position=(50.0, 0.0, 50.0), health=200.0, max_health=200.0, tags=["ENGINEER"])
    eng2 = Unit(id=32, blueprint_id="url0105", position=(52.0, 0.0, 52.0), health=200.0, max_health=200.0, tags=["ENGINEER"])

    spot1 = MassSpot(x=60.0, z=60.0, status="free")
    spot2 = MassSpot(x=80.0, z=80.0, status="free")

    state = create_mock_state(tick=10, units=[eng1, eng2], mass_spots=[spot1, spot2])

    exp_mgr.dispatch(state, client, available_engineers=[eng1, eng2], base_pos=(50.0, 0.0, 50.0))
    cmds = client.buffer.flush()

    assert len(cmds) == 2
    assert cmds[0]["type"] == "build_mobile"
    assert cmds[0]["builder"] == 31
    assert cmds[0]["target"] == [60.0, 0.0, 60.0]

    assert cmds[1]["type"] == "build_mobile"
    assert cmds[1]["builder"] == 32
    assert cmds[1]["target"] == [80.0, 0.0, 80.0]


def test_military_manager_rally_and_assault():
    config = BotConfig(min_platoon_size=6)
    mil_mgr = MilitaryManager(config)
    client = SCFAClient(ipc=SCFAIPC(shm_dir="/tmp/test_shm_mil"), faction=Faction.CYBRAN)

    acu = Unit(id=1, blueprint_id="url0001", position=(30.0, 0.0, 30.0), health=12000.0, max_health=12000.0, tags=["COMMANDER"])

    # 1. When platoon size < 6, units gather at rally point
    small_army = [
        Unit(id=100 + i, blueprint_id="url0107", position=(32.0 + i, 0.0, 32.0), health=300.0, max_health=300.0, tags=["LAND", "DIRECTFIRE"])
        for i in range(3)
    ]
    state_small = create_mock_state(tick=10, units=[acu] + small_army)
    mil_mgr.update(state_small, client, base_pos=(30.0, 0.0, 30.0), estimated_enemy_pos=(200.0, 0.0, 200.0))
    cmds = client.buffer.flush()
    assert any(c["type"] == "move" for c in cmds)

    # 2. When platoon size >= 6, units attack-move towards enemy
    full_army = [
        Unit(id=100 + i, blueprint_id="url0107", position=(32.0 + i, 0.0, 32.0), health=300.0, max_health=300.0, tags=["LAND", "DIRECTFIRE"])
        for i in range(7)
    ]
    state_assault = create_mock_state(tick=20, units=[acu] + full_army)
    mil_mgr.update(state_assault, client, base_pos=(30.0, 0.0, 30.0), estimated_enemy_pos=(200.0, 0.0, 200.0))
    cmds = client.buffer.flush()
    assert any(c["type"] == "attack_move" and c["target"] == [200.0, 0.0, 200.0] for c in cmds)

    # 3. Base threat alert: enemy close to base (< 65m) triggers defense attack
    enemy_raider = Unit(id=999, blueprint_id="uel0201", position=(45.0, 0.0, 45.0), health=250.0, max_health=250.0, tags=["LAND", "DIRECTFIRE"])
    state_threat = create_mock_state(tick=30, units=[acu] + full_army, enemies=[enemy_raider])
    mil_mgr.update(state_threat, client, base_pos=(30.0, 0.0, 30.0), estimated_enemy_pos=(200.0, 0.0, 200.0))
    cmds = client.buffer.flush()
    assert any(c["type"] == "attack" and c["target_id"] == 999 for c in cmds)


def test_acu_survival_retreat_and_overcharge():
    config = BotConfig(acu_retreat_health_ratio=0.45, acu_combat_engage_dist=25.0)
    mil_mgr = MilitaryManager(config)
    client = SCFAClient(ipc=SCFAIPC(shm_dir="/tmp/test_shm_acu"), faction=Faction.CYBRAN)

    # Test Retreat: ACU health < 45% (4000 / 12000 = 33%)
    hurt_acu = Unit(id=1, blueprint_id="url0001", position=(70.0, 0.0, 70.0), health=4000.0, max_health=12000.0, tags=["COMMANDER"])
    state_hurt = create_mock_state(tick=10, units=[hurt_acu])
    mil_mgr.update(state_hurt, client, base_pos=(30.0, 0.0, 30.0), estimated_enemy_pos=(200.0, 0.0, 200.0))
    cmds = client.buffer.flush()
    assert any(c["type"] == "move" and c["target"] == [30.0, 0.0, 30.0] for c in cmds)

    # Test Overcharge: Full health ACU, enemy within 20m, energy > 2500
    healthy_acu = Unit(id=1, blueprint_id="url0001", position=(50.0, 0.0, 50.0), health=12000.0, max_health=12000.0, tags=["COMMANDER"])
    nearby_enemy = Unit(id=888, blueprint_id="uel0201", position=(55.0, 0.0, 55.0), health=300.0, max_health=300.0, tags=["LAND"])
    state_oc = create_mock_state(tick=20, energy_stored=3000.0, units=[healthy_acu], enemies=[nearby_enemy])
    mil_mgr.update(state_oc, client, base_pos=(30.0, 0.0, 30.0), estimated_enemy_pos=(200.0, 0.0, 200.0))
    cmds = client.buffer.flush()
    assert any(c["type"] == "overcharge" and c["commander"] == 1 for c in cmds)


def test_rule_based_bot_full_step():
    client = SCFAClient(ipc=SCFAIPC(shm_dir="/tmp/test_shm_full"), faction=Faction.CYBRAN)
    bot = RuleBasedBot(client=client)

    acu = Unit(id=1, blueprint_id="url0001", position=(50.0, 0.0, 50.0), health=12000.0, max_health=12000.0, tags=["COMMANDER"])
    state = create_mock_state(tick=10, units=[acu])

    bot.step(state)
    cmds = client.buffer.flush()
    assert len(cmds) > 0
    # On tick 10, ACU was ordered to start the opening build order (Mex 1)
    assert cmds[0]["type"] == "build_mobile"
