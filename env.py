import time
from multiprocessing import Queue, Process
import numpy as np
from gym import Env
from gym.spaces import Box, Discrete

from stable_baselines3.common.type_aliases import GymObs, GymStepReturn
import data_processing_server.congestion_control_server as cc_server


class CongestionControlEnv(Env):
    def __init__(self,
                 episode_lenght: int = 1000,
                 eps: float = 0.05,
                 num_actions: int = 4,
                 observation_length: int = 2):
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

    def _get_state(self):
        self.state = self._state_queue.get()
        print("Received State: ", self.state)
        return self.state

    def _next_observation(self) -> np.array:
        return np.array([self._get_state(), 0])

    def _put_action(self, action):
        print("Performing Action: ", action)
        self._action_queue.put(action)

    def _get_reward(self) -> float:
        return 1.0

    def reset(self) -> GymObs:
        self.current_step = 0
        self.num_resets += 1
        return self._next_observation()

    def step(self, action: np.ndarray) -> GymStepReturn:
        self._put_action(self.state)
        self.current_step += 1
        reward = self._get_reward()
        done = self.current_step >= self.episode_lenght
        return self._next_observation(), reward, done, {}

    def render(self, mode: str = "console") -> None:
        pass
