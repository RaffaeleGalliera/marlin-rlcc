from typing import Union, Optional

import gym
import optuna
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.logger import TensorBoardOutputFormat
from stable_baselines3.common.vec_env import VecEnv

from envs.utils.constants import State
from stable_baselines3.common.callbacks import EvalCallback
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
        self._packets_sum = 0

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
                self._throughput_sum +=info['current_statistics'][State.THROUGHPUT]
                self._goodput_sum += info['current_statistics'][State.GOODPUT]
                self._rtt_sum += info['current_statistics'][State.LAST_RTT]
                self._retransmissions_sum += info['current_statistics'][State.RETRANSMISSIONS]
                self._cwnd_sum += info['current_statistics'][State.CURR_WINDOW_SIZE]
                self._packets_sum += info['current_statistics'][State.PACKETS_TRANSMITTED]
                self._delay_sum += info['action_delay']

                step_logger = {
                    "training/observations/throughput_KB": info[
                        'current_statistics'][State.THROUGHPUT],
                    "training/observations/goodput_KB": info[
                        'current_statistics'][State.GOODPUT],
                    "training/observations/rtt_ms": info[
                        'current_statistics'][State.LAST_RTT],
                    "training/observations/srtt": info[
                        'current_statistics'][State.SRTT],
                    "training/observations/retransmissions": info[
                        'current_statistics'][State.RETRANSMISSIONS],
                    "training/observations/ema_retransmissions": info[
                        'current_statistics'][State.EMA_RETRANSMISSIONS],
                    "training/observations/current_window_size_KB": info[
                        'current_statistics'][State.CURR_WINDOW_SIZE],
                    "training/observations/packet_transmitted": info[
                        'current_statistics'][State.PACKETS_TRANSMITTED],
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
                avg_episodic_packet_transmitted = self._packets_sum/info["episode"]["l"]
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
                    "training/rollouts/episodic_packets_transmitted":
                        avg_episodic_packet_transmitted,
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
                self._packets_sum = 0

                exclude_dict = {key: None for key in logger_dict.keys()}
                self._tensorboard_writer.write(logger_dict, exclude_dict, self._episode_counter)

        return True


class EpisodeEvalCallback(EvalCallback):
    """
    Callback for evaluating an agent.

    .. warning::

      When using multiple environments, each call to  ``env.step()``
      will effectively correspond to ``n_envs`` steps.
      To account for that, you can use ``eval_freq = max(eval_freq // n_envs, 1)``

    :param eval_env: The environment used for initialization
    :param callback_on_new_best: Callback to trigger
        when there is a new best model according to the ``mean_reward``
    :param callback_after_eval: Callback to trigger after every evaluation
    :param n_eval_episodes: The number of episodes to test the agent
    :param eval_freq: Evaluate the agent every ``eval_freq`` call of the callback.
    :param log_path: Path to a folder where the evaluations (``evaluations.npz``)
        will be saved. It will be updated at each evaluation.
    :param best_model_save_path: Path to a folder where the best model
        according to performance on the eval env will be saved.
    :param deterministic: Whether the evaluation should
        use a stochastic or deterministic actions.
    :param render: Whether to render or not the environment during evaluation
    :param verbose:
    :param warn: Passed to ``evaluate_policy`` (warns if ``eval_env`` has not been
        wrapped with a Monitor wrapper)
    """

    def __init__(
        self,
        eval_env: Union[gym.Env, VecEnv],
        callback_on_new_best: Optional[BaseCallback] = None,
        callback_after_eval: Optional[BaseCallback] = None,
        n_eval_episodes: int = 5,
        eval_freq_ep: int = 10000,
        log_path: Optional[str] = None,
        best_model_save_path: Optional[str] = None,
        deterministic: bool = True,
        render: bool = False,
        verbose: int = 1,
        warn: bool = True,
    ):
        self.n_episode = 0
        self.eval_freq_ep = eval_freq_ep
        super(EpisodeEvalCallback, self).__init__(eval_env,
                                                  callback_on_new_best,
                                                  callback_after_eval,
                                                  n_eval_episodes,
                                                  1,
                                                  log_path,
                                                  best_model_save_path,
                                                  deterministic,
                                                  render,
                                                  verbose,
                                                  warn)

    def _on_step(self) -> bool:
        for info in self.locals["infos"]:
            if 'episode' in info or 'eval' in info:
                self.n_episode += 1
        if self.n_episode == self.eval_freq_ep:
            print("Running Eval now...")
            result = super(EpisodeEvalCallback, self)._on_step()
            self.n_episode = 0
            return result


class EpisodeTrialEvalCallback(EvalCallback):
    """
    Callback used for evaluating and reporting a trial.
    """

    def __init__(
            self,
            eval_env: VecEnv,
            trial: optuna.Trial,
            n_eval_episodes: int = 5,
            eval_freq_ep: int = 10000,
            deterministic: bool = True,
            verbose: int = 0,
            best_model_save_path: Optional[str] = None,
            log_path: Optional[str] = None,
    ):

        super(EpisodeTrialEvalCallback, self).__init__(
            eval_env=eval_env,
            n_eval_episodes=n_eval_episodes,
            eval_freq=1,
            deterministic=deterministic,
            verbose=verbose,
            best_model_save_path=best_model_save_path,
            log_path=log_path,
        )
        self.trial = trial
        self.eval_idx = 0
        self.is_pruned = False
        self.eval_freq_ep = eval_freq_ep
        self.n_episode = 0

    def _on_step(self) -> bool:
        for info in self.locals["infos"]:
            if 'episode' in info or 'eval' in info:
                self.n_episode += 1
        if self.n_episode == self.eval_freq_ep:
            print("Running Optuna Eval now...")
            super(EpisodeTrialEvalCallback, self)._on_step()
            self.eval_idx += 1
            # report best or report current ?
            # report num_timesteps or elasped time ?
            self.trial.report(self.last_mean_reward, self.eval_idx)
            # Prune trial if need
            if self.trial.should_prune():
                self.is_pruned = True
                return False
            self.n_episode = 0
        return True
