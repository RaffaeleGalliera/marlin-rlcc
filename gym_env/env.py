from typing import Optional, Union

import numpy as np
from gym import Env, Space
from gym.spaces import Box, Discrete, MultiBinary, MultiDiscrete

from stable_baselines3.common.type_aliases import GymObs, GymStepReturn


class CongestionControlEnv(Env):
    def __init__(self,
                 episode_lenght: int = 1000,
                 eps: float = 0.05,
                 num_actions: int = 4,
                 observation_length: int = 20):
        """
        :param eps: the epsilon bound for correct value
        :param episode_length: the length of each episode in timesteps
        :param observation_lenght: the lenght of the observations
        """
        self.action_space = Discrete(num_actions)
        self.observation_space = Box(low=-float("inf"),
                                     high=float("inf"),
                                     shape=(observation_length,))
        self.episode_lenght = episode_lenght

        self.current_step = 0
        self.num_resets = -1
        self.eps = eps
        self.reset()

    def reset(self) -> GymObs:
        self.current_step = 0
        self.num_resets += 1
        self._choose_next_state()
        return self.state

    def step(self, action: np.ndarray) -> GymStepReturn:
        reward = self._get_reward()
        self._choose_next_state()
        self.current_step += 1
        done = self.current_step >= self.episode_lenght
        return self.state, reward, done, {}

    def _choose_next_state(self) -> None:
        self.state = self.observation_space.sample()

    def _get_reward(self) -> float:
        return 1.0

    def render(self, mode: str = "console") -> None:
        pass
