import queue
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
from constants import Parameters

logging.basicConfig(level=logging.DEBUG)


class CongestionControlEnv(Env):
    def __init__(self,
                 episode_lenght: int = 1000,
                 eps: float = 0.05,
                 num_actions: int = len(constants.ACTIONS),
                 observation_length: int = len(Parameters)):
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
        logging.info("FEEDING STATE..")
        if self.current_step == 0:
            while True:
                logging.info("WARMUP - WAITING FIRST SENT..")
                parameter = self._state_queue.get()
                mpo.update_statistics(parameter['value'],
                                      parameter['timestamp'],
                                      parameter['parameter_type'])
                if mpo.current_statistics[Parameters.SENT_BYTES] > 0:
                    break
        self.state = np.array(
            [mpo.current_statistics[x] for x in Parameters])

        return self.state

    def _next_observation(self) -> np.array:
        return self._get_state()

    def _put_action(self, action):
        self._action_queue.put(action)

    def _get_reward(self) -> float:
        # TODO: When should allow to proceed with the next action?
        while True:
            logging.info("GETTING NEW PARAMS - WAITING REWARD REFLECTION...")
            parameter = self._state_queue.get()
            mpo.update_statistics(parameter['value'],
                                  parameter['timestamp'],
                                  parameter['parameter_type'])

            logging.debug(f"CURRENT STEP {self.current_step}")
            logging.debug(f"CWND BYTES {mpo.current_statistics[Parameters.CURR_WINDOW_SIZE]}")
            logging.debug(f"SET CWND BYTES"
                          f" {mpo.prev_stats_helper[Parameters.CURR_WINDOW_SIZE]}")
            if mpo.current_statistics[Parameters.CURR_WINDOW_SIZE] == mpo.prev_stats_helper[
                Parameters.CURR_WINDOW_SIZE] or mpo.current_statistics[
                Parameters.FINISHED]:
                break

        reward = mpo.reward_function(mpo.current_statistics[Parameters.EMA_THROUGHPUT],
                                     mpo.current_statistics[Parameters.THROUGHPUT],
                                     mpo.current_statistics[Parameters.LAST_RTT],
                                     mpo.current_statistics[Parameters.VAR_RTT],
                                     mpo.current_statistics[Parameters.MIN_RTT])

        logging.info(f"REWARD PRODUCED: {reward}")

        return reward

    def reset(self) -> GymObs:
        if self.num_resets >= 0:
            logging.info(f"COMPLETED EPISODE {self.num_resets} - RESETTING...")
            mpo.current_statistics = dict((param, 0.0) for param in Parameters)
            mpo.prev_stats_helper = dict((param, 0.0) for param in Parameters)
            mpo.timestamps = dict((param, 0) for param in Parameters)

        self.current_step = 0
        self.num_resets += 1

        return self._next_observation()

    def step(self, action: np.ndarray) -> GymStepReturn:
        self._put_action(mpo.cwnd_update(action))
        self.current_step += 1
        reward = self._get_reward()
        done = mpo.current_statistics[Parameters.FINISHED]
        return self._next_observation(), reward, done, {}

    def render(self, mode: str = "console") -> None:
        pass
