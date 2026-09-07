"""
Unit tests for the SCFA IPC Shared Memory Bridge.
"""

import json
import os
import tempfile
import time
from pathlib import Path

from scfa_env.ipc import SCFAIPCBridge


def test_ipc_handshake():
    with tempfile.TemporaryDirectory() as tmpdir:
        bridge = SCFAIPCBridge(shm_dir=tmpdir)
        bridge.clean()

        # Simulate in-game Lua observation write
        sample_obs = {
            "step": 1,
            "game_time": 10.5,
            "economy": {"mass_stored": 500, "energy_stored": 2500},
            "acu": {"alive": True, "health": 12000, "max_health": 12000, "pos": [100, 20, 150]},
            "counts": {"engineers": 2, "factories_land": 1}
        }
        bridge.obs_file.write_text(json.dumps(sample_obs))
        bridge.obs_ready.write_text("1")

        # Python reads observation
        obs = bridge.wait_for_observation(timeout_sec=1.0)
        assert obs is not None
        assert obs["step"] == 1
        assert obs["economy"]["mass_stored"] == 500
        assert not bridge.obs_ready.exists()  # Flag should be consumed

        # Python sends action
        success = bridge.send_action(action_id=3, target=(120.0, 0.0, 160.0))
        assert success
        assert bridge.act_ready.exists()

        # Verify action file content
        action_data = json.loads(bridge.act_file.read_text())
        assert action_data["action"] == 3
        assert action_data["step"] == 1
        assert action_data["target"] == [120.0, 0.0, 160.0]

        bridge.clean()
        assert not bridge.obs_file.exists()
        assert not bridge.act_file.exists()
