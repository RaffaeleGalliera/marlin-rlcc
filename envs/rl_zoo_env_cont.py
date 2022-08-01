import time
from multiprocessing import Queue, Process
import numpy as np
import logging
from gym import Env
from gym.spaces import Box, Discrete

from stable_baselines3.common.type_aliases import GymObs, GymStepReturn

import data_processing_server.congestion_control_server as cc_server
from envs.utils import constants
import math
from envs.utils.constants import Parameters, State
import subprocess
import paramiko

logging.basicConfig(level=logging.DEBUG)


def writable_bytes(cwnd: float, inflight_bytes: float) -> float:
    return cwnd - inflight_bytes


def throughput(sent_bytes: float, delta: float) -> float:
    return sent_bytes if delta == 0 else sent_bytes/delta


def ema_throughput(current_ema_throughput: float, current_throughput: float,
                   alpha: float) -> float:
    if current_ema_throughput == 0.0:
        return current_throughput
    else:
        return (1 - alpha) * current_ema_throughput + alpha * current_throughput


def mockets_gradlew_args(mockets_server_ip: str, grpc_port: int, is_testing: bool):
    if is_testing:
        client_type = "runCCTestingClient"
    else:
        client_type = "runCCTrainingClient"

    return ['/code/jmockets/gradlew',
            client_type,
            f"--args=-ip {mockets_server_ip} --grpc-server localhost:{grpc_port}",
            '-p',
            '/code/jmockets']


def mockets_dist_args(mockets_server_ip: str, grpc_port: int,
                               is_testing: bool):
    if is_testing:
        path = f"{constants.DIST_PATH}/testing/examples/bin/examples"
    else:
        path = f"{constants.DIST_PATH}/training/examples/bin/examples"

    return [path,
            '-ip',
            f'{mockets_server_ip}',
            '--grpc-server',
            f'localhost:{grpc_port}']


def _reward_function(instant_throughput, last_rtt,
                     rtt_min, retransmissions):
    eps = 0.005
    b = 1 + last_rtt - rtt_min
    th = math.log((eps + instant_throughput))
    penalties = math.log((1 + retransmissions) * b)
    # b = (1 + math.log(goodput/current_ema_throughput))
    return th - penalties


