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
import math
from constants import Parameters, State

logging.basicConfig(level=logging.INFO)


def _delta_timestamp_micro(timestamp_2, timestamp_1):
    return (timestamp_2 - timestamp_1) * 1000


class CongestionControlEnv(Env):
    def __init__(self,
                 total_timesteps,
                 num_actions: int = len(constants.ACTIONS),
                 observation_length: int = len(State)):
        """
        :param eps: the epsilon bound for correct value
        :param episode_length: the length of each episode in timesteps
        :param observation_lenght: the lenght of the observations
        """
        self.action_space = Discrete(num_actions)
        self.observation_space = Box(low=-float("inf"),
                                     high=float("inf"),
                                     shape=(observation_length,))
        # Observation queue where the server will publish
        self._state_queue = Queue()
        # Action queue where the agent will publish the action
        self._action_queue = Queue()

        self.current_step = 0
        self.total_steps = 0
        self.num_resets = -1
        self.total_timesteps = total_timesteps
        self.older_messages = 0
        self.episode_return = 0
        self.timer = 0

        self.received_params = 0

        self.current_statistics = dict((param, 0.0) for param in Parameters)
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

    def _check_cwnd_coherency_and_wait_srtt_ms(self, timestamp):
        return self.current_statistics[Parameters.CURR_WINDOW_SIZE] == self.stats_helper[Parameters.CURR_WINDOW_SIZE] \
               and _delta_timestamp_micro(timestamp, self.timestamps[Parameters.CURR_WINDOW_SIZE]) > self.current_statistics[Parameters.SRTT]

    def _check_detected_sent_bytes_and_cwnd(self):
        return (self.current_statistics[Parameters.SENT_BYTES] and
                self.current_statistics[Parameters.CURR_WINDOW_SIZE]) == constants.STARTING_WINDOW_SIZE

    def _fetch_param_and_update_stats(self) -> int:
        self.current_statistics = self._state_queue.get()
        logging.info(f"STATE: {self.current_statistics}")

        return self.current_statistics[Parameters.TIMESTAMP]

    def _get_state(self) -> np.array:
        logging.info("FEEDING STATE..")

        timestamp = self._fetch_param_and_update_stats()

        self.state = np.array([self.current_statistics[Parameters(x.value)]
                               for x in
                               State])

        return self.state

    def _next_observation(self) -> np.array:
        return self._get_state()

    def _put_action(self, action):
        self._action_queue.put(action)

    def _reward_function(self, current_ema_throughput, goodput, rtt, rtt_ema,
                         rtt_min):
        assert current_ema_throughput > 0.0, f"Throughput greater than 0 expected, got: {current_ema_throughput}"
        assert goodput >= 0.0, f"Goodput greater than 0 expected, got: {goodput}"

        return math.log(goodput / current_ema_throughput)

    def _get_reward(self) -> float:
        reward = self._reward_function(
            self.current_statistics[Parameters.EMA_THROUGHPUT],
            self.current_statistics[Parameters.THROUGHPUT],
            self.current_statistics[Parameters.LAST_RTT],
            self.current_statistics[Parameters.VAR_RTT],
            self.current_statistics[Parameters.MIN_RTT]
        )

        logging.info(f"REWARD PRODUCED: {reward}")
        self.episode_return += reward

        return reward

    # Mockets Congestion Window % action
    def _cwnd_update(self, index) -> int:
        action = math.ceil(
            self.current_statistics[Parameters.CURR_WINDOW_SIZE] +
            self.current_statistics[Parameters.CURR_WINDOW_SIZE] * constants.ACTIONS[index])

        logging.info(f"TAKING ACTION {action}")
        return action

    def report(self):
        logging.info(f"EPISODE {self.num_resets} COMPLETED")
        logging.info(f"Steps taken in episode: {self.current_step}")
        logging.info(f"Total steps until training completion: "
                     f"{self.total_timesteps - self.total_steps}")
        logging.info(f"Old messages detected in episode: {self.older_messages}")
        logging.info(f"Return accumulated: {self.episode_return}")
        logging.info(f"Time taken: {time.time() - self.timer}")
        logging.info(f"EMA THROUGHPUT: "
                     f"{self.current_statistics[Parameters.EMA_THROUGHPUT]}")

    def reset(self) -> GymObs:
        # if self.num_resets >= 0:
        self.report()

        self.current_statistics = dict((param, 0.0) for param in Parameters)

        self.received_params = 0
        self.current_step = 0
        self.num_resets += 1
        self.older_messages = 0
        self.episode_return = 0
        self.timer = time.time()

        return self._next_observation()

    def step(self, action: np.ndarray) -> GymStepReturn:
        self._put_action(self._cwnd_update(action))
        self.current_step += 1
        self.total_steps += 1
        reward = self._get_reward()
        done = self.current_statistics[Parameters.FINISHED]
        return self._next_observation(), reward, done, {}

    def render(self, mode: str = "console") -> None:
        pass
