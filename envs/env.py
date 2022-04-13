import time
from multiprocessing import Queue, Process
import numpy as np
import logging
from gym import Env
from gym.spaces import Box, Discrete

from stable_baselines3.common.type_aliases import GymObs, GymStepReturn

import data_processing_server.congestion_control_server as cc_server
import constants
import math
from constants import Parameters, State

logging.basicConfig(level=logging.INFO)


def writable_bytes(cwnd: float, inflight_bytes: float, lrtt: float) -> float:
    return cwnd / lrtt * 1000 - inflight_bytes


def throughput(sent_bytes: float, delta: int) -> float:
    return sent_bytes if delta == 0 else sent_bytes/delta


def ema_throughput(current_ema_throughput: float, current_throughput: float,
                   alpha: float) -> float:
    if current_ema_throughput == 0.0:
        return current_throughput
    else:
        return (1 - alpha) * current_ema_throughput + alpha * current_throughput


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
        self.episode_return = 0
        self.timer = 0

        self.previous_timestamp = 0
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

    def _process_missing_params(self):
        if self.previous_timestamp == 0:
            delta = 0
        else:
            delta = self.current_statistics[Parameters.TIMESTAMP] - self.previous_timestamp

        self.current_statistics[Parameters.THROUGHPUT] = throughput(
            self.current_statistics[Parameters.SENT_BYTES_TIMEFRAME],
            delta
        )
        self.current_statistics[Parameters.GOODPUT] = throughput(
            self.current_statistics[Parameters.SENT_GOOD_BYTES_TIMEFRAME],
            delta
        )
        self.current_statistics[Parameters.EMA_THROUGHPUT] = ema_throughput(
            self.current_statistics[Parameters.EMA_THROUGHPUT],
            self.current_statistics[Parameters.THROUGHPUT],
            constants.ALPHA
        )
        self.current_statistics[Parameters.EMA_GOODPUT] = ema_throughput(
            self.current_statistics[Parameters.EMA_GOODPUT],
            self.current_statistics[Parameters.GOODPUT],
            constants.ALPHA
        )
        self.current_statistics[Parameters.WRITABLE_BYTES] = writable_bytes(
            self.current_statistics[Parameters.CURR_WINDOW_SIZE],
            self.current_statistics[Parameters.UNACK_BYTES],
            self.current_statistics[Parameters.LAST_RTT]
        )

    def _fetch_param_and_update_stats(self) -> int:
        self.current_statistics = self._state_queue.get()

        return self.current_statistics[Parameters.TIMESTAMP]

    def _get_state(self) -> np.array:
        logging.debug("FETCHING STATE..")

        if not self.current_statistics[Parameters.FINISHED]:
            timestamp = self._fetch_param_and_update_stats()
            self._process_missing_params()
            self.previous_timestamp = timestamp

            logging.debug(f"STATE RECEIVED WITH DELAY: "
                         f"{time.time() * 1000 - timestamp}ms")

            logging.debug(f"STATE: {self.current_statistics}")
        else:
            logging.debug("SKIPPING STATE FETCH")

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
            self.current_statistics[Parameters.GOODPUT],
            self.current_statistics[Parameters.LAST_RTT],
            self.current_statistics[Parameters.VAR_RTT],
            self.current_statistics[Parameters.MIN_RTT]
        )

        logging.debug(f"REWARD PRODUCED: {reward} after "
                     f"{time.time()*1000 - self.previous_timestamp}ms from "
                     f"received the action")
        self.episode_return += reward

        return reward

    # Mockets Congestion Window % action
    def _cwnd_update(self, index) -> int:
        action = math.ceil(
            self.current_statistics[Parameters.CURR_WINDOW_SIZE] +
            self.current_statistics[Parameters.CURR_WINDOW_SIZE] * constants.ACTIONS[index])

        logging.debug(f"TAKING ACTION {action}")

        # Bound to int64 range
        return action if action < constants.CWND_UPPER_LIMIT else constants.CWND_UPPER_LIMIT

    def report(self):
        logging.info(f"EPISODE {self.num_resets} COMPLETED")
        logging.info(f"Steps taken in episode: {self.current_step}")
        logging.info(f"Total steps until training completion: "
                     f"{self.total_timesteps - self.total_steps}")
        logging.info(f"Return accumulated: {self.episode_return}")
        logging.info(f"Time taken: {time.time() - self.timer}")
        logging.info(f"EMA THROUGHPUT: "
                     f"{self.current_statistics[Parameters.EMA_THROUGHPUT]}")

    def reset(self) -> GymObs:
        # if self.num_resets >= 0:
        self.report()

        self.current_statistics = dict((param, 0.0) for param in Parameters)

        self.current_step = 0
        self.num_resets += 1
        self.episode_return = 0
        self.timer = time.time()

        return self._next_observation()

    def step(self, action: np.ndarray) -> GymStepReturn:
        self._put_action(self._cwnd_update(action))
        reward = self._get_reward()

        self.current_step += 1
        self.total_steps += 1

        done = True if self.current_statistics[Parameters.FINISHED] else False
        return self._next_observation(), reward, done, {}

    def render(self, mode: str = "console") -> None:
        pass
