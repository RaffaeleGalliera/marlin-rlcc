"""
This module takes care of compute statistics, log them and visualize them

<long description>

Author: Raffaele Galliera gallieraraffaele@gmail.com

Created: February 21st, 2022
"""

import logging
import constants

# Initialize current_statistics with None
current_statistics = dict.fromkeys(['lrtt',  # Last RTT in ms
                                    'rtt_min',
                                    # Minimum RTT since beginning ep.
                                    'srtt',  # Smoothed RTT
                                    'rtt_standing',  # Min RTT over win size
                                    # srtt/2
                                    'rtt_var',  # Variance in RTT
                                    'delay',  # Queuing delay measured in
                                    # rtt_standing - rtt_min
                                    'cwnd_bytes',  # Congestion window in
                                    # bytes calculated as cwnd * MSS
                                    'inflight_bytes',  # Number of bytes sent
                                    # but unacked
                                    'writable_bytes',  # Number of writable
                                    # bytes cwnd_bytes - inflight_bytes
                                    'sent_bytes',  # Number of bytes sent
                                    # since last ACK
                                    'received_bytes',  # Number of byte
                                    # received since last ACK
                                    'rtx_bytes',  # Number of bytes
                                    # retransmitted since last ACK
                                    'acked_bytes',  # Number of bytes acked
                                    # in this ACK
                                    'lost_bytes',  # Number of bytes lost in
                                    # this loss
                                    'throughput',  # Instant throughput
                                    # estimated from recent ACKs
                                    'rtx_count',  # Number of pakcets
                                    # retransmitted since last ACK
                                    'timeout_based_rtx_count',  # Number of
                                    # Retransmissions due to PTO since last ACK
                                    'pto_count',  # Number of times packet
                                    # loss timer fired before receiving an ACK
                                    'total_pto_count',  # Number of times
                                    # packet loss timer fired since last ACK
                                    'persistent_congestion'  # Flag
                                    # indicating whether persistent congestion
                                    # is detected
                                    ])


def smoothed_rtt(current_srtt: float, rtt: int, alpha: float):
    return rtt if current_srtt is None else (1 - alpha) * current_srtt + \
                                            alpha * rtt


# Just a placeholder for the time being
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
    logging.debug(f"SERVER RECEIVED - Cumulative Receive bytes:"
          f" {cumulative_received_bytes}")
    logging.debug(f"SERVER RECEIVED - Cumulative Sent bytes:"
          f" {cumulative_sent_bytes}")
    logging.debug(f"SERVER RECEIVED - Cumulative Sent good bytes:"
          f" {cumulative_sent_good_bytes}")
    logging.debug(f"SERVER RECEIVED - Current Window Size: {current_window_size}")
    logging.debug(f"SERVER RECEIVED - Last Received Timestamp (Micro):"
          f" {last_receive_timestamp}")
    logging.debug(f"SERVER RECEIVED - Unack Bytes: {unack_bytes}")
    logging.debug(f"SERVER RECEIVED - Retransmissions: {retransmissions}")
    logging.debug(f"SERVER RECEIVED - Chunk RTT (Micro): {chunk_rtt}")
    logging.debug(f"SERVER RECEIVED - Min Ack Time (Micro): {min_acknowledge_time}")

    current_statistics["srtt"] = smoothed_rtt(current_statistics["srtt"],
                                              current_statistics["rtt"],
                                              constants.ALPHA)


# Mockets Congestion Window % action
def update_cwnd(index):
    return constants.ACTIONS[index]
