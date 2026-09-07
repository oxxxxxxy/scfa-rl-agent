# Supreme Commander: Forged Alliance — Reinforcement Learning Agent

Autonomous Reinforcement Learning Agent and Gymnasium Environment for **Supreme Commander: Forged Alliance** running on Linux with FA Linux / FAForever, Proton, and Wine.

## Architecture

- **In-game Lua Mod (`mods/PyAgent`)**: Injects into the simulation context (`Sim`) during `BeginSession()`. Collects economy, military units, and threat data, serializes them, and executes high-level RTS macro actions (`IssueBuildMobile`, `IssueMove`, `IssueAttack`, `IssueFactoryRallyPoint`, etc.) while running at **10x accelerated game speed** (`SetGameSpeed(10)`).
- **Zero-Dependency Fast IPC (`scfa_env/ipc.py`)**: Microsecond-latency data exchange via Linux Shared Memory (`/dev/shm`), bridging Wine/Proton and native Python processes without requiring third-party network DLLs.
- **Gymnasium Environment (`scfa_env/environment.py`)**: Standard `gym.Env` interface with an 18-dimensional normalized state vector and 12 discrete macro actions.
- **Neural Policy Network (`models/policy_network.py`)**: Actor-Critic architecture with shared representation trunk, categorical policy head, and state-value estimator.
- **PPO Training Engine (`train.py`)**: Proximal Policy Optimization loop for training against game bots (Sorian / Default AI) in accelerated headless matches.

## Directory Structure

```
scfa-rl-agent/
├── mods/
│   └── PyAgent/             # In-game Lua mod (sim hook, IPC serializer, command dispatcher)
├── scfa_env/
│   ├── environment.py       # SCFAEnv (Gymnasium environment)
│   ├── game_process.py      # Subprocess lifecycle manager for FA Linux
│   └── ipc.py               # Shared memory IPC bridge
├── models/
│   └── policy_network.py    # PyTorch Actor-Critic policy model
├── tests/
│   ├── test_ipc.py          # IPC handshake unit tests
│   └── test_env.py          # Observation vector extraction tests
├── train.py                 # PPO training pipeline
└── requirements.txt
```

## Getting Started

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run automated tests:
   ```bash
   python3 -m pytest tests/
   ```

3. Start training against bots:
   ```bash
   python3 train.py --episodes 50 --max-steps 300
   ```
