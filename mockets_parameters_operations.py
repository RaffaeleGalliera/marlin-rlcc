"""
This module takes care of compute statistics, log them and visualize them

<long description>

Author: Raffaele Galliera gallieraraffaele@gmail.com

Created: February 21st, 2022
"""

import logging
import constants
import math
import numpy as np
import statistics
import time
from constants import Parameters


# (2.2) When the first RTT measurement R is made, the host MUST set
#
#             SRTT <- R
#             RTTVAR <- R/2
#
# (2.3) When a subsequent RTT measurement R' is made, a host MUST set
#
#             RTTVAR <- (1 - beta) * RTTVAR + beta * |SRTT - R'|
#             SRTT <- (1 - alpha) * SRTT + alpha * R'
# https://datatracker.ietf.org/doc/html/rfc6298
def smoothed_rtt(current_srtt: float, rtt: float, alpha: float):
    # SRTT is an exponential moving average (EMA) with decay
    return rtt if current_srtt == 0.0 else (1 - alpha) * current_srtt + alpha * rtt


def rtt_var(current_srtt: float, current_rtt_var: float, rtt: float,
            beta: float):
    return rtt / 2 if current_rtt_var == 0.0 else (1 - beta) * current_rtt_var + beta * abs(current_srtt - rtt)


def writable_bytes(cwnd: float, inflight_bytes: float) -> float:
    return cwnd - inflight_bytes


def throughput(sent_bytes: float, delta: int) -> float:
    return sent_bytes / delta


def ema_throughput(current_ema_throughput: float, current_throughput: float,
                   alpha: float):
    if current_ema_throughput == 0.0:
        return current_throughput
    else:
        return (1 - alpha) * current_ema_throughput + alpha * current_throughput


# Mockets Congestion Window % action
def cwnd_update(current_statistics, stats_helper, index) -> int:
    action = math.ceil(
        current_statistics[Parameters.CURR_WINDOW_SIZE] + current_statistics[
            Parameters.CURR_WINDOW_SIZE] * constants.ACTIONS[index])
    stats_helper[Parameters.CURR_WINDOW_SIZE] = action

    logging.debug(f"AGENT - CURRENT CWND {current_statistics[Parameters.CURR_WINDOW_SIZE]} "
                  f"UPDATE WITH ACTION {constants.ACTIONS[index]} RETURNING "
                  f"{action}")
    return action


def leaky_relu(alpha, val):
    return max(alpha * val, val)


def reward_function(current_ema_throughput, goodput, rtt, rtt_ema, rtt_min):
    assert current_ema_throughput > 0.0, f"Throughput greater than 0 expected, got: {current_ema_throughput}"
    assert goodput >= 0.0, f"Goodput greater than 0 expected, got: {goodput}"

    return math.log(goodput/current_ema_throughput)


def debug_stats_information(current_statistics):
    logging.debug("\n".join(f"ENV STATS - {stat}: {value}" for stat, value in current_statistics.items()))


def min_excluding_zero(array_1, array_2):
    arr = np.array([array_1, array_2])
    return np.min(arr[np.nonzero(arr)])


def sent_bytes_in_timeframe(total_sent_bytes, previously_sent_byte):
    return total_sent_bytes - previously_sent_byte


