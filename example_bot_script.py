"""
Example script demonstrating how to use the SCFA Python API to control a Bot.

This script shows:
1. Connecting to / starting an accelerated SCFA match.
2. Observing game state (economy, units, enemies, mass spots).
3. Issuing orders: building extractors, factories, ordering military units.
"""

import time
from scfa import Faction, GameSession, SCFAClient


def run_simple_bot(client: SCFAClient, max_steps: int = 50):
    print("=== SCFA Bot Script Started ===")

    for step_num in range(1, max_steps + 1):
        # 1. Query full game state snapshot
        state = client.get_state()
        print(f"\n[Step {step_num}] Time: {state.time:.1f}s, Tick: {state.tick}")
        print(f"  Economy: Mass={state.economy.mass.stored:.0f}/{state.economy.mass.capacity:.0f} (+{state.economy.mass.income:.1f}/s), "
              f"Energy={state.economy.energy.stored:.0f}/{state.economy.energy.capacity:.0f} (+{state.economy.energy.income:.1f}/s)")

        acu = state.get_commander()
        if not acu or not acu.is_alive:
            print("  Commander is dead! Match lost.")
            break

        print(f"  ACU: HP={acu.health:.0f}/{acu.max_health:.0f} at {acu.position}")

        # 2. Logic: Build Mass Extractor if nearby free spot exists
        free_mex = state.get_nearest_free_mex(acu.position)
        if free_mex and state.economy.mass.stored > 36:
            print(f"  -> Ordering ACU to build Mass Extractor at ({free_mex.x}, {free_mex.z})")
            client.build(acu, "mex_t1", free_mex.position)

        # 3. Logic: Build Power Generator if energy income is low
        if state.economy.energy.income < 20 and state.economy.mass.stored > 75:
            p_pos = (acu.position[0] + 5, 0.0, acu.position[2] + 5)
            print(f"  -> Ordering ACU to build Power Generator at {p_pos}")
            client.build(acu, "power_t1", p_pos)

        # 4. Logic: Build Land Factory
        factories = state.get_factories()
        if len(factories) == 0 and state.economy.mass.stored > 120:
            f_pos = (acu.position[0] - 8, 0.0, acu.position[2] - 8)
            print(f"  -> Ordering ACU to build Land Factory at {f_pos}")
            client.build(acu, "factory_land_t1", f_pos)

        # 5. Logic: Produce tanks from factory
        for fac in factories:
            print(f"  -> Queueing 2 T1 Tanks in Factory #{fac.id}")
            client.produce(fac, "tank_t1", count=2)

        # 6. Logic: Military attack
        combat_units = state.get_combat_units()
        enemies = state.get_enemy_units()
        print(f"  Units: Engineers={len(state.get_engineers())}, Factories={len(factories)}, Army={len(combat_units)}, Visible Enemies={len(enemies)}")

        if len(combat_units) >= 6:
            if enemies:
                target = enemies[0]
                print(f"  -> Army attacking enemy #{target.id} at {target.position}")
                client.attack(combat_units, target)
            else:
                # Attack towards center or enemy side
                center_target = (state.map_width * 0.75, 0.0, state.map_height * 0.75)
                print(f"  -> Army attack-moving towards {center_target}")
                client.attack_move(combat_units, center_target)

        # 7. Advance simulation by 1 step (10 sim ticks = 1 second)
        client.step()

    print("\n=== SCFA Bot Script Finished ===")


if __name__ == "__main__":
    # To run with a live game session:
    # with GameSession(map_name="SCMP_009", faction=Faction.CYBRAN, enemy_ai="medium", game_speed=10) as client:
    #     run_simple_bot(client)
    print("Example bot script ready. Use with GameSession or standalone SCFAClient.")