class CongestionControlEnv(Env):
    def __init__(self,
                 n_timesteps: int = 500000,
                 mocket_server_ip: str = "192.168.1.17",
                 grpc_port: int = 50051,
                 observation_length: int = len(State),
                 max_number_of_steps: int = 70000,
                 is_testing: bool = False):
        """
        :param eps: the epsilon bound for correct value
        :param episode_length: the length of each episode in timesteps
        :param observation_lenght: the lenght of the observations
        """
        self.has_eval_been_launched = False
        self.action_space = Box(low=-1, high=+1, shape=(1,), dtype=np.float32)

        self.observation_space = Box(low=-float("inf"),
                                     high=float("inf"),
                                     shape=(observation_length,))
        # Observation queue where the server will publish
        self._state_queue = Queue()
        # Action queue where the agent will publish the action
        self._action_queue = Queue()

        self.current_step = 0
        self.total_steps = 0
        self.num_resets = 0
        self.episode_return = 0
        self.episode_start_time = 0
        self.episode_time = 0
        self.action_delay = 0
        self.n_timestep = n_timesteps

        self.previous_timestamp = 0
        self.current_statistics = dict((param, 0.0) for param in Parameters)

        self._mockets_server_ip = mocket_server_ip
        self.grpc_port = grpc_port
        self.ssh_traffic_gen = paramiko.SSHClient()
        self.ssh_traffic_gen.set_missing_host_key_policy(
            paramiko.AutoAddPolicy())

        # Run server in a different process
        self._server_process = None
        self._mocket_process = None

        self._max_number_of_steps = max_number_of_steps
        self._is_testing = is_testing

        # self.reset()

    def __del__(self):
        """Book-keeping to release resources"""
        if self._server_process is not None and self._mocket_process is not None:
            while True:
                try:
                    self._mocket_process.wait(1)
                    break
                except subprocess.TimeoutExpired:
                    logging.info("Waiting for Mockets to gently terminate...")

            logging.info("Closing GRPC Server...")
            self._server_process.terminate()

            self._server_process.join()
            self._server_process.close()

            self._action_queue.close()
            self._state_queue.close()

            logging.info("Closing Background traffic gen")
            self.ssh_traffic_gen.close()

    def _run_mockets_client(self, mockets_server_address, grpc_port,
                            mockets_logfile):
        self._mocket_process = subprocess.Popen(mockets_gradlew_args(
            mockets_server_address,
            grpc_port,
            self._is_testing
        ), stdout=mockets_logfile, stderr=subprocess.STDOUT)
        self._mocket_process.daemon = True

    def _run_grpc_server(self, port: int):
        """Run the server process"""
        self._server_process = Process(
            target=cc_server.run,
            args=(self._action_queue,
                  self._state_queue,
                  port), name='marlin_grpc')
        self._server_process.daemon = True
        self._server_process.start()

    def _process_additional_params(self):
        if self.previous_timestamp == 0:
            delta = 0
        else:
            delta = self.current_statistics[Parameters.TIMESTAMP] - self.previous_timestamp

        self.current_statistics[Parameters.THROUGHPUT] = throughput(
            self.current_statistics[Parameters.SENT_BYTES_TIMEFRAME],
            delta  # Throughput B/Sec
        )
        self.current_statistics[Parameters.GOODPUT] = throughput(
            self.current_statistics[Parameters.SENT_GOOD_BYTES_TIMEFRAME],
            delta  # Throughput B/Sec
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
            self.current_statistics[Parameters.UNACK_BYTES]
        )

    def _fetch_param_and_update_stats(self) -> int:
        self.current_statistics = self._state_queue.get()
        self.current_statistics[Parameters.TIMESTAMP] /= 1000
        # Return Timestamp in Seconds
        return self.current_statistics[Parameters.TIMESTAMP]

    def _get_state(self) -> np.array:
        logging.debug("FETCHING STATE..")

        if not self.current_statistics[Parameters.FINISHED]:
            timestamp = self._fetch_param_and_update_stats()
            self._process_additional_params()
            self.previous_timestamp = timestamp

            logging.debug(f"STATE RECEIVED WITH DELAY: "
                         f"{(time.time() - timestamp) * 1000}ms")

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

    def _get_reward(self) -> float:
        reward = _reward_function(
            self.current_statistics[Parameters.THROUGHPUT],
            self.current_statistics[Parameters.LAST_RTT],
            self.current_statistics[Parameters.MIN_RTT],
            self.current_statistics[Parameters.RETRANSMISSIONS]
        )

        self.episode_return += reward

        return reward

    # New CWND by throttle action
    def _cwnd_update_throttle(self, percentage) -> int:
        # New CWND in Bytes
        cwnd = math.ceil(self.current_statistics[Parameters.CURR_WINDOW_SIZE] + percentage * self.current_statistics[Parameters.CURR_WINDOW_SIZE]) * 1000
        if cwnd < 1:
            return 1
        elif cwnd > constants.GRPC_FLOAT_UPPER_LIMIT:
            return constants.GRPC_FLOAT_UPPER_LIMIT
        else:
            return cwnd

    def _has_reached_steps_limits(self):
        return self.current_step == self._max_number_of_steps or self.n_timestep == self.total_steps

    def _run_grpc_and_mockets(self):
        logging.info(self.current_statistics)
        self._run_grpc_server(self.grpc_port)
        with open('mockets.log', "w") as log:
            self._run_mockets_client(self._mockets_server_ip,
                                     self.grpc_port,
                                     mockets_logfile=log)

    def _start_background_traffic(self):
        logging.info("Connecting to sender host for background traffic")
        self.ssh_traffic_gen.connect("192.168.1.40", username="marlin",
                                     password="nomads")

        logging.info("Starting Background traffic")
        ssh_stdin, ssh_tdou, sshstderr = self.ssh_traffic_gen.exec_command(
            "mgen inpuT /home/marlin/Muddasar-MGN/evaluation_generator_100MB.mgen",
            get_pty=True)


    def _cleanup(self):
        # You gotta clean your stuff sometimes
        self.__del__()
        self._state_queue = Queue()
        self._action_queue = Queue()

    def report(self):
        logging.info(f"EPISODE {self.num_resets} COMPLETED")
        logging.info(f"Steps taken in episode: {self.current_step}")
        logging.info(f"Return accumulated: {self.episode_return}")
        logging.info(f"Time taken: {time.time() - self.episode_start_time}")
        logging.info(f"EMA THROUGHPUT: {self.current_statistics[Parameters.EMA_THROUGHPUT]}")
        logging.info(f"Cumulative retransmissions : "
                     f"{self.current_statistics[Parameters.CUMULATIVE_RETRANSMISSIONS]}")
        logging.info(f"SRTT : {self.current_statistics[Parameters.SRTT]}")
        logging.info(f"Current CWND : {self.current_statistics[Parameters.CURR_WINDOW_SIZE]}")

    def reset(self) -> GymObs:
        self.report()

        self.current_statistics = dict((param, 0.0) for param in Parameters)
        self.current_step = 0
        self.num_resets += 1
        self.episode_return = 0
        self.episode_start_time = time.time()
        initial_state = np.array([self.current_statistics[Parameters(x.value)] for x in State])

        return initial_state

    def step(self, action) -> GymStepReturn:
        info = {}
        reward = 0

        self.current_step += 1
        self.total_steps += 1

        if self.current_step == 1:
            self._run_grpc_and_mockets()
            # if self._is_testing:
                # self._start_background_traffic()

        else:
            cwnd_value = self._cwnd_update_throttle(action[0])
            # Handle timeout to let the episode finish asap
            if self._has_reached_steps_limits():
                logging.info("TIMEOUT STEPS EXPIRED")
                info['TimeLimit.truncated'] = True
                self._put_action(constants.CWND_UPPER_LIMIT_BYTES)
            else:
                # CWND value must be in Bytes
                # self._put_action(cwnd_value)
                self._put_action(364380)

            # Action delay in ms
            self.action_delay = (time.time() - self.previous_timestamp) * 1000
            reward = self._get_reward()

            info = {
                'current_statistics': self.current_statistics,
                'action': action[0],
                'reward': reward,
                'action_delay': self.action_delay,
                'start_time': self.episode_start_time
            }

        observation = self._next_observation()

        done = False
        if self.current_statistics[Parameters.FINISHED] or self._has_reached_steps_limits():
            logging.info("Cleaning up, waiting for communication to end...")
            self._cleanup()
            self.episode_time = time.time() - self.episode_start_time
            info['episode_time'] = self.episode_time
            logging.info(f"Done - Stats: {self.current_statistics}")
            done = True

        return observation, reward, done, info

    def render(self, mode: str = "console") -> None:
        pass
