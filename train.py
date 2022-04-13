from stable_baselines3 import A2C
from envs.env import CongestionControlEnv
import wandb
from wandb.integration.sb3 import WandbCallback

config = {
    "policy_type": "MlpPolicy",
    "total_timesteps": 25000
}

run = wandb.init(
    project="mocketsML",
    config=config,
    sync_tensorboard=True,
    # monitor_gym=True,
    save_code=True
)

if __name__ == "__main__":
    model = A2C(config["policy_type"], CongestionControlEnv(
        total_timesteps=config["total_timesteps"]),
        verbose=1,
        tensorboard_log=f"runs/{run.id}")
    model.learn(
        total_timesteps=config["total_timesteps"],
        callback=WandbCallback(
            gradient_save_freq=100,
            model_save_path=f"models/{run.id}",
            verbose=2
        ),
    )
    run.finish()
