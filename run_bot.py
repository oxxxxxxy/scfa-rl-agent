#!/usr/bin/env python3
"""
Supreme Commander: Forged Alliance — Rule-Based Bot CLI Runner.

Supports 3 launch scenarios:
1. Automated Bot vs Game AI:
   python3 run_bot.py --mode bot_vs_ai --faction cybran --enemy-ai medium

2. Human vs Bot (1v1 Skirmish takeover):
   python3 run_bot.py --connect --army 2 --speed 0

3. LAN Multiplayer (Human + Friends vs Bot):
   python3 run_bot.py --connect --army 3 --speed 0
"""

import argparse
import sys
import time

from scfa import Faction, GameSession, RuleBasedBot, SCFAClient, SCFAIPC


def parse_args():
    parser = argparse.ArgumentParser(description="Run Rule-Based Bot for Supreme Commander: Forged Alliance")
    parser.add_argument(
        "--mode",
        choices=["bot_vs_ai", "human_vs_bot", "connect"],
        default="bot_vs_ai",
        help="Run mode: 'bot_vs_ai' (spawns game process), 'human_vs_bot', or 'connect' (attaches to running match)"
    )
    parser.add_argument(
        "--connect",
        action="store_true",
        help="Connect to an already running match without launching a new game process"
    )
    parser.add_argument(
        "--army",
        type=int,
        default=None,
        help="Army index to control (default: 1 for bot_vs_ai, 2 for connect/human_vs_bot)"
    )
    parser.add_argument(
        "--faction",
        choices=["cybran", "uef", "aeon", "seraphim"],
        default="cybran",
        help="Faction to play as (default: cybran)"
    )
    parser.add_argument(
        "--enemy-ai",
        default="medium",
        help="In-game AI personality to play against (default: medium, e.g. easy, medium, hard, sorian)"
    )
    parser.add_argument(
        "--map",
        default="SCMP_009",
        help="Scenario map name (default: SCMP_009 - Finns Revenge)"
    )
    parser.add_argument(
        "--speed",
        type=int,
        default=None,
        help="Game simulation speed (default: 10 for accelerated bot_vs_ai, 0 for real-time interactive)"
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Open visible game window instead of running headless"
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=None,
        help="Maximum simulation steps to run before exiting"
    )
    parser.add_argument(
        "--step-delay",
        type=float,
        default=0.0,
        help="Delay in seconds between steps (useful for slowing down real-time view)"
    )
    return parser.parse_args()


def get_faction_enum(name: str) -> Faction:
    f_map = {
        "uef": Faction.UEF,
        "aeon": Faction.AEON,
        "cybran": Faction.CYBRAN,
        "seraphim": Faction.SERAPHIM,
    }
    return f_map.get(name.lower(), Faction.CYBRAN)


def main():
    args = parse_args()
    faction = get_faction_enum(args.faction)

    is_connect_mode = args.connect or args.mode in ("connect", "human_vs_bot")
    army_index = args.army if args.army is not None else (2 if is_connect_mode else 1)
    game_speed = args.speed if args.speed is not None else (0 if is_connect_mode else 10)

    print("=" * 60)
    print("Supreme Commander: Forged Alliance — Rule-Based AI Bot")
    print(f"Mode: {'CONNECT TO EXISTING MATCH' if is_connect_mode else 'SPAWN GAME SESSION'}")
    print(f"Faction: {faction.name} | Army Index: {army_index} | Speed: {game_speed}")
    print("=" * 60)

    if is_connect_mode:
        # Connect mode: attach to existing in-game match (Skirmish or LAN)
        ipc = SCFAIPC()
        print("\nConfiguring in-game bridge via shared memory (/dev/shm)...")
        ipc.write_config(army=army_index, speed=game_speed, disable_ai=True)

        print("Waiting for game session to start and produce first state snapshot...")
        client = SCFAClient(ipc=ipc, faction=faction)
        client.set_army(army_index)
        client.set_speed(game_speed)

        try:
            print("Waiting for match to launch in game (press Ctrl+C to cancel)...")
            while True:
                try:
                    state = client.get_state(timeout_sec=5.0)
                    acu = state.get_commander()
                    hp_str = f"{acu.health:.0f}/{acu.max_health:.0f}" if acu else "N/A"
                    print(f"🎮 Connected to live game! Time: {state.time:.1f}s | ACU HP: {hp_str}")
                    break
                except TimeoutError:
                    print("  ⏳ Waiting for match start in lobby / map loading...")
            bot = RuleBasedBot(client=client)
            bot.run(max_steps=args.max_steps, step_delay=args.step_delay)
        except KeyboardInterrupt:
            print("\nBot interrupted by user. Exiting cleanly.")
    else:
        # Spawn mode: automated game launch
        headless = not args.no_headless
        print(f"\nLaunching game session (Map: {args.map}, Enemy: {args.enemy_ai}, Headless: {headless})...")
        session = GameSession(
            map_name=args.map,
            faction=faction,
            enemy_ai=args.enemy_ai,
            game_speed=game_speed,
            headless=headless
        )

        try:
            with session as client:
                client.configure(army=army_index, speed=game_speed, disable_ai=False)
                bot = RuleBasedBot(client=client)
                bot.run(max_steps=args.max_steps, step_delay=args.step_delay)
        except KeyboardInterrupt:
            print("\nMatch interrupted by user.")
        except Exception as e:
            print(f"\nError running match: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
