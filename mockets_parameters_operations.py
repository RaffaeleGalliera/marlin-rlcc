"""
This module takes care of compute statistics, log them and visualize them

<long description>

Author: Raffaele Galliera gallieraraffaele@gmail.com

Created: February 21st, 2022
"""

import logging
import constants
import math
import statistics
from constants import Parameters

# Initialize current_statistics with None
min_ack = [0.0]

# current_statistics = dict.fromkeys(['lrtt',  # Last RTT in ms
#                                     'rtt_min',
#                                     # Minimum RTT since beginning ep.
#                                     'srtt',  # Smoothed RTT
#                                     'rtt_var',  # Variance in RTT
#                                     'delay',  # Queuing delay measured in
#                                     # rtt_standing - rtt_min
#                                     'cwnd_bytes',  # Congestion window in
#                                     # bytes calculated as cwnd * MSS ??
#                                     'inflight_bytes',  # Number of bytes sent
#                                     # but unacked
#                                     'writable_bytes',  # Number of writable
#                                     # bytes cwnd_bytes - inflight_bytes
#                                     'sent_bytes',  # Number of bytes sent
#                                     # since last ACK (LAST RECEIVE??)
#                                     'received_bytes',  # Number of byte
#                                     # received since last ACK (LAST RECEIVE??)
#                                     'acked_bytes',  # Number of bytes acked
#                                     # in this ACK
#                                     'throughput',  # Instant throughput
#                                     # estimated from recent ACKs
#                                     'ema_throughput',
#                                     'goodput',
#                                     'acked_bytes_in_time_window',
#                                     'sent_bytes_in_time_window',
#                                     # Sent bytes in last_receive_timestamp
#                                     # window. Used for approximate throughput
#                                     # TODO: 'rtt_standing',  # Min RTT over
#                                     # win of size
#                                     # srtt/2 ??
#                                     # TODO: 'rtx_bytes',  # Number of bytes
#                                     # retransmitted since last ACK
#                                     # TODO: 'lost_bytes',  # Number of bytes
#                                     # lost in
#                                     # this loss
#                                     # TODO:'rtx_count',  # Number of pakcets
#                                     # retransmitted since last ACK
#                                     # TODO: 'timeout_based_rtx_count',
#                                     # Number of
#                                     # Retransmissions due to PTO since last ACK
#                                     # TODO: 'pto_count',  # Number of times
#                                     # packet
#                                     # loss timer fired before receiving an ACK
#                                     # TODO: 'total_pto_count',  # Number of times
#                                     # packet loss timer fired since last ACK
#                                     # TODO: 'persistent_congestion'  # Flag
#                                     # indicating whether persistent congestion
#                                     # is detected
#                                     ], 0.0)

current_statistics = dict((param, 0.0) for param in Parameters)

# Additional parameters to help with stats calculation
prev_stats_helper = dict((param, 0.0) for param in Parameters)
timestamps = dict((param, 0) for param in Parameters)


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
    return rtt if current_srtt is 0.0 else (1 - alpha) * current_srtt + alpha * rtt


def rtt_var(current_srtt: float, current_rtt_var: float, rtt: float,
            beta: float):
    return rtt / 2 if current_rtt_var is 0.0 else (1 - beta) * current_rtt_var \
                                                  + beta * abs(current_srtt - rtt)


def writable_bytes(cwnd: float, inflight_bytes: float) -> float:
    return cwnd - inflight_bytes


def throughput(sent_bytes: float, delta: int) -> float:
    return sent_bytes / delta


def ema_throughput(current_ema_throughput: float, current_throughput: float,
                   alpha: float):
    if current_ema_throughput is 0.0:
        return current_throughput
    else:
        return (1 - alpha) * current_ema_throughput + alpha * current_throughput


# Mockets Congestion Window % action
def cwnd_update(index) -> int:
    action = math.ceil(
        current_statistics[Parameters.CURR_WINDOW_SIZE] + current_statistics[
            Parameters.CURR_WINDOW_SIZE] * constants.ACTIONS[index])
    prev_stats_helper[Parameters.CURR_WINDOW_SIZE] = action

    logging.debug(f"AGENT - CURRENT CWND {current_statistics[Parameters.CURR_WINDOW_SIZE]} "
                  f"UPDATE WITH ACTION {constants.ACTIONS[index]} RETURNING "
                  f"{action}")
    return action


def leaky_relu(alpha, val):
    return max(alpha * val, val)


def reward_function(current_ema_throughput, goodput, rtt, rtt_ema, rtt_min):
    return math.log(goodput/current_ema_throughput)


def debug_stats_information():
    logging.debug("\n".join(f"ENV STATS - {stat}: {value}" for stat, value in current_statistics.items()))


def update_statistics(param) -> None:
    param_type = param['parameter_type']
    logging.debug(param_type)
    # Param type is the int value associated to the enum
    if Parameters(param_type) is Parameters.CURR_WINDOW_SIZE:
        current_statistics[Parameters.CURR_WINDOW_SIZE] = param['value']
        timestamps[Parameters.CURR_WINDOW_SIZE] = param['timestamp']

        current_statistics[Parameters.WRITABLE_BYTES] = writable_bytes(
            current_statistics[Parameters.CURR_WINDOW_SIZE],
            current_statistics[Parameters.INFLIGHT_BYTES])

    elif Parameters(param_type) is Parameters.MIN_ACK_TIME_MICRO:
        # min_ack.append(current_statistics['lrtt'])
        current_statistics[Parameters.LAST_RTT] = param['value']
        # current_statistics[Parameters.MIN_RTT] = min(current_statistics['lrtt'],
        #                                     current_statistics['rtt_min'])
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

    # New Sent notification
    elif Parameters(param_type) is Parameters.SENT_BYTES:
        delta = param['timestamp'] - timestamps[Parameters.SENT_BYTES]
        current_statistics[Parameters.SENT_BYTES] += param['value']
        timestamps[Parameters.SENT_BYTES] = param['timestamp']

        current_statistics[Parameters.SENT_BYTES_TIMEFRAME] = \
            current_statistics[Parameters.SENT_BYTES] - prev_stats_helper[Parameters.SENT_BYTES]

        current_statistics[Parameters.ACKED_BYTES_IN_TIMEFRAME] = \
            current_statistics[Parameters.ACKED_BYTES] - prev_stats_helper[
                Parameters.ACKED_BYTES]

        current_statistics[Parameters.THROUGHPUT] = throughput(
            current_statistics[Parameters.SENT_BYTES_TIMEFRAME],
            delta
        )

        current_statistics[Parameters.GOODPUT] = throughput(
            current_statistics[Parameters.ACKED_BYTES_IN_TIMEFRAME],
            delta
        )

        current_statistics[Parameters.EMA_THROUGHPUT] = ema_throughput(
            current_statistics[Parameters.EMA_THROUGHPUT],
            current_statistics[Parameters.THROUGHPUT],
            alpha=constants.ALPHA
        )

        prev_stats_helper[Parameters.SENT_BYTES] = current_statistics[Parameters.SENT_BYTES]
        prev_stats_helper[Parameters.ACKED_BYTES] = current_statistics[Parameters.ACKED_BYTES]

    else:
        current_statistics[Parameters(param_type)] += param['value']
        timestamps[Parameters(param_type)] = param['timestamp']

    debug_stats_information()
