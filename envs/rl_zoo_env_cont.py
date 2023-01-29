import time
from multiprocessing import Queue, Process
import queue
import numpy as np
import logging
from gym import Env
from gym.spaces import Box, Discrete
from stable_baselines3.common.type_aliases import GymObs, GymStepReturn

import data_processing_server.congestion_control_server as cc_server
from envs.utils import constants, traffic_generator
import math
from envs.utils.constants import Parameters, State,Statistic
import subprocess
import paramiko

import pprint
import pandas as pd
from collections import defaultdict

from statistics import fmean, median_low, median, median_high, stdev
import socket

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


def mockets_gradlew_args(mockets_server_ip: str, grpc_port: int, is_testing: bool, duration: int):
    if is_testing:
        client_type = "runCCTestingClient"
    else:
        client_type = "runCCTrainingClient"

    return ['/code/jmockets/gradlew',
            client_type,
            f"--args=-ip {mockets_server_ip} --grpc-server localhost:"
            f"{grpc_port} --duration {duration}",
            '-p',
            '/code/jmockets']


def mockets_dist_args(mockets_server_ip: str, grpc_port: int, is_testing: bool,
                      duration: int):
    if is_testing:
        path = f"{constants.DIST_PATH}/testing/examples/bin/examples"
    else:
        path = f"{constants.DIST_PATH}/training/examples/bin/examples"

    return [path,
            '-ip',
            f'{mockets_server_ip}',
            '--grpc-server',
            f'localhost:{grpc_port}',
            '--duration',
            f'{duration}']


def _state_parameters_intersection():
    parameters_values = set([parameter.value for parameter in Parameters])
    state_values = set([state_parameter.value for state_parameter in State])

    return parameters_values & state_values


def reward_v1_1(instant_throughput, rtt_diff, packets_transmitted,
                retransmissions, eps=0.05):
    th = math.log((eps + instant_throughput))
    penalties = math.log((1 + retransmissions) * (1 + rtt_diff))
    if retransmissions > packets_transmitted or packets_transmitted == 0:
        reward = th - penalties
    else:
        reward = th - (retransmissions / packets_transmitted) * penalties
    reward = math.log((1 + packets_transmitted) / (1 + retransmissions))

    return reward


def reward_v2(packets_transmitted, retransmissions, rtt, rtt_min):
    if retransmissions > 0:
        reward = packets_transmitted / (rtt / rtt_min * (retransmissions))
    else:
        reward = packets_transmitted

    return reward


def reward_v3(good_inst, rtt_diff, good_diff, th_ema, rtt_min_ema):

    if good_diff > 2:
        alfa = math.log(good_diff, 2)
    if good_diff < -10:
        # If the RTT gets better of a substantial quantity give a positive
        # but small reward in function of what the reduction of goodput is
        if rtt_diff/rtt_min_ema < 1:
            alfa = 1/math.log(abs(good_diff), 10)
        # If the RTT gets worst of a substantial quantity everything should
        # be negative, so this is for penalty coherence
        if rtt_diff/rtt_min_ema > 1:
            alfa = math.log(abs(good_diff), 10)
        else:
            alfa = - math.log(abs(good_diff), 10)
    else:
        alfa = 1

    # How many "good" things per second we have just sent compared to the EMA
    # of the total bytes sent per second
    bonus = alfa * (good_inst/(th_ema + 1))

    # Reward an increase of goodput

    penalties = 0

    if abs(rtt_diff/rtt_min_ema) > 0.4:
        beta = 1
    elif 0.1 < abs(rtt_diff/rtt_min_ema) <= 0.4:# if retr_diff > 0:
    #todo: if goodput_diff > 0:
    #   bonus *= goodput_diff


        beta = 0.5
    elif 0.03 < abs(rtt_diff/rtt_min_ema) <= 0.1:
        beta = 0.3
    else:
        beta = 0.1

    penalties += beta * rtt_diff/(rtt_min_ema + 1)

    reward = bonus * (1 - penalties) if good_inst != 0 else -penalties

    return reward


