"""
Gymnasium-compatible Environment for Supreme Commander: Forged Alliance.
"""

import time
from typing import Any, Dict, Optional, Tuple

import numpy as np

try:
    import gymnasium as gym
    from gymnasium import spaces
except ImportError:
    # Minimal fallback interface if gymnasium is not installed
    class gym:
        class Env:
            pass

    class spaces:
        class Box:
            def __init__(self, low, high, shape, dtype=np.float32):
                self.low = low
                self.high = high
                self.shape = shape
                self.dtype = dtype

            def sample(self):
                return np.random.uniform(self.low, self.high, size=self.shape).astype(self.dtype)

        class Discrete:
            def __init__(self, n):
                self.n = n

            def sample(self):
                return np.random.randint(0, self.n)

from .game_process import SCFAGameProcess
from .ipc import SCFAIPCBridge


class SCFAEnv(gym.Env):
    metadata = {"render_modes": ["human", "none"]}

    def __init__(
        self,
        map_name: str = "SCMP_009",
        ai_type: str = "medium",
        faction: int = 3,  # 3 = Cybran
        max_steps: int = 600,  # 10 minutes at 1s/step
        headless: bool = True
    ):
        super().__init__()
        self.map_name = map_name
        self.ai_type = ai_type
        self.faction = faction
        self.max_steps = max_steps
        self.headless = headless

        self.ipc = SCFAIPCBridge()
        self.game = SCFAGameProcess(
            map_name=map_name,
            ai_type=ai_type,
            faction=faction,
            headless=headless
        )

        # 18-dimensional continuous observation space
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(18,),
            dtype=np.float32
        )

        # 12 discrete macro actions
        self.action_space = spaces.Discrete(12)

        self.current_step = 0
        self.prev_obs: Optional[Dict[str, Any]] = None

    def _extract_feature_vector(self, raw_obs: Dict[str, Any]) -> np.ndarray:
        econ = raw_obs.get("economy", {})
        acu = raw_obs.get("acu", {})
        counts = raw_obs.get("counts", {})
        threat = raw_obs.get("enemy_threat", {}).get("pos", [0, 0, 0])

        acu_hp = acu.get("health", 0.0)
        acu_max_hp = max(acu.get("max_health", 1.0), 1.0)
        acu_pos = acu.get("pos", [0, 0, 0])

        vec = [
            # Economy features (normalized)
            float(econ.get("mass_stored", 0)) / 1000.0,
            float(econ.get("mass_income", 0)) / 50.0,
            float(econ.get("mass_usage", 0)) / 50.0,
            float(econ.get("energy_stored", 0)) / 5000.0,
            float(econ.get("energy_income", 0)) / 500.0,
            float(econ.get("energy_usage", 0)) / 500.0,

            # ACU features
            1.0 if acu.get("alive", False) else 0.0,
            float(acu_hp) / float(acu_max_hp),
            float(acu_pos[0]) / 512.0,
            float(acu_pos[2]) / 512.0,

            # Unit counts
            float(counts.get("engineers", 0)) / 20.0,
            float(counts.get("factories_land", 0)) / 5.0,
            float(counts.get("factories_air", 0)) / 5.0,
            float(counts.get("combat_land", 0)) / 50.0,
            float(counts.get("combat_air", 0)) / 30.0,
            float(counts.get("energy_prod", 0)) / 20.0,
            float(counts.get("mex", 0)) / 10.0,

            # Threat distance/presence
            1.0 if (threat[0] > 0 or threat[2] > 0) else 0.0
        ]
        return np.array(vec, dtype=np.float32)

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        self.current_step = 0
        self.ipc.clean()

        # Restart game instance
        self.game.start()

        # Wait for first state from the in-game Lua mod
        raw_obs = self.ipc.wait_for_observation(timeout_sec=25.0)
        if raw_obs is None:
            # Fallback zero observation if game launch timed out
            raw_obs = {"economy": {}, "acu": {"alive": True, "health": 12000, "max_health": 12000}}

        self.prev_obs = raw_obs
        obs_vec = self._extract_feature_vector(raw_obs)
        return obs_vec, {"raw_obs": raw_obs}

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        self.current_step += 1

        # 1. Send action to the in-game Lua loop
        self.ipc.send_action(action)

        # 2. Receive new observation
        raw_obs = self.ipc.wait_for_observation(timeout_sec=5.0)
        if raw_obs is None:
            # Game ended or lagged
            terminated = not self.game.is_alive()
            obs_vec = self._extract_feature_vector(self.prev_obs or {})
            return obs_vec, -1.0, terminated, False, {"error": "ipc_timeout"}

        obs_vec = self._extract_feature_vector(raw_obs)

        # 3. Compute reward
        reward = 0.0
        curr_econ = raw_obs.get("economy", {})
        prev_econ = (self.prev_obs or {}).get("economy", {})

        # Reward for positive mass economy scaling
        d_mass_income = float(curr_econ.get("mass_income", 0)) - float(prev_econ.get("mass_income", 0))
        reward += d_mass_income * 2.0

        # Reward for healthy energy
        if curr_econ.get("energy_stored", 0) > 200:
            reward += 0.05

        # Reward for combat unit accumulation
        combat_units = raw_obs.get("counts", {}).get("combat_land", 0)
        reward += combat_units * 0.02

        # Check termination
        acu_alive = raw_obs.get("acu", {}).get("alive", False)
        is_over = raw_obs.get("is_over", False) or not self.game.is_alive()

        terminated = False
        truncated = self.current_step >= self.max_steps

        if not acu_alive:
            reward -= 50.0  # Lost ACU
            terminated = True
        elif is_over:
            reward += 100.0  # Victory
            terminated = True

        self.prev_obs = raw_obs
        return obs_vec, float(reward), terminated, truncated, {"raw_obs": raw_obs}

    def close(self) -> None:
        self.ipc.request_stop()
        time.sleep(0.2)
        self.game.terminate()
        self.ipc.clean()
