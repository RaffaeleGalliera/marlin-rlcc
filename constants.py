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
    CUMULATIVE_PACKET_LOSS = 8
    FINISHED = 9
    # Other Params
    WRITABLE_BYTES = 10
    SENT_BYTES_TIMEFRAME = 11
    SENT_GOOD_BYTES_TIMEFRAME = 12
    THROUGHPUT = 13
    GOODPUT = 14
    EMA_THROUGHPUT = 15
    LAST_RTT = 16
    MIN_RTT = 17
    MAX_RTT = 18
    SRTT = 19
    VAR_RTT = 20


class State(Enum):
    CHUNK_RTT_MICRO = 0
    SENT_BYTES = 2
    RCV_BYTES = 3
    SENT_GOOD_BYTES = 4
    CURR_WINDOW_SIZE = 5
    UNACK_BYTES = 6
    RETRANSMISSIONS = 7
    CUMULATIVE_PACKET_LOSS = 8
    WRITABLE_BYTES = 10
    SENT_BYTES_TIMEFRAME = 11
    SENT_GOOD_BYTES_TIMEFRAME = 12
    THROUGHPUT = 13
    GOODPUT = 14
    EMA_THROUGHPUT = 15
    LAST_RTT = 16
    MIN_RTT = 17
    MAX_RTT = 18
    SRTT = 19
    VAR_RTT = 20

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
ALPHA = 1 / 8  # Alfa for Smoother RTT calc
BETA = 1 / 4  # Beta for RTT Var
CWND_UPPER_LIMIT = 10000000
STARTING_WINDOW_SIZE = 4000
