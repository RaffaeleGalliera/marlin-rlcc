from stable_baselines3 import DQN, A2C
from stable_baselines3.common.cmd_util import make_vec_env
from env import CongestionControlEnv

if __name__ == "__main__":
    A2C('MlpPolicy',
        CongestionControlEnv(),
        verbose=1,
        tensorboard_log="./a2c_test/").learn(total_timesteps=5000,
                                             tb_log_name='first_run')