def reward_v4(good_inst, rtt_diff, retransmissions, rtt_min_ema):
    bonus = good_inst

    # if good_diff > 0:
    #     alfa = math.log(10 + good_diff, 10)
    # if good_diff < 0:
    #     alfa = - math.log(abs(good_diff - 10), 10)
    # else:
    #     alfa = 1
    # bonus += alfa

    # if rtt_diff < 0:
    #     bonus += good_diff

    penalties = 0

    if abs(rtt_diff/(rtt_min_ema + 1)) > 0.6:
        beta = 1
    elif 0.1 < abs(rtt_diff/(rtt_min_ema + 1)) <= 0.6:
        beta = 0.5
    elif 0.03 < abs(rtt_diff/(rtt_min_ema + 1)) <= 0.1:
        beta = 0.3
    else:
        beta = 0.1

    penalties += beta * rtt_diff/(rtt_min_ema + 1)

    reward = bonus * (1 - penalties) if good_inst > 0 else - retransmissions * (1 - penalties)

    return reward


def reward_v5(good_inst, packets_transmitted, retransmissions, rtt_diff,
              rtt_min_ema):
    bonus = (packets_transmitted/(1 + retransmissions))

    # if good_diff > 0:
    #     alfa = math.log(10 + good_diff, 10)
    # if good_diff < 0:
    #     alfa = - math.log(abs(good_diff - 10), 10)
    # else:
    #     alfa = 1
    # bonus += alfa

    # if rtt_diff < 0:
    #     bonus += good_diff

    penalties = 0
    eps = 0.05
    if abs(rtt_diff/(rtt_min_ema + 1)) > 0.6:
        beta = 1
    elif 0.1 < abs(rtt_diff/(rtt_min_ema + 1)) <= 0.6:
        beta = 0.5
    elif 0.03 < abs(rtt_diff/(rtt_min_ema + 1)) <= 0.1:
        beta = 0.3
    else:
        beta = 0.1

    penalties += beta * rtt_diff/(rtt_min_ema + 1)

    if penalties >= 1:
        penalties = 0.99

    reward = - 1 / (1 + bonus * (1 - penalties))
    #Problem, if SRTT is very high the agent gets higher return due to lesser
    # steps and

    return reward


def reward_v6(acked_bytes_timeframe, acked_diff, rtt_diff, rtt_min_ema):
    bonus = acked_bytes_timeframe

    penalties = 0

    eps = 0.05
    if rtt_diff/(rtt_min_ema + 1) > 0.6:
        beta = 1
    elif 0.1 < rtt_diff/(rtt_min_ema + 1) <= 0.6:
        beta = 0.5
    elif 0.03 < rtt_diff/(rtt_min_ema + 1) <= 0.1:
        beta = 0.3
    else:
        beta = 0.1

    penalties += beta * rtt_diff/(rtt_min_ema + 1)

    if penalties >= 1:
        penalties = 0.99

    reward = - 1 / (1 + bonus * (1 - penalties))

    return reward

def reward_v7(real_goodput, rtt_diff, retransmissions, rtt_min_ema, current_traffic_patterns, traffic_timer, packets_transmitted):
    elapsed_time_in_period = int(time.time() - traffic_timer) % 8
    target = constants.LINK_BANDWIDTH_KB - 20

    if 0 < elapsed_time_in_period < 2:
        target = target - current_traffic_patterns[0].packets
    elif 2 < elapsed_time_in_period < 4:
        target = target - current_traffic_patterns[1].packets
    elif 4 < elapsed_time_in_period < 6:
        target = target - current_traffic_patterns[2].packets
    elif 6 < elapsed_time_in_period < 8:
        target = target - current_traffic_patterns[3].packets

    bonus = (real_goodput/target)

    if abs(rtt_diff/(rtt_min_ema + 1)) > 0.6:
        beta = 1
    elif 0.1 < abs(rtt_diff/(rtt_min_ema + 1)) <= 0.6:
        beta = 0.5
    elif 0.03 < abs(rtt_diff/(rtt_min_ema + 1)) <= 0.1:
        beta = 0.3
    else:
        beta = 0.1

    penalties = beta * rtt_diff/(rtt_min_ema + 1)

    if real_goodput == 0:
        reward = - retransmissions/packets_transmitted
    else:
        reward = bonus * (1 - penalties)

    return reward


