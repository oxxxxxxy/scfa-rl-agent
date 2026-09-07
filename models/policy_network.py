"""
Actor-Critic Policy Network for Supreme Commander RTS Decision Making.
"""

from typing import Tuple

try:
    import torch
    import torch.nn as nn
    from torch.distributions import Categorical
except ImportError:
    torch = None
    nn = None
    Categorical = None


class ActorCriticPolicy:
    def __new__(cls, *args, **kwargs):
        if torch is None:
            raise ImportError("PyTorch is required for ActorCriticPolicy. Run: pip install torch")
        return super().__new__(cls)


if torch is not None:
    class ActorCriticPolicy(nn.Module):
        def __init__(self, obs_dim: int = 18, action_dim: int = 12, hidden_dim: int = 128):
            super().__init__()
            self.obs_dim = obs_dim
            self.action_dim = action_dim

            # Feature extractor trunk
            self.trunk = nn.Sequential(
                nn.Linear(obs_dim, hidden_dim),
                nn.LayerNorm(hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, hidden_dim),
                nn.LayerNorm(hidden_dim),
                nn.ReLU()
            )

            # Actor head (policy distribution)
            self.actor = nn.Sequential(
                nn.Linear(hidden_dim, hidden_dim // 2),
                nn.ReLU(),
                nn.Linear(hidden_dim // 2, action_dim)
            )

            # Critic head (state-value estimation)
            self.critic = nn.Sequential(
                nn.Linear(hidden_dim, hidden_dim // 2),
                nn.ReLU(),
                nn.Linear(hidden_dim // 2, 1)
            )

        def forward(self, obs: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
            """Returns (action_logits, value)."""
            features = self.trunk(obs)
            logits = self.actor(features)
            value = self.critic(features)
            return logits, value

        def get_action(self, obs: torch.Tensor) -> Tuple[int, torch.Tensor, torch.Tensor]:
            """Selects an action by sampling from the categorical distribution."""
            logits, value = self.forward(obs)
            dist = Categorical(logits=logits)
            action = dist.sample()
            log_prob = dist.log_prob(action)
            return action.item(), log_prob, value.squeeze(-1)

        def evaluate_actions(
            self,
            obs: torch.Tensor,
            actions: torch.Tensor
        ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
            """Evaluates batch of actions for PPO loss computation."""
            logits, values = self.forward(obs)
            dist = Categorical(logits=logits)
            log_probs = dist.log_prob(actions)
            entropy = dist.entropy()
            return log_probs, values.squeeze(-1), entropy
