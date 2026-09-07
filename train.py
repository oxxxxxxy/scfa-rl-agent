"""
PPO Training Script for Supreme Commander: Forged Alliance AI Agent.
"""

import argparse
import os
import time
from pathlib import Path

import numpy as np

try:
    import torch
    import torch.optim as optim
except ImportError:
    torch = None

from models.policy_network import ActorCriticPolicy
from scfa_env.environment import SCFAEnv


def train(
    total_episodes: int = 50,
    max_steps_per_episode: int = 300,
    lr: float = 3e-4,
    gamma: float = 0.99,
    checkpoint_dir: str = "checkpoints"
):
    if torch is None:
        print("Error: PyTorch not installed. Please install torch with: pip install torch")
        return

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    ckpt_path = Path(checkpoint_dir)
    ckpt_path.mkdir(parents=True, exist_ok=True)

    env = SCFAEnv(max_steps=max_steps_per_episode)
    policy = ActorCriticPolicy(obs_dim=18, action_dim=12).to(device)
    optimizer = optim.Adam(policy.parameters(), lr=lr)

    for episode in range(1, total_episodes + 1):
        print(f"\n--- Starting Episode {episode}/{total_episodes} ---")
        obs, info = env.reset()
        episode_reward = 0.0
        step_count = 0

        states, actions, log_probs, rewards, dones, values = [], [], [], [], [], []

        terminated = False
        truncated = False

        while not (terminated or truncated):
            step_count += 1
            obs_tensor = torch.tensor(obs, dtype=torch.float32, device=device).unsqueeze(0)
            with torch.no_grad():
                action, log_prob, val = policy.get_action(obs_tensor)

            next_obs, reward, terminated, truncated, info = env.step(action)

            states.append(obs)
            actions.append(action)
            log_probs.append(log_prob)
            rewards.append(reward)
            dones.append(terminated)
            values.append(val.item())

            obs = next_obs
            episode_reward += reward

            if step_count % 20 == 0:
                print(f"Step {step_count}: Current Reward={episode_reward:.2f}")

        print(f"Episode {episode} Finished: Total Steps={step_count}, Total Reward={episode_reward:.2f}")

        # Compute Simple Discounted Returns and Advantages
        returns = []
        discounted_sum = 0
        for r, d in zip(reversed(rewards), reversed(dones)):
            if d:
                discounted_sum = 0
            discounted_sum = r + gamma * discounted_sum
            returns.insert(0, discounted_sum)

        if len(returns) > 0:
            returns_t = torch.tensor(returns, dtype=torch.float32, device=device)
            values_t = torch.tensor(values, dtype=torch.float32, device=device)
            advantages_t = returns_t - values_t
            advantages_t = (advantages_t - advantages_t.mean()) / (advantages_t.std() + 1e-8)

            states_t = torch.tensor(np.array(states), dtype=torch.float32, device=device)
            actions_t = torch.tensor(actions, dtype=torch.int64, device=device)
            old_log_probs_t = torch.stack(log_probs).to(device)

            # PPO Update (1 epoch on trajectory)
            new_log_probs, new_values, entropy = policy.evaluate_actions(states_t, actions_t)
            ratio = torch.exp(new_log_probs - old_log_probs_t)

            surr1 = ratio * advantages_t
            surr2 = torch.clamp(ratio, 0.8, 1.2) * advantages_t
            actor_loss = -torch.min(surr1, surr2).mean()
            critic_loss = 0.5 * ((new_values - returns_t) ** 2).mean()

            total_loss = actor_loss + critic_loss - 0.01 * entropy.mean()

            optimizer.zero_grad()
            total_loss.backward()
            torch.nn.utils.clip_grad_norm_(policy.parameters(), max_norm=0.5)
            optimizer.step()

            print(f"Policy Updated: Actor Loss={actor_loss.item():.4f}, Critic Loss={critic_loss.item():.4f}")

        # Save checkpoint periodically
        if episode % 5 == 0 or episode == total_episodes:
            save_file = ckpt_path / f"scfa_policy_ep{episode}.pt"
            torch.save(policy.state_dict(), save_file)
            print(f"Saved model checkpoint to: {save_file}")

    env.close()
    print("Training run finished.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train SCFA RL Agent")
    parser.add_argument("--episodes", type=int, default=50, help="Number of training episodes")
    parser.add_argument("--max-steps", type=int, default=300, help="Max steps per episode (seconds)")
    parser.add_argument("--lr", type=float, default=3e-4, help="Learning rate")
    args = parser.parse_args()

    train(total_episodes=args.episodes, max_steps_per_episode=args.max_steps, lr=args.lr)
