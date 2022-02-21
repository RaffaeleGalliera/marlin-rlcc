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


# Just a placeholder for the time being
def compute_statistics(cumulative_received_bytes: int,
                       cumulative_sent_bytes: int,
                       cumulative_sent_good_bytes: int,
                       current_window_size: int,
                       last_receive_timestamp: int,
                       traffic_in_flight: int) -> None:
    logging.debug(f"SERVER RECEIVED - Cumulative Receive bytes:"
                  f" {cumulative_received_bytes}")
    logging.debug(f"SERVER RECEIVED - Cumulative Sent bytes:"
                  f" {cumulative_sent_bytes}")
    logging.debug(f"SERVER RECEIVED - Cumulative Sent good bytes:"
                  f" {cumulative_sent_good_bytes}")
    logging.debug(
        f"SERVER RECEIVED - Current Window Size: {current_window_size}")
    logging.debug(f"SERVER RECEIVED - Last Received Timestamp:"
                  f" {last_receive_timestamp}")
    logging.debug(f"SERVER RECEIVED - Traffic in flight: {traffic_in_flight}")


# Mockets Congestion Window % action
def update_cwnd(index):
    return constants.ACTIONS[index]


