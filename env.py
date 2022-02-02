from multiprocessing import Queue, Process
import numpy as np
from gym import Env
from gym.spaces import Box, Discrete

from stable_baselines3.common.type_aliases import GymObs, GymStepReturn
import python_server.congestion_control_server as cc_server


class CongestionControlEnv(Env):
    def __init__(self,
                 episode_lenght: int = 1000,
                 eps: float = 0.05,
                 num_actions: int = 4,
                 observation_length: int = 1):
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
        # Run server in a different process
        self._server_process: Process
        self._run_server_process()

        self.current_step = 0
        self.num_resets = -1
        self.eps = eps
        self.reset()

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
        return self._state_queue.get()

    def _next_state(self) -> None:
        self.state = self._get_state()

    def _get_reward(self) -> float:
        return 1.0

    def reset(self) -> GymObs:
        self.current_step = 0
        self.num_resets += 1
        self._next_state()
        return self.state

    def step(self, action: np.ndarray) -> GymStepReturn:
        self._action_queue.put(1)
        reward = self._get_reward()
        self._next_state()
        self.current_step += 1
        done = self.current_step >= self.episode_lenght
        return self.state, reward, done, {}

    def render(self, mode: str = "console") -> None:
        pass
