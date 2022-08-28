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


def mockets_dist_args(mockets_server_ip: str, grpc_port: int, is_testing: bool):
    if is_testing:
        path = f"{constants.DIST_PATH}/testing/examples/bin/examples"
    else:
        path = f"{constants.DIST_PATH}/training/examples/bin/examples"

    return [path,
            '-ip',
            f'{mockets_server_ip}',
            '--grpc-server',
            f'localhost:{grpc_port}']


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

    if abs(rtt_diff/rtt_min_ema + 1) > 0.6:
        beta = 1
    elif 0.1 < abs(rtt_diff/rtt_min_ema + 1) <= 0.6:
        beta = 0.5
    elif 0.03 < abs(rtt_diff/rtt_min_ema + 1) <= 0.1:
        beta = 0.3
    else:
        beta = 0.1

    penalties += beta * rtt_diff/(rtt_min_ema + 1)

    reward = bonus * (1 - penalties) if good_inst > 0 else - retransmissions * (1 - penalties)

    return reward


class CongestionControlEnv(Env):
    def __init__(self,
                 n_timesteps: int = 500000,
                 mockets_server_ip: str = "192.168.1.17",
                 traffic_generator_ip: str = "192.168.2.40",
                 traffic_receiver_ip: str = "192.168.1.40",
                 grpc_port: int = 50051,
                 observation_length: int = len(State) * len(Statistic),
                 max_number_of_steps: int = 70000,
                 is_testing: bool = False):
        """
        :param eps: the epsilon bound for correct value
        :param episode_length: the length of each episode in timesteps
        :param observation_lenght: the lenght of the observations
        """
        self.action_space = Box(low=-1, high=+1, shape=(1,), dtype=np.float32)

        self.observation_space = Box(low=-float("inf"),
                                     high=float("inf"),
                                     shape=(observation_length, ))

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

            logging.info("Closing Background traffic connection")
            self.ssh_traffic_gen.close()

            logging.info("Closing BG Traffic receiver")
            self.ssh_traffic_rec.close()

            logging.info("Closing Mockets Server connection")
            self.ssh_mockets_server.close()

            # Sleep, increase the chance ssh connections detected close()
            time.sleep(2)

    def _run_mockets_client(self, mockets_server_address, grpc_port,
                            mockets_logfile):
        self._mocket_process = subprocess.Popen(mockets_dist_args(
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
            delta = self.mockets_raw_observations[Parameters.TIMESTAMP] - self.previous_timestamp

        self.processed_observations_history[State.THROUGHPUT].append(throughput(
            self.mockets_raw_observations[Parameters.SENT_BYTES_TIMEFRAME],
            delta  # Throughput KB/Sec
        ))
        self.processed_observations_history[State.GOODPUT].append(throughput(
            self.mockets_raw_observations[Parameters.SENT_GOOD_BYTES_TIMEFRAME],
            delta  # Throughput KB/Sec
        ))

        # Every packet is 1KB so every KB in timeframe sent is also a packet
        # sent
        self.processed_observations_history[State.PACKETS_TRANSMITTED].append(
            math.floor(self.mockets_raw_observations[Parameters.SENT_BYTES_TIMEFRAME]/constants.PACKET_SIZE_KB)
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
        self.mockets_raw_observations = self._state_queue.get()
        self.mockets_raw_observations[Parameters.TIMESTAMP] /= constants.UNIT_FACTOR

        for value in _state_parameters_intersection():
            # Avoid fetching RTT if finished signal is detected and value is 0
            if State(value) in {State.LAST_RTT,
                                State.MIN_RTT,
                                State.MAX_RTT,
                                State.SRTT,
                                State.VAR_RTT} and  \
                    self.mockets_raw_observations[Parameters(value)] == 0:
                continue

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

            logging.debug(f"STATE RECEIVED WITH DELAY: "
                     f"{(time.time() - timestamp) * constants.UNIT_FACTOR}ms")

            logging.debug(f"STATE: {self.state_statistics}")
        else:
            logging.debug("SKIPPING STATE FETCH")

        self.state = np.array([self.state_statistics[State(param.value)][Statistic(stat.value)]
                               for param in State for stat in Statistic])

        return self.state

    def _next_observation(self) -> np.array:
        return self._get_state()

    def _put_action(self, action):
        self._action_queue.put(action)

    # b = (1 + math.log(goodput/current_ema_throughput))
    # (bandwidth_used/bandwidth_avail)
    # (throughput/(last_rtt - rtt_min))
    # th = math.log((eps + instant_goodput))
    # Add retrasmissions/total_packets_sent
    def _get_reward(self) -> float:
        reward = reward_v4(
            good_inst=self.state_statistics[State.GOODPUT][Statistic.LAST],
            rtt_diff=self.state_statistics[State.LAST_RTT][Statistic.DIFF],
            retransmissions=self.state_statistics[State.RETRANSMISSIONS][Statistic.LAST],
            rtt_min_ema=self.state_statistics[State.MIN_RTT][Statistic.EMA]
        )
        self.episode_return += reward

        return reward

    # New CWND by throttle action return the amout of BYTES the CWND can be set
    def _cwnd_update_throttle(self, percentage) -> int:
        # New CWND in Bytes
        current_cwnd = self.state_statistics[State.CURR_WINDOW_SIZE][Statistic.LAST]
        cwnd = math.ceil((current_cwnd + percentage * current_cwnd) * constants.UNIT_FACTOR)

        if cwnd < constants.PACKET_SIZE_KB * constants.UNIT_FACTOR:
            return math.ceil(constants.PACKET_SIZE_KB * constants.UNIT_FACTOR)
        elif cwnd > constants.GRPC_FLOAT_UPPER_LIMIT:
            return constants.GRPC_FLOAT_UPPER_LIMIT
        else:
            return cwnd

    def _has_reached_steps_limits(self):
        return self.current_step == self._max_number_of_steps or self.n_timestep == self.total_steps

    def _run_grpc_and_mockets(self):
        self._run_grpc_server(self.grpc_port)
        with open(f"mockets_log/client/mockets_client_ep{self.num_resets}.log", "w") as log:
            self._run_mockets_client(self._mockets_server_ip,
                                     self.grpc_port,
                                     mockets_logfile=log)

    def _run_mockets_server(self):
        logging.info("Connecting to Mockets Server host machine")
        while True:
            try:
                self.ssh_mockets_server.connect(self._mockets_server_ip,
                                                username="marlin",
                                                password="nomads")
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
                "cd /home/marlin/Documents/jmockets/examples/bin/ && "
                "./examples -ip 0.0.0.0",
            )

    def _start_traffic_generator(self):
        logging.info("Connecting to sender host for background traffic")
        while True:
            try:
                self.ssh_traffic_gen.connect(self._traffic_generator_ip,
                                             username="raffaele",
                                             password="armageddon12345")
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
        transport = self.ssh_traffic_gen.get_transport()
        channel = transport.open_session()
        # get_pty allows as to request a pseudo-terminal and bound all the
        # processes to it (theoretically, usage and docs are kinda confusing...)
        # It is used so that when the connection is closed also the command
        # gets its termination.
        channel.get_pty()
        script = "evaluation_generator_100MB.mgen" if self._is_testing else "generator.mgen"
        channel.exec_command(
            "/Users/raffaele/Documents/IHMC/mgen/makefiles/mgen inpuT "
            f"/Users/raffaele/Documents/IHMC/{script}"
        )
        logging.info(f"{script} started!")

    def _start_traffic_receiver(self):
        logging.info("Connecting to receiver host for background traffic")
        while True:
            try:
                self.ssh_traffic_rec.connect(self._traffic_receiver_ip,
                                             username="nomads",
                                             password="nomads")
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

    def _cleanup(self):
        # You gotta clean your stuff sometimes
        self.__del__()
        self._state_queue = Queue()
        self._action_queue = Queue()

    def report(self):
        time_taken = time.time() - self.episode_start_time
        logging.info(f"EPISODE {self.num_resets} COMPLETED")
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

        self.mockets_raw_observations = dict((param, 0.0) for param in Parameters)
        self.processed_observations_history = dict((param, [0.0]) for param in State)
        self.state_statistics = dict((stats, dict((stat, 0.0) for stat in Statistic)) for stats in State)
        self.last_state = dict((param, 0.0) for param in State)

        self.current_step = 0
        self.num_resets += 1
        self.episode_return = 0
        initial_state = np.array([self.state_statistics[State(param.value)][Statistic(stat.value)]
                                  for param in State for stat in Statistic])

        return initial_state

    def step(self, action) -> GymStepReturn:
        info = {}
        reward = 0

        self.current_step += 1
        self.total_steps += 1

        #TODO: Try to move this step to reset() method
        if self.current_step == 1:
            logging.info("-------------------------------------")
            logging.info(f"STARTED EPISODE {self.num_resets}")
            self._run_mockets_server()
            self._start_background_traffic()
            self._run_grpc_and_mockets()
            self.episode_start_time = time.time()
            logging.info("All commands executed. Episode started!")

        else:
            cwnd_value = self._cwnd_update_throttle(action[0])
            # Handle timeout to let the episode finish asap
            if self._has_reached_steps_limits():
                logging.info("TIMEOUT STEPS EXPIRED")
                info['TimeLimit.truncated'] = True
                self._put_action(constants.CWND_UPPER_LIMIT_BYTES)
            else:
                # CWND value must be in Bytes
                self._put_action(cwnd_value)
                # self._put_action(9000)
                # self._put_action(25000)
            # Action delay in ms
            self.action_delay = (time.time() - self.previous_timestamp) * constants.UNIT_FACTOR
            reward = self._get_reward()

            info = {
                'current_statistics': self.last_state,
                'action': action[0],
                'reward': reward,
                'action_delay': self.action_delay,
                'start_time': self.episode_start_time
            }

        observation = self._next_observation()

        done = False
        if self._is_finished() or self._has_reached_steps_limits():
            logging.info("Cleaning up, waiting for communication to end...")
            self._cleanup()
            self.episode_time = time.time() - self.episode_start_time
            info['episode_time'] = self.episode_time
            done = True

        return observation, reward, done, info

    def render(self, mode: str = "console") -> None:
        pass