def reward_v8(real_goodput, rtt_diff, retransmissions, rtt_min_ema, current_traffic_patterns, traffic_timer, packets_transmitted):
    elapsed_time_in_period = float(time.time() - traffic_timer) % 8
    target = constants.LINK_BANDWIDTH_KB - traffic_generator.MICE_FLOWS_KB_S

    if 0 <= elapsed_time_in_period <= 2:
        target = target - current_traffic_patterns[0].packets
    elif 2 < elapsed_time_in_period <= 4:
        target = target - current_traffic_patterns[1].packets
    elif 4 < elapsed_time_in_period <= 6:
        target = target - current_traffic_patterns[2].packets
    elif 6 < elapsed_time_in_period < 8:
        target = target - current_traffic_patterns[3].packets

    bonus = (real_goodput/target)

    if abs(rtt_diff/(rtt_min_ema + 1)) > 0.6:
        beta = 1
    elif 0.1 < abs(rtt_diff/(rtt_min_ema + 1)) <= 0.6:
        beta = 0.5
    elif 0.03 < abs(rtt_diff/(rtt_min_ema + 1)) <= 0.1:
        beta = 0.3
    else:
        beta = 0.1
    penalties = beta * rtt_diff/(rtt_min_ema + 1)

    if penalties >= 1:
        penalties = 0.99

    reward = - 1 / (1 + bonus * (1 - penalties))

    return reward


def ideal_cwnd(current_traffic_patterns, traffic_timer, rtt, retransmissions):
    elapsed_time_in_period = float(time.time() - traffic_timer) % 8
    target = constants.LINK_BANDWIDTH_KB - traffic_generator.MICE_FLOWS_KB_S

    if 0 <= elapsed_time_in_period <= 2:
        target = target - current_traffic_patterns[0].packets
    elif 2 < elapsed_time_in_period <= 4:
        target = target - current_traffic_patterns[1].packets
    elif 4 < elapsed_time_in_period <= 6:
        target = target - current_traffic_patterns[2].packets
    elif 6 < elapsed_time_in_period < 8:
        target = target - current_traffic_patterns[3].packets

    cwnd = math.ceil((target / (1000/(80))) * constants.UNIT_FACTOR)
    logging.info(f"TARGET GOOD: {target} RTT:{rtt}, CWND:{cwnd}, RETR: {retransmissions}"
                 f"ELAPSED: {elapsed_time_in_period}")
    return cwnd


def eval_or_train(is_testing):
    return "Eval" if is_testing else "Training"


