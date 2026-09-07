"""
Unit tests for the SCFA Gymnasium Environment feature extraction.
"""

import numpy as np
from scfa_env.environment import SCFAEnv


def test_feature_vector_extraction():
    env = SCFAEnv(headless=True)

    raw_obs = {
        "step": 10,
        "economy": {
            "mass_stored": 800.0,
            "mass_income": 25.0,
            "mass_usage": 20.0,
            "energy_stored": 4000.0,
            "energy_income": 300.0,
            "energy_usage": 250.0
        },
        "acu": {
            "alive": True,
            "health": 10000.0,
            "max_health": 12000.0,
            "pos": [256.0, 10.0, 256.0]
        },
        "counts": {
            "engineers": 4,
            "factories_land": 2,
            "factories_air": 1,
            "combat_land": 15,
            "combat_air": 5,
            "energy_prod": 6,
            "mex": 4
        },
        "enemy_threat": {
            "pos": [400.0, 0.0, 450.0]
        }
    }

    vec = env._extract_feature_vector(raw_obs)
    assert isinstance(vec, np.ndarray)
    assert vec.shape == (18,)
    assert vec.dtype == np.float32

    # Verify normalization bounds
    assert 0.0 <= vec[0] <= 1.0  # Mass stored ratio
    assert vec[6] == 1.0          # ACU alive
    assert 0.8 < vec[7] < 0.9     # ACU HP ratio ~ 10000/12000
    assert vec[8] == 0.5          # X pos 256/512
    assert vec[9] == 0.5          # Z pos 256/512
    assert vec[17] == 1.0         # Threat detected
