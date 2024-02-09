import time
from multiprocessing import Queue, Process
import queue
import os
import numpy as np
import logging
from gym import Env
from gym.spaces import Box
from stable_baselines3.common.type_aliases import GymObs, GymStepReturn

import grpc_server.congestion_control_server as cc_server
from envs.utils import constants
import math
from envs.utils.constants import Parameters, State,Statistic

import pprint
import docker
import netifaces as ni
import rpyc
from statistics import fmean, stdev

logging.basicConfig(level=logging.INFO)


def writable_bytes(cwnd: float, inflight_bytes: float) -> float:
    return cwnd - inflight_bytes


def throughput(sent_bytes: float, delta: float) -> float:
    return sent_bytes if delta == 0 else sent_bytes/delta


def exponential_moving_average(current_ema: float, value: float,
                               alpha=constants.ALPHA) -> float:
    if current_ema == 0.0:
        return value
    else:
        return (1 - alpha) * current_ema + alpha * value


def _state_parameters_intersection():
    parameters_values = set([parameter.value for parameter in Parameters])
    state_values = set([state_parameter.value for state_parameter in State])

    return parameters_values & state_values


def eval_or_train(is_testing):
    return "Eval" if is_testing else "Training"


class CongestionControlEnv(Env):
    def __init__(
            self,
            n_timesteps: int = 500000,
            mockets_server_ip: str = "10.0.2.1",
            grpc_port: int = 50051,
            mininet_port: int = 18861,
            observation_length: int = len(State) * len(Statistic),
            is_testing: bool = False,
            max_duration: int = 80,
            max_time_steps_per_episode: int = 200,
            timestamp_interval_ms: int = 0,
            bandwidth_start = 1.0,
            delay_start = 100,
            loss_start = 0,
            bandwidth_var = 0.5,
            delay_var = 10,
            loss_var = 0,
            variation_range_start: int = 1,
            variation_range_end: int = 20,
            variation_interval_test = 10,
            kbytes_testing = 500,
            random_seed = 1
    ):
        """
        :param eps: the epsilon bound for correct value
        :param episode_length: the length of each episode in timesteps
        :param observation_lenght: the lenght of the observations
        """
        self.current_traffic_patterns = None
        self.action_space = Box(low=-1, high=+1, shape=(1,), dtype=np.float32)
        self.observation_space = Box(low=-float("inf"), high=float("inf"), shape=(observation_length, ))

        np.random.seed(random_seed)
        self.current_step = 0
        self.total_steps = 0
        self.num_resets = 0
        self.episode_return = 0
        self.episode_start_time = 0
        self.episode_time = 0
        self.action_delay = 0
        self.current_bandwidth = 0
        self.current_delay = 0
        self.current_loss = 0
        self.bandwidth_start = bandwidth_start
        self.delay_start = delay_start
        self.loss_start = loss_start
        self.n_timestep = n_timesteps
        self.variation_range_start = variation_range_start
        self.variation_range_end = variation_range_end
        self._is_testing = is_testing
        self.variation_interval_test = variation_interval_test

        self.kbytes_testing = kbytes_testing
        self.previous_timestamp = 0
        self.timestamp_interval_ms = timestamp_interval_ms
        self.mockets_raw_observations = dict((param, 0.0) for param in Parameters)
        self.processed_observations_history = dict((param, [0.0]) for param in State)

        self.state_statistics = dict((stats, dict((stat, 0.0) for stat in Statistic)) for stats in State)
        self.last_state = dict((param, 0.0) for param in State)
        self.acked_bytes = None
        self._mockets_receiver_ip = mockets_server_ip

        self.grpc_port = grpc_port

        # Bind to Docker Client
        self.docker_client = docker.from_env()
        # Get containers
        self.mockets_sender = self.docker_client.containers.get("mn.lh1")
        self.mockets_receiver = self.docker_client.containers.get("mn.rh1")
        self.bg_sender = self.docker_client.containers.get("mn.lh2")
        self.bg_receiver = self.docker_client.containers.get("mn.rh2")
        self.host_address = ni.ifaddresses('docker0')[ni.AF_INET][0]['addr']
        self.mininet_connection = rpyc.connect(self.host_address, mininet_port)
        self.timed_link_update = rpyc.async_(self.mininet_connection.root.timed_link_update)
        self.current_mice_flows_kbs = None
        # Prevent zombie Mockets/Mgen processes running on the container
        self.cleanup_containers()

        # Run server in a different process
        self._server_process = None
        # Observation queue where the server will publish
        self._state_queue = None
        # Action queue where the agent will publish the action
        self._action_queue = None

        self.parameter_fetch_error = False
        self._max_duration = max_duration
        self.max_time_steps_per_episode = 500 if self._is_testing else max_time_steps_per_episode

        #Parameters for random variations link characteristics, bandwidth and delay at the moment

        self.variation_interval = None
        self.bandwidth_var = bandwidth_var
        self.delay_var = delay_var
        self.loss_var = loss_var
        self.variation_pending = None

        self._traffic_timer = None
        self.episode_training_script = None

        self.target_episode = 0
        self.effective_episode = 0
        self.last_step_timestamp = None


    def __del__(self):
        """Book-keeping to release resources"""
        if self._server_process is not None:
            self.cleanup_containers()

            logging.info("Closing GRPC Server...")
            self._server_process.terminate()
            self._server_process.join()
            self._server_process.close()

            self._action_queue.close()
            self._state_queue.close()

            self._server_process = None

    def cleanup_containers(self):
        self.cleanup_mockets()

    def cleanup_mockets(self):
        shutdown_mockets = ['sh', '-c', "ps -ef | grep 'mockets' | grep -v grep | awk '{print $2}' | xargs -r kill -9"]

        logging.info(f"Closing process for {eval_or_train(self._is_testing)}")

        logging.info("Closing Mockets Receiver connection")
        self.mockets_receiver.exec_run(shutdown_mockets)

        logging.info("Closing Mockets Sender connection")
        self.mockets_sender.exec_run(shutdown_mockets)


    def _run_mockets_sender(self, mockets_receiver_address, grpc_port,
                            mockets_logfile):
        logging.info("Launching Mockets Sender...")
        mod = 'client_training' if self._is_testing else 'client_test'
        cmd = f"./bin/driver -m {mod} " \
              f"-address {mockets_receiver_address} " \
              f"{f'-congestionUpdate {self.timestamp_interval_ms}' if self.timestamp_interval_ms > 0 else ''} " \
              f"-marlinServer {self.host_address}:{grpc_port} " \
              f"{f'-episodeBytes {self.kbytes_testing * 1000}' if self._is_testing > 0 else ''}"
        return self.mockets_sender.exec_run(cmd, stream=True)


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
            delta = self.mockets_raw_observations[Parameters.TIMESTAMP] - self.previous_timestamp

        self.processed_observations_history[State.THROUGHPUT].append(throughput(
            self.mockets_raw_observations[Parameters.SENT_BYTES_TIMEFRAME],
            delta  # Throughput KB/Sec
        ))
        self.processed_observations_history[State.GOODPUT].append(throughput(
            self.mockets_raw_observations[Parameters.ACKED_BYTES_TIMEFRAME],
            delta  # Throughput KB/Sec
        ))

        # Every packet is 1KB so every KB in timeframe sent is also a packet
        # sent
        self.processed_observations_history[State.PACKETS_TRANSMITTED].append(
            math.ceil(self.mockets_raw_observations[Parameters.SENT_BYTES_TIMEFRAME]/constants.PACKET_SIZE_KB)
        )

        # Gather statistics from the observation history, dictionaries from
        # observation history share the same first level key of state statistics
        for key, value in self.processed_observations_history.items():
            # Skip RTT Fetch if communication is finished and value was not
            # computed
            self.last_state[key] = value[-1]
            self.state_statistics[key][Statistic.LAST] = value[-1]
            self.state_statistics[key][Statistic.EMA] = \
                exponential_moving_average(self.state_statistics[key][
                                               Statistic.EMA], value[-1])
            self.state_statistics[key][Statistic.MIN] = min(value[1:]) if len(value) > 2 else value[-1]
            self.state_statistics[key][Statistic.MAX] = max(value[1:]) if len(value) > 2 else value[-1]
            self.state_statistics[key][Statistic.MEAN] = fmean(value[1:]) if len(value) > 2 else value[-1]
            self.state_statistics[key][Statistic.STD] = stdev(value[1:]) if len(value) > 2 else value[-1]
            self.state_statistics[key][Statistic.DIFF] = value[-1] - value[-2] if len(value) > 2 else value[-1]

    def _fetch_param_and_update_stats(self) -> int:
        while True:
            try:
                obs = self._state_queue.get(timeout=30)
            except queue.Empty as error:
                logging.info(f"Parameter Fetch: Timeout occurred")
                logging.info("Restarting Service!!")
                self.parameter_fetch_error = True
                self.current_step = self.max_time_steps_per_episode
                self._cleanup()
                self._start_mockets_processes()
            else:
                break

        self.mockets_raw_observations = obs
        self.mockets_raw_observations[Parameters.TIMESTAMP] /= constants.UNIT_FACTOR

        for value in _state_parameters_intersection():
            self.processed_observations_history[State(value)].append(self.mockets_raw_observations[Parameters(value)])

        # Return Timestamp in Seconds
        return self.mockets_raw_observations[Parameters.TIMESTAMP]

    def _is_finished(self):
        return self.mockets_raw_observations[Parameters.FINISHED] or (self._is_testing and self.acked_bytes >= self.kbytes_testing)

    def _get_state(self) -> np.array:
        logging.debug("FETCHING STATE..")

        if not self._is_finished():
            timestamp = self._fetch_param_and_update_stats()
            self._process_additional_params()
            self.acked_bytes += self.state_statistics[State.ACKED_BYTES_TIMEFRAME][Statistic.LAST]

            self.previous_timestamp = timestamp

            logging.debug(f"STATE: {self.state_statistics}")
        else:
            logging.debug("SKIPPING STATE FETCH")

        return np.array([self.state_statistics[State(param.value)][Statistic(
            stat.value)] for param in State for stat in Statistic])

    def _next_state(self) -> np.array:
        return self._get_state()

    def _put_action(self, action):
        self._action_queue.put(action)

    def _get_reward(self) -> float:
        reward = self.reward()
        self.episode_return += reward

        return reward

    # New CWND by throttle action return the amount of BYTES the CWND can be set
    def _cwnd_update_throttle(self, percentage) -> int:
        # New CWND in Bytes
        current_cwnd = self.state_statistics[State.CURR_WINDOW_SIZE][Statistic.LAST]
        cwnd = math.ceil((current_cwnd + percentage * current_cwnd) * constants.UNIT_FACTOR)

        if cwnd < constants.PACKET_SIZE_KB * constants.UNIT_FACTOR:
            return math.ceil(constants.PACKET_SIZE_KB * constants.UNIT_FACTOR)
        elif cwnd > constants.CWND_UPPER_LIMIT_BYTES:
            return constants.CWND_UPPER_LIMIT_BYTES
        else:
            return cwnd

    def _run_mockets_ep_client(self):
        # Add logging
        logs = self._run_mockets_sender(self._mockets_receiver_ip,
                                        self.grpc_port,
                                        None)

        for line in logs.output:
            line = line.decode('utf-8')
            logging.debug(line)

            tokens = line.split(':')
            if len(tokens) == 3 and tokens[1] == "READY":
                logging.info(f"Client Connected!")
                break

    def _run_mockets_receiver(self):
        logging.info("Launching Mockets Receiver...")
        logs = self.mockets_receiver.exec_run(
            './bin/driver -m server '
            f'-address {self._mockets_receiver_ip}', stream=True
        )
        for line in logs.output:
            line = line.decode('utf-8')
            logging.debug(line)

            tokens = line.split(':')
            if len(tokens) == 3 and tokens[1] == "READY":
                logging.info(f"Server ready to accept connections!")
                break

    def _init_background_traffic_timers(self):
        instant = time.time()
        self._traffic_timer = instant
        self.last_step_timestamp = instant

    def _cleanup(self):
        # You gotta clean your stuff sometimes
        self.__del__()

    def _start_mockets_processes(self, reset_time=True):
        logging.info("-------------------------------------")
        logging.info(f"STARTED EPISODE {self.num_resets} {eval_or_train(self._is_testing)}")
        self._state_queue = Queue()
        self._action_queue = Queue()

        self._run_grpc_server(self.grpc_port)
        self._run_mockets_receiver()
        self._run_mockets_ep_client()

        logging.info(f"Current variation at {self.variation_interval}s")
        logging.info("All commands executed. Episode started!")

    def report(self):
        time_taken = time.time() - self.episode_start_time
        logging.info(f"EPISODE {self.num_resets} {eval_or_train(self._is_testing)} COMPLETED")
        logging.info(f"Stats: {pprint.pformat(self.state_statistics)}")
        logging.info(f"Steps taken during episode: {self.current_step}")
        logging.info(f"Return accumulated: {self.episode_return}")
        logging.info(f"Acked bytes since beginning: {self.acked_bytes}")
        logging.info(f"Time taken: {time_taken}")
        logging.info("-------------------------------------")

        if self._is_testing:
            logging.info("Saving Evaluation Time")
            with open(f"logs/evaluation_time.log",
                      "w+") as log:
                log.write(str(time_taken))

    def reset(self) -> GymObs:
        self.report()
        self._cleanup()

        self.mockets_raw_observations = dict((param, 0.0) for param in Parameters)
        self.processed_observations_history = dict((param, [0.0]) for param in State)
        self.state_statistics = dict((stats, dict((stat, 0.0) for stat in Statistic)) for stats in State)
        self.last_state = dict((param, 0.0) for param in State)

        self.parameter_fetch_error = False

        self.current_step = 0
        self.num_resets += 1
        self.episode_return = 0
        self.target_episode = 0
        self.effective_episode = 0

        self.current_bandwidth = self.bandwidth_start
        self.current_delay = self.delay_start
        self.current_loss = self.loss_start
        self.mininet_connection.root.manual_link_update(
            bandwidth=self.current_bandwidth,
            delay=f"{self.current_delay}ms",
            loss=self.current_loss
        )
        self.variation_interval = self.variation_interval_test

        initial_state = np.array(
            [
                self.state_statistics[State(param.value)][Statistic(stat.value)]
                for param in State for stat in Statistic
            ]
        )
        self.acked_bytes = 0
        self.current_mice_flows_kbs = self.bandwidth_start * .08
        self.current_traffic_patterns = [
            self.bandwidth_start * 125  * .4,
            self.bandwidth_start * 125  * .8,
            self.bandwidth_start * 125  * .4,
            self.bandwidth_start * 125  * .208
        ]
        logging.info("Traffic patterns: " + str(self.current_traffic_patterns))

        return initial_state

    def reward(self):
        elapsed_time_in_period = float(time.time() - self._traffic_timer) % 8
        current_bandwidth_kbs = self.current_bandwidth * 125
        target_goodput = current_bandwidth_kbs - self.current_mice_flows_kbs
        time_since_last = time.time() - self.last_step_timestamp

        if 0 <= elapsed_time_in_period <= 2:
            target_goodput = target_goodput - self.current_traffic_patterns[0]
        elif 2 < elapsed_time_in_period <= 4:
            target_goodput = target_goodput - self.current_traffic_patterns[1]
        elif 4 < elapsed_time_in_period <= 6:
            target_goodput = target_goodput - self.current_traffic_patterns[2]
        elif 6 < elapsed_time_in_period < 8:
            target_goodput = target_goodput - self.current_traffic_patterns[3]

        self.effective_episode += self.state_statistics[State.ACKED_BYTES_TIMEFRAME][Statistic.LAST]
        # Count loss for target
        self.target_episode += target_goodput * time_since_last * (1 - self.current_loss / 100)
        retransmissions_penalty = 1 + self.state_statistics[State.RETRANSMISSIONS][Statistic.LAST] * (1 - self.current_loss/100)
        if self.effective_episode > self.target_episode:
            reward = - retransmissions_penalty / 2
        else:
            reward = - retransmissions_penalty / (1 + (self.effective_episode / self.target_episode))

        logging.debug(f"Time since last {time_since_last}, Effective {self.effective_episode}, Target {self.target_episode}  Reward {reward}")

        return reward

    def truncated(self):
        if self.current_step >= self.max_time_steps_per_episode:
            return True
        else:
            return False

    def update_link_properties(self):
        self.current_bandwidth = self.bandwidth_var
        self.current_delay = self.delay_var
        self.current_loss = self.loss_var
        self.current_mice_flows_kbs *= self.bandwidth_var / self.bandwidth_start
        self.current_traffic_patterns = [
            self.bandwidth_var * 125 * .8,
            self.bandwidth_var * 125  * .208,
            self.bandwidth_var * 125  * .8,
            self.bandwidth_var * 125  * 0.208
        ]
        logging.info("Traffic patterns: " + str(self.current_traffic_patterns))
        instant = time.time()
        self._traffic_timer = instant

    def step(self, action) -> GymStepReturn:
        self.current_step += 1
        self.total_steps += 1
        #TODO: Try to move this step to reset() method somehow
        if self.current_step == 1:
            self._start_mockets_processes()
            # New Mockets takes seconds before establishing connection
            self.state = self._next_state()
            self.variation_pending = self.timed_link_update(
                delay_start=f"{self.delay_start}ms",
                bandwidth_start=self.bandwidth_start,
                loss_start=self.loss_start,
                new_delay=f"{self.delay_var}ms",
                new_bandwidth=self.bandwidth_var,
                new_loss=self.loss_var,
                interval_sec=self.variation_interval
            )
            self._init_background_traffic_timers()
            self.episode_start_time = time.time()

        cwnd_value = self._cwnd_update_throttle(action[0])

        # CWND value must be in Bytes
        self._put_action(cwnd_value)

        # Apply link variation if necessary
        if self.variation_pending and self.variation_pending.ready:
            self.variation_pending = None
            self.update_link_properties()

        # Action delay in ms
        self.action_delay = (time.time() - self.previous_timestamp) * constants.UNIT_FACTOR
        self.state = self._next_state()

        reward = self._get_reward()

        info = {
            'current_statistics': self.last_state,
            'action': action[0],
            'reward': reward,
            'action_delay': self.action_delay,
            'start_time': self.episode_start_time,
            'parameter_fetch_error': self.parameter_fetch_error
        }

        terminated = True if self._is_finished() else False

        if self.truncated():
            info["TimeLimit.truncated"] = not terminated
            terminated = True

        self.last_step_timestamp = time.time()

        return self.state, reward, terminated, info

    def render(self, mode: str = "console") -> None:
        pass