class CongestionControlEnv(Env):
    def __init__(self,
                 n_timesteps: int = 500000,
                 mockets_server_ip: str = "192.168.1.17",
                 traffic_generator_ip: str = "192.168.2.40",
                 traffic_receiver_ip: str = "192.168.1.40",
                 grpc_port: int = 50051,
                 observation_length: int = len(State) * len(Statistic),
                 is_testing: bool = False,
                 max_duration: int = 80,
                 max_time_steps_per_episode: int = 200):
        """
        :param eps: the epsilon bound for correct value
        :param episode_length: the length of each episode in timesteps
        :param observation_lenght: the lenght of the observations
        """
        self.action_space = Box(low=-1, high=+1, shape=(1,), dtype=np.float32)
        self.observation_space = Box(low=-float("inf"),
                                     high=float("inf"),
                                     shape=(observation_length, ))

        self.current_step = 0
        self.total_steps = 0
        self.num_resets = 0
        self.episode_return = 0
        self.episode_start_time = 0
        self.episode_time = 0
        self.action_delay = 0
        self.n_timestep = n_timesteps

        self.previous_timestamp = 0
        self.mockets_raw_observations = dict((param, 0.0) for param in Parameters)
        self.processed_observations_history = dict((param, [0.0]) for param in State)

        self.state_statistics = dict((stats, dict((stat, 0.0) for stat in Statistic)) for stats in State)
        self.last_state = dict((param, 0.0) for param in State)

        self._mockets_server_ip = mockets_server_ip
        self._traffic_generator_ip = traffic_generator_ip
        self._traffic_receiver_ip = traffic_receiver_ip

        self.grpc_port = grpc_port

        self.ssh_traffic_gen = paramiko.SSHClient()
        self.ssh_traffic_gen.set_missing_host_key_policy(
            paramiko.AutoAddPolicy())

        self.ssh_traffic_rec = paramiko.SSHClient()
        self.ssh_traffic_rec.set_missing_host_key_policy(
            paramiko.AutoAddPolicy())

        self.ssh_mockets_server = paramiko.SSHClient()
        self.ssh_server_stdout = None
        self.ssh_mockets_server.set_missing_host_key_policy(
            paramiko.AutoAddPolicy())

        # Run server in a different process
        self._server_process = None
        self._mocket_process = None
        # Observation queue where the server will publish
        self._state_queue = None
        # Action queue where the agent will publish the action
        self._action_queue = None

        self.parameter_fetch_error = False
        self._is_testing = is_testing
        self._max_duration = max_duration
        self.max_time_steps_per_episode = 500 if self._is_testing else max_time_steps_per_episode


        self.traffic_generator = traffic_generator.TrafficGenerator()
        self._traffic_timer = None
        self.episode_training_script = None
        self.episode_evaluation_script = self.traffic_generator.generate_evaluation_script()

        self.traffic_script = None
        self.target_episode = 0
        self.effective_episode = 0
        self.last_step_timestamp = None

        # self.reset()

    def __del__(self):
        """Book-keeping to release resources"""
        if self._server_process is not None and self._mocket_process is not None:
            logging.info(f"Closing process for {eval_or_train(self._is_testing)}")
            logging.info("Closing Mockets Client connection")
            self._mocket_process.terminate()

            logging.info("Closing Mockets Server connection")
            self.ssh_mockets_server.close()

            logging.info("Closing GRPC Server...")
            self._server_process.terminate()
            self._server_process.join()
            self._server_process.close()

            self._action_queue.close()
            self._state_queue.close()

            logging.info("Closing Background traffic connection")
            self.ssh_traffic_gen.close()

            logging.info("Closing BG Traffic receiver")
            self.ssh_traffic_rec.close()

            self._mocket_process = None
            self._server_process = None

            # Sleep, increase the chance ssh connections detected close()
            time.sleep(2)

    def _run_mockets_client(self, mockets_server_address, grpc_port,
                            mockets_logfile):
        self._mocket_process = subprocess.Popen(mockets_dist_args(
            mockets_server_address,
            grpc_port,
            self._is_testing,
            self._max_duration
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
        # TODO: Cleanup all that list slicing to avoid the zeros you don't want
        for key, value in self.processed_observations_history.items():
            # Skip RTT Fetch if communication is finished and value was not
            # computed
            self.last_state[key] = value[-1]
            self.state_statistics[key][Statistic.LAST] = value[-1]
            self.state_statistics[key][Statistic.EMA] = \
                exponential_moving_average(self.state_statistics[key][
                                               Statistic.EMA], value[-1])
            self.state_statistics[key][Statistic.MIN] = min(value[1:]) if\
                len(value) > 2 else value[-1]
            self.state_statistics[key][Statistic.MAX] = max(value[1:]) if\
                len(value) > 2 else value[-1]
            self.state_statistics[key][Statistic.MEAN] = fmean(value[1:]) if\
                len(value) > 2 else value[-1]
            self.state_statistics[key][Statistic.STD] = stdev(value[1:]) if\
                len(value) > 2 else value[-1]
            self.state_statistics[key][Statistic.DIFF] = value[-1] - value[-2] if \
                len(value) > 2 else value[-1]

    def _fetch_param_and_update_stats(self) -> int:
        while True:
            try:
                obs = self._state_queue.get(timeout=3)
            except queue.Empty as error:
                logging.info(f"Parameter Fetch: Timeout occurred")
                logging.info("Restarting Service!!")
                self.parameter_fetch_error = True
                self._cleanup()
                self._start_external_processes(reset_time=False)
            else:
                break

        self.mockets_raw_observations = obs
        self.mockets_raw_observations[Parameters.TIMESTAMP] /= constants.UNIT_FACTOR

        for value in _state_parameters_intersection():
            self.processed_observations_history[State(value)].append(self.mockets_raw_observations[Parameters(value)])

        # Return Timestamp in Seconds
        return self.mockets_raw_observations[Parameters.TIMESTAMP]

    def _is_finished(self):
        return self.mockets_raw_observations[Parameters.FINISHED]

    def _get_state(self) -> np.array:
        logging.debug("FETCHING STATE..")

        if not self._is_finished():
            timestamp = self._fetch_param_and_update_stats()
            self._process_additional_params()
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
        reward = self.reward_v9(
            current_traffic_patterns=self.traffic_generator.current_patterns,
            traffic_timer=self._traffic_timer
        )
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
        with open(f"mockets_log/client/mockets_client_ep"
                  f"{self.num_resets}.log", "w+") as log:
            self._run_mockets_client(self._mockets_server_ip,
                                     self.grpc_port,
                                     mockets_logfile=log)

    def _run_mockets_server(self):
        logging.info("Connecting to Mockets Server host machine")
        while True:
            try:
                self.ssh_mockets_server.connect(self._mockets_server_ip,
                                                username="pi",
                                                password="raspberry", timeout=60)
            except paramiko.ssh_exception.NoValidConnectionsError as e:
                logging.info("Connection failed, new attempt...")
            except socket.timeout as e:
                logging.info("Timeout elapsed, new attempt...")
            except socket.error as e:
                logging.info("Socket error, new attempt...")
            else:
                logging.info("Connected!")
                break

        logging.info("Launching Mockets Server...")
        transport = self.ssh_mockets_server.get_transport()
        channel = transport.open_session()
        # get_pty allows as to request a pseudo-terminal and bound all the
        # processes to it (theoretically, usage and docs are kinda confusing...)
        # It is used so that when the connection is closed also the command
        # gets its termination.
        # Changing directory is needed in order to load Mockets conf file
        # from  that folder
        channel.get_pty()
        channel.exec_command(
                "cd /home/pi/examples/bin/ && "
                "./examples -ip 0.0.0.0",
            )

    def _start_traffic_generator(self):
        logging.info("Connecting to sender host for background traffic")
        while True:
            try:
                self.ssh_traffic_gen.connect(self._traffic_generator_ip,
                                             username="raffaele",
                                             password="armageddon12345", timeout=60)
            except paramiko.ssh_exception.NoValidConnectionsError as e:
                logging.info("Connection failed, new attempt...")
            except socket.timeout as e:
                logging.info("Timeout elapsed, new attempt...")
            except socket.error as e:
                logging.info("Socket error, new attempt...")
            else:
                logging.info("Connected!")
                break

        logging.info("Starting Background traffic")
        logging.info(f"Script used: {self.traffic_script}")
        transport = self.ssh_traffic_gen.get_transport()
        channel = transport.open_session()
        # get_pty allows as to request a pseudo-terminal and bound all the
        # processes to it (theoretically, usage and docs are kinda confusing...)
        # It is used so that when the connection is closed also the command
        # gets its termination.
        channel.get_pty()
        channel.exec_command(
            "/Users/raffaele/Documents/IHMC/mgen/makefiles/mgen "
            f"{self.traffic_script}"
        )

    def _start_traffic_receiver(self):
        logging.info("Connecting to receiver host for background traffic")
        while True:
            try:
                self.ssh_traffic_rec.connect(self._traffic_receiver_ip,
                                             username="nomads",
                                             password="nomads", timeout=60)
            except paramiko.ssh_exception.NoValidConnectionsError as e:
                logging.info("Connection failed, new attempt...")
            except socket.timeout as e:
                logging.info("Timeout elapsed, new attempt...")
            except socket.error as e:
                logging.info("Socket error, new attempt...")
            else:
                logging.info("Connected!")
                break

        logging.info("Starting traffic receiver")
        transport = self.ssh_traffic_rec.get_transport()
        channel = transport.open_session()
        # get_pty allows as to request a pseudo-terminal and bound all the
        # processes to it (theoretically, usage and docs are kinda confusing...)
        # It is used so that when the connection is closed also the command
        # gets its termination.
        channel.get_pty()
        script = "receiver.mgen"
        channel.exec_command(
            "mgen inpuT /home/nomads/Muddasar-mgen/receiver.mgen nolog"
        )
        logging.info(f"{script} started!")

    def _start_background_traffic(self):
        self._start_traffic_receiver()
        self._start_traffic_generator()
        instant = time.time()
        self._traffic_timer = instant
        self.last_step_timestamp = instant

    def _cleanup(self):
        # You gotta clean your stuff sometimes
        self.__del__()

    def _start_external_processes(self, reset_time=True):
        logging.info("-------------------------------------")
        logging.info(f"STARTED EPISODE {self.num_resets} {eval_or_train(self._is_testing)}")
        self._state_queue = Queue()
        self._action_queue = Queue()

        self._run_grpc_server(self.grpc_port)
        self._run_mockets_server()
        self._start_background_traffic()
        self._run_mockets_ep_client()

        if reset_time:
            self.episode_start_time = time.time()
        logging.info("All commands executed. Episode started!")

    def report(self):
        time_taken = time.time() - self.episode_start_time
        logging.info(f"EPISODE {self.num_resets} {eval_or_train(self._is_testing)} COMPLETED")
        logging.info(f"Stats: {pprint.pformat(self.state_statistics)}")
        logging.info(f"Steps taken during episode: {self.current_step}")
        logging.info(f"Return accumulated: {self.episode_return}")
        logging.info(f"Time taken: {time_taken}")
        logging.info("-------------------------------------")

        if self._is_testing:
            logging.info("Saving Evaluation Time")
            with open(f"mockets_log/evaluation.log",
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

        initial_state = np.array([self.state_statistics[State(param.value)][Statistic(stat.value)]
                                  for param in State for stat in Statistic])

        self.traffic_script = self.traffic_generator.generate_evaluation_script() if self._is_testing else self.traffic_generator.generate_training_script()

        return initial_state

    def reward_v9(self, current_traffic_patterns, traffic_timer):
        elapsed_time_in_period = float(time.time() - traffic_timer) % 8

        target_goodput = constants.LINK_BANDWIDTH_KB - traffic_generator.MICE_FLOWS_KB_S
        time_since_last = time.time() - self.last_step_timestamp

        if 0 <= elapsed_time_in_period <= 2:
            target_goodput = target_goodput - current_traffic_patterns[0].packets
        elif 2 < elapsed_time_in_period <= 4:
            target_goodput = target_goodput - current_traffic_patterns[1].packets
        elif 4 < elapsed_time_in_period <= 6:
            target_goodput = target_goodput - current_traffic_patterns[2].packets
        elif 6 < elapsed_time_in_period < 8:
            target_goodput = target_goodput - current_traffic_patterns[3].packets

        self.effective_episode += self.state_statistics[State.SENT_GOOD_BYTES_TIMEFRAME][Statistic.LAST]
        # Count loss for target
        self.target_episode += target_goodput * time_since_last * 0.97


        if self.effective_episode > self.target_episode:
            reward = - 1 / 2
        else:
            reward = - 1 / (1 + (self.effective_episode / self.target_episode))

        logging.debug(f"Time since last {time_since_last}, Effective {self.effective_episode}, Target {self.target_episode}  Reward {reward}")

        return reward

    def truncated(self):
        if self.current_step >= self.max_time_steps_per_episode:
            return True
        else:
            return False

    def step(self, action) -> GymStepReturn:
        self.current_step += 1
        self.total_steps += 1

        #TODO: Try to move this step to reset() method somehow
        if self.current_step == 1:
            self._start_external_processes()
            self.state = self._next_state()

        cwnd_value = self._cwnd_update_throttle(action[0])

        # CWND value must be in Bytes
        self._put_action(cwnd_value)

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
