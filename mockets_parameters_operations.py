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

# Initialize current_statistics with None
min_ack = [0]
current_statistics = dict.fromkeys(['lrtt',  # Last RTT in ms
                                    'rtt_min',
                                    # Minimum RTT since beginning ep.
                                    'srtt',  # Smoothed RTT
                                    'delay',  # Queuing delay measured in
                                    # rtt_standing - rtt_min
                                    'cwnd_bytes',  # Congestion window in
                                    # bytes calculated as cwnd * MSS ??
                                    'inflight_bytes',  # Number of bytes sent
                                    # but unacked
                                    'writable_bytes',  # Number of writable
                                    # bytes cwnd_bytes - inflight_bytes
                                    'sent_bytes',  # Number of bytes sent
                                    # since last ACK (LAST RECEIVE??)
                                    'received_bytes',  # Number of byte
                                    # received since last ACK (LAST RECEIVE??)
                                    'acked_bytes',  # Number of bytes acked
                                    # in this ACK
                                    'throughput',  # Instant throughput
                                    # estimated from recent ACKs
                                    'last_receive_timestamp',
                                    'sent_bytes_in_time_window',
                                    # Sent bytes in last_receive_timestamp
                                    # window. Used for approximate throughput
                                    'set_cwnd_bytes'
                                    # TODO: 'rtt_standing',  # Min RTT over
                                    # win of size
                                    # srtt/2 ??
                                    # TODO: 'rtt_var',  # Variance in RTT
                                    # TODO: 'rtx_bytes',  # Number of bytes
                                    # retransmitted since last ACK
                                    # TODO: 'lost_bytes',  # Number of bytes
                                    # lost in
                                    # this loss
                                    # TODO:'rtx_count',  # Number of pakcets
                                    # retransmitted since last ACK
                                    # TODO: 'timeout_based_rtx_count',
                                    # Number of
                                    # Retransmissions due to PTO since last ACK
                                    # TODO: 'pto_count',  # Number of times
                                    # packet
                                    # loss timer fired before receiving an ACK
                                    # TODO: 'total_pto_count',  # Number of times
                                    # packet loss timer fired since last ACK
                                    # TODO: 'persistent_congestion'  # Flag
                                    # indicating whether persistent congestion
                                    # is detected
                                    ], 0.0)


def smoothed_rtt(current_srtt: float, rtt: float, alpha: float):
    return rtt if current_srtt is None else (1 - alpha) * current_srtt + \
                                            alpha * rtt


def writable_bytes(cwnd: float, inflight_bytes: float) -> float:
    return cwnd - inflight_bytes


def throughput(sent_bytes: float, timestamp_t1: float, timestamp_t2: float,
               ) -> float:
    return sent_bytes / (timestamp_t2 - timestamp_t1)


# Just a placeholder for the time being
def compute_statistics(cumulative_received_bytes: int,
                       cumulative_sent_bytes: int,
                       cumulative_sent_good_bytes: int,
                       current_window_size: int,
                       last_receive_timestamp: int,
                       unack_bytes: int,
                       retransmissions: int,
                       chunk_rtt: int,
                       min_acknowledge_time: int) -> None:
    # Based
    current_statistics['lrtt'] = min_acknowledge_time
    current_statistics['cwnd_bytes'] = current_window_size
    current_statistics['inflight_bytes'] = unack_bytes
    min_ack.append(min_acknowledge_time)

    # Further computation
    current_statistics['rtt_min'] = min(current_statistics['lrtt'],
                                        current_statistics['rtt_min'])
    current_statistics['srtt'] = smoothed_rtt(current_statistics['srtt'],
                                              current_statistics['lrtt'],
                                              constants.ALPHA)
    current_statistics['writable_bytes'] = writable_bytes(current_statistics[
                                                              'cwnd_bytes'],
                                                          current_statistics[
                                                              'inflight_bytes'])

    if last_receive_timestamp != current_statistics['last_receive_timestamp']:
        current_statistics['throughput'] = throughput(current_statistics[
                                                          'sent_bytes_in_time_window'],
                                                      current_statistics[
                                                          'last_receive_timestamp'],
                                                      last_receive_timestamp)

        current_statistics['last_receive_timestamp'] = last_receive_timestamp
        current_statistics['sent_bytes_in_time_window'] = 0

    # Temporary
    current_statistics['sent_bytes_in_time_window'] += cumulative_sent_bytes
    current_statistics['sent_bytes'] += cumulative_sent_bytes
    current_statistics['received_bytes'] += cumulative_received_bytes
    current_statistics['acked_bytes'] += cumulative_sent_bytes - unack_bytes

    logging.debug(f"ENV RECEIVED - Cumulative Receive bytes:"
                  f" {cumulative_received_bytes}")
    logging.debug(f"ENV RECEIVED - Cumulative Sent bytes:"
                  f" {cumulative_sent_bytes}")
    logging.debug(f"ENV RECEIVED - Cumulative Sent good bytes:"
                  f" {cumulative_sent_good_bytes}")
    logging.debug(
        f"ENV RECEIVED - Current Window Size: {current_window_size}")
    logging.debug(f"ENV RECEIVED - Last Received Timestamp (Micro):"
                  f" {last_receive_timestamp}")
    logging.debug(f"ENV RECEIVED - Unack Bytes: {unack_bytes}")
    logging.debug(f"ENV RECEIVED - Retransmissions: {retransmissions}")
    logging.debug(f"ENV RECEIVED - Chunk RTT (Micro): {chunk_rtt}")
    logging.debug(
        f"ENV RECEIVED - Min Ack Time (Micro): {min_acknowledge_time}")

    logging.debug(f"ENV CAL - RTT MEAN: {statistics.mean(min_ack)} ms")
    logging.debug(
        f"ENV CALC - RTT VARIANCE: {statistics.variance(min_ack)} "
        f"ms")
    logging.debug(f"ENV CAL - RTT MAX: {max(min_ack)} ms")
    logging.debug(f"ENV CAL - RTT MIN: {min(min_ack)} ms")
    logging.debug(f"ENV CAL - THROUGHPUT: {current_statistics['throughput']}")
    logging.debug(f"ENV CAL - SENT BYTES IN TIMESTAMP DIFFERENCE:"
                  f" {current_statistics['sent_bytes_in_time_window']}")


# Mockets Congestion Window % action
def cwnd_update(index) -> int:
    action = math.ceil(current_statistics['cwnd_bytes'] + current_statistics['cwnd_bytes'] * constants.ACTIONS[index])
    current_statistics['set_cwnd_bytes'] = action

    logging.debug(f"AGENT - CURRENT CWND {current_statistics['cwnd_bytes']} "
                  f"UPDATE WITH ACTION {constants.ACTIONS[index]} RETURNING "
                  f"{action}")
    return action
