"""
Declares constant used for actions and mockets parameters
"""
from enum import Enum


class Parameters(Enum):
    # From Mockets
    CHUNK_RTT_MICRO = 0
    MIN_ACK_TIME_MICRO = 1
    SENT_BYTES = 2
    RCV_BYTES = 3
    SENT_GOOD_BYTES = 4
    CURR_WINDOW_SIZE = 5
    UNACK_BYTES = 6
    RETRANSMISSIONS = 7
    # Other Params
    WRITABLE_BYTES = 8
    SENT_BYTES_TIMEFRAME = 9
    SENT_GOOD_BYTES_TIMEFRAME = 10
    THROUGHPUT = 11
    GOODPUT = 12
    EMA_THROUGHPUT = 13
    LAST_RTT = 14
    MIN_RTT = 15
    SRTT = 16
    VAR_RTT = 17

# TODO: 'rtt_standing',  # Min RTT over
# win of size
# srtt/2 ??
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

MAXIMUM_SEGMENT_SIZE = None
# Increment/Decrement in % to be applied to the cwnd
ACTIONS = (1, 0.33, 0.05, -0.05, -0.33, 0)
STATE = ['lrtt', 'rtt_min', 'srtt', 'rtt_var', 'cwnd_bytes', 'sent_bytes',
         'received_bytes', 'acked_bytes', 'inflight_bytes', 'writable_bytes',
         'throughput', 'goodput']
ALPHA = 1 / 8  # Alfa for Smoother RTT calc
BETA = 1 / 4  # Beta for RTT Var
