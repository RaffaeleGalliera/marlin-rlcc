from stable_baselines3.common.callbacks import BaseCallback, EvalCallback
from stable_baselines3.common.logger import TensorBoardOutputFormat

from constants import Parameters, ACTIONS

import time


class TrainingCallback(BaseCallback):
    """
    Callback used for logging raw episode data (return and episode length).
    """

    def __init__(self, verbose=0):
        super(TrainingCallback, self).__init__(verbose)
        # Custom counter to reports stats
        # (and avoid reporting multiple values for the same step)
        self._episode_counter = 0
        self._state_array_positions = dict()
        counter = 0

        self._throughput_sum = 0
        self._goodput_sum = 0
        self._rtt_sum = 0
        self._retransmissions_sum = 0
        self._cwnd_sum = 0
        self._delay_sum = 0

        self._start_time = time.time()

        self._tensorboard_writer = None

    def _init_callback(self) -> None:
        # Retrieve tensorboard writer to not flood the logger output
        for out_format in self.logger.output_formats:
            if isinstance(out_format, TensorBoardOutputFormat):
                self._tensorboard_writer = out_format
        assert self._tensorboard_writer is not None, "You must activate tensorboard logging when using RawStatisticsCallback"

    def _on_step(self) -> bool:

        for info in self.locals["infos"]:
            if 'current_statistics' in info:
                self._throughput_sum +=info['current_statistics'][Parameters.THROUGHPUT]
                self._goodput_sum += info['current_statistics'][Parameters.GOODPUT]
                self._rtt_sum += info['current_statistics'][Parameters.LAST_RTT]
                self._retransmissions_sum += info['current_statistics'][Parameters.RETRANSMISSIONS]
                self._cwnd_sum += info['current_statistics'][Parameters.CURR_WINDOW_SIZE]
                self._delay_sum += info['action_delay']

                step_logger = {
                    "training/observations/throughput_KB": info[
                        'current_statistics'][Parameters.THROUGHPUT],
                    "training/observations/goodput_KB": info[
                        'current_statistics'][Parameters.GOODPUT],
                    "training/observations/rtt_ms": info[
                        'current_statistics'][Parameters.LAST_RTT],
                    "training/observations/retransmissions": info[
                        'current_statistics'][Parameters.RETRANSMISSIONS],
                    "training/observations/current_window_size_KB": info[
                        'current_statistics'][Parameters.CURR_WINDOW_SIZE],
                    'training/action': info['action'],
                    'training/action_delay_ms': info['action_delay'],
                    'training/rewards': info['reward']
                }

                exclude_dict = {key: None for key in step_logger.keys()}
                self._tensorboard_writer.write(step_logger, exclude_dict,
                                               self.num_timesteps)

            if 'episode' in info:
                self._episode_counter += 1
                avg_episodic_throughput = self._throughput_sum/info["episode"]["l"]
                avg_episodic_goodput = self._goodput_sum/info["episode"]["l"]
                avg_episodic_rtt = self._rtt_sum/info["episode"]["l"]
                avg_episodic_retransmissions = self._retransmissions_sum/info["episode"]["l"]
                avg_window_size = self._cwnd_sum/info["episode"]["l"]
                avg_delay = self._delay_sum/info["episode"]["l"]

                logger_dict = {
                    "training/rollouts/episodic_return": info["episode"]["r"],
                    "training/rollouts/episodic_length": info["episode"]["l"],
                    "training/rollouts/episodic_avg_throughput_KB":
                        avg_episodic_throughput,
                    "training/rollouts/episodic_avg_goodput_KB":
                        avg_episodic_goodput,
                    "training/rollouts/episodic_avg_rtt_ms": avg_episodic_rtt,
                    "training/rollouts/episodic_avg_retransmissions":avg_episodic_retransmissions,
                    "training/rollouts/episodic_window_size_KB":
                        avg_window_size,
                    "training/rollouts/avg_delay_ms": avg_delay
                }

                if 'episode_time' in info:
                    logger_dict["training/rollouts/time_taken"] = info['episode_time']

                self._throughput_sum = 0
                self._goodput_sum = 0
                self._rtt_sum = 0
                self._retransmissions_sum = 0
                self._cwnd_sum = 0
                self._delay_sum = 0

                exclude_dict = {key: None for key in logger_dict.keys()}
                self._tensorboard_writer.write(logger_dict, exclude_dict, self._episode_counter)

        return True
