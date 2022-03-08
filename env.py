import time
from multiprocessing import Queue, Process
import numpy as np
import logging
from gym import Env
from gym.spaces import Box, Discrete

from stable_baselines3.common.type_aliases import GymObs, GymStepReturn

import data_processing_server.congestion_control_server as cc_server
import mockets_parameters_operations as mpo
import constants

logging.basicConfig(level=logging.DEBUG)


class CongestionControlEnv(Env):
    def __init__(self,
                 episode_lenght: int = 1000,
                 eps: float = 0.05,
                 num_actions: int = 6,
                 observation_length: int = 9):
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

        # Observation queue where the server will publish
        self._state_queue = Queue(maxsize=1)
        # Action queue where the agent will publish the action
        self._action_queue = Queue(maxsize=1)

        self.current_step = 0
        self.num_resets = -1
        self.eps = eps
        # Run server in a different process
        self._server_process: Process
        self._run_server_process()

        # self.reset()

    def __del__(self):
        """Book-keeping to release resources"""
        self._server_process.terminate()
        self._state_queue.close()
        self._action_queue.close()

    def _run_server_process(self):
        """Run the server process"""
        self._server_process = Process(
            target=cc_server.run,
            args=(self._action_queue,
                  self._state_queue))
        self._server_process.daemon = True
        self._server_process.start()

    def _get_state(self) -> np.array:
        parameters = self._state_queue.get()
        mpo.compute_statistics(
                parameters[0],
                parameters[1],
                parameters[2],
                parameters[3],
                parameters[4],
                parameters[5],
                parameters[6],
                parameters[7],
                parameters[8]
            )

        self.state = np.array([mpo.current_statistics[x] for x in constants.STATE])

        return self.state

    def _next_observation(self) -> np.array:
        return self._get_state()

    def _put_action(self, action):
        self._action_queue.put(action)

    def _get_reward(self) -> float:
        return mpo.current_statistics['throughput']

    def reset(self) -> GymObs:
        self.current_step = 0
        self.num_resets += 1
        return self._next_observation()

    def step(self, action: np.ndarray) -> GymStepReturn:
        self._put_action(mpo.cwnd_update(action))
        self.current_step += 1
        reward = self._get_reward()
        done = self.current_step >= self.episode_lenght
        return self._next_observation(), reward, done, {}

    def render(self, mode: str = "console") -> None:
        pass