def update_statistics(current_statistics, stats_helper, timestamps, value,
                      timestamp, param_type) -> None:
    # Param type is the int value associated to the enum
    if Parameters(param_type) is Parameters.CURR_WINDOW_SIZE:
        current_statistics[Parameters.CURR_WINDOW_SIZE] = value
        timestamps[Parameters.CURR_WINDOW_SIZE] = timestamp

        current_statistics[Parameters.WRITABLE_BYTES] = writable_bytes(
            current_statistics[Parameters.CURR_WINDOW_SIZE],
            current_statistics[Parameters.UNACK_BYTES])

    elif Parameters(param_type) is Parameters.CHUNK_RTT_MICRO:
        current_statistics[Parameters.CHUNK_RTT_MICRO] = value
        timestamps[Parameters.CHUNK_RTT_MICRO] = timestamp

        current_statistics[Parameters.LAST_RTT] = value
        timestamps[Parameters.LAST_RTT] = timestamp

        current_statistics[Parameters.MIN_RTT] = min_excluding_zero(
            current_statistics[Parameters.LAST_RTT],
            current_statistics[Parameters.MIN_RTT]
        )
        current_statistics[Parameters.MAX_RTT] = max(
            current_statistics[Parameters.LAST_RTT],
            current_statistics[Parameters.MAX_RTT]
        )
        current_statistics[Parameters.SRTT] = smoothed_rtt(
            current_statistics[Parameters.SRTT],
            current_statistics[Parameters.LAST_RTT],
            constants.ALPHA
        )
        current_statistics[Parameters.VAR_RTT] = rtt_var(
            current_statistics[Parameters.SRTT],
            current_statistics[Parameters.VAR_RTT],
            current_statistics[Parameters.LAST_RTT],
            constants.BETA
        )

    # New Sent notification, UPDATE UNACK
    elif Parameters(param_type) is Parameters.SENT_BYTES:
        # Delta between the last two sents
        delta = timestamp - timestamps[Parameters.SENT_BYTES]
        assert delta >= 0, f"Delta supposed to be positive, cannot have " \
                             f"info " \
                       f"from back in time...Got:" \
                       f" {timestamp} - {timestamps[Parameters.SENT_BYTES]}"

        # Update params
        current_statistics[Parameters.SENT_BYTES] += value
        timestamps[Parameters.SENT_BYTES] = timestamp
        
        current_statistics[Parameters.SENT_BYTES_TIMEFRAME] = sent_bytes_in_timeframe(
            current_statistics[Parameters.SENT_BYTES],
            stats_helper[Parameters.SENT_BYTES]
        )

        if delta > 0:
            current_statistics[Parameters.THROUGHPUT] = throughput(
                current_statistics[Parameters.SENT_BYTES_TIMEFRAME],
                delta
            )
            current_statistics[Parameters.EMA_THROUGHPUT] = ema_throughput(
                current_statistics[Parameters.EMA_THROUGHPUT],
                current_statistics[Parameters.THROUGHPUT],
                alpha=constants.ALPHA
            )

        stats_helper[Parameters.SENT_BYTES] = current_statistics[Parameters.SENT_BYTES]
        # Calc UNACK BYTES
        current_statistics[Parameters.UNACK_BYTES] = current_statistics[Parameters.SENT_BYTES] - current_statistics[Parameters.SENT_GOOD_BYTES]

    # New ACKED bytes notification, UPDATE UNACK
    elif Parameters(param_type) is Parameters.SENT_GOOD_BYTES:
        delta = timestamp - timestamps[Parameters.SENT_GOOD_BYTES]
        assert delta >= 0.0, f"Delta supposed to be positive, cannot have " \
                             f"info " \
                       f"from back in time...Got:" \
                       f" {delta}"

        current_statistics[Parameters.SENT_GOOD_BYTES] += value
        timestamps[Parameters.SENT_GOOD_BYTES] = timestamp

        current_statistics[
            Parameters.SENT_GOOD_BYTES_TIMEFRAME] = sent_bytes_in_timeframe(
            current_statistics[Parameters.SENT_GOOD_BYTES],
            stats_helper[Parameters.SENT_GOOD_BYTES]
        )
        if delta > 0:
            current_statistics[Parameters.GOODPUT] = throughput(
                current_statistics[Parameters.SENT_GOOD_BYTES_TIMEFRAME],
                delta
            )

        stats_helper[Parameters.SENT_GOOD_BYTES] = current_statistics[Parameters.SENT_GOOD_BYTES]
        # Calc UNACK BYTES
        current_statistics[Parameters.UNACK_BYTES] = current_statistics[Parameters.SENT_BYTES] - current_statistics[Parameters.SENT_GOOD_BYTES]

    elif Parameters(param_type) is Parameters.FINISHED:
        current_statistics[Parameters.FINISHED] = 1

    else:
        current_statistics[Parameters(param_type)] += value
        timestamps[Parameters(param_type)] = timestamp

    debug_stats_information(current_statistics)
