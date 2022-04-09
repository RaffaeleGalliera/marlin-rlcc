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
        self.stats_helper = dict((param, 0.0) for param in Parameters)
        self.timestamps = dict((param, 0) for param in Parameters)
        self.counter = dict((param, 0) for param in Parameters)
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
        parameter = self._state_queue.get()
        is_message_valid = mpo.update_statistics(self.current_statistics,
                                                 self.stats_helper,
                                                 self.timestamps,
                                                 parameter['value'],
                                                 parameter['timestamp'],
                                                 self.counter,
                                                 parameter['parameter_type'])

        if not is_message_valid:
            self.older_messages += 1

        return parameter['timestamp']

    def _get_state(self) -> np.array:
        logging.debug("FEEDING STATE..")

        # Wait until CWND > 0 or Sent bytes detected if step 0
        while self.current_step == 0 and not self._check_detected_sent_bytes_and_cwnd():
            _ = self._fetch_param_and_update_stats()

        self.state = np.array([self.current_statistics[Parameters(x.value)]
                               for x in
                               State])

        return self.state

    def _next_observation(self) -> np.array:
        return self._get_state()

    def _put_action(self, action):
        self._action_queue.put(action)

    def _get_reward(self) -> float:
        counter = 0
        while True:
            logging.debug("GETTING NEW PARAMS - WAITING REWARD REFLECTION...")
            timestamp = self._fetch_param_and_update_stats()
            counter += 1
            if self.current_statistics[Parameters.FINISHED] or self._check_cwnd_coherency_and_wait_srtt_ms(timestamp):
                break

        logging.info(f"Reflection passed - "
                     f"Delay: {time.time()* 1000 - timestamp} "
                     f"State Queue: {self._state_queue.qsize()} "
                     f"Action Queue: {self._action_queue.qsize()} "
                     f"Processed messages: {counter}")

        reward = mpo.reward_function(
            self.current_statistics[Parameters.EMA_THROUGHPUT],
            self.current_statistics[Parameters.THROUGHPUT],
            self.current_statistics[Parameters.LAST_RTT],
            self.current_statistics[Parameters.VAR_RTT],
            self.current_statistics[Parameters.MIN_RTT]
        )

        logging.debug(f"REWARD PRODUCED: {reward}")
        self.episode_return += reward

        return reward

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
        logging.info(f"COUNTER SUMMARY: {self.counter}")

    def reset(self) -> GymObs:
        # if self.num_resets >= 0:
        self.report()

        self.current_statistics = dict((param, 0.0) for param in Parameters)
        self.stats_helper = dict((param, 0.0) for param in Parameters)
        self.timestamps = dict((param, 0) for param in Parameters)
        self.counter = dict((param, 0) for param in Parameters)

        self.received_params = 0
        self.current_step = 0
        self.num_resets += 1
        self.older_messages = 0
        self.episode_return = 0
        self.timer = time.time()

        return self._next_observation()

    def step(self, action: np.ndarray) -> GymStepReturn:
        self._put_action(mpo.cwnd_update(self.current_statistics,
                                         self.stats_helper,
                                         action)
                         )
        self.current_step += 1
        self.total_steps += 1
        reward = self._get_reward()
        done = self.current_statistics[Parameters.FINISHED]
        return self._next_observation(), reward, done, {}

    def render(self, mode: str = "console") -> None:
        pass
