"""
Declares constant used for actions and mockets parameters
"""
from enum import Enum


class Parameters(Enum):
    # From Mockets
    CURR_WINDOW_SIZE = 1

    SENT_BYTES = 2
    RCV_BYTES = 3
    SENT_GOOD_BYTES = 4
    SENT_BYTES_TIMEFRAME = 5
    SENT_GOOD_BYTES_TIMEFRAME = 6

    UNACK_BYTES = 7
    CUMULATIVE_RETRANSMISSIONS = 8
    RETRANSMISSIONS = 9
    EMA_RETRANSMISSIONS = 10
    WRITABLE_BYTES = 11

    # Other Params

    THROUGHPUT = 12
    GOODPUT = 13
    EMA_THROUGHPUT = 14
    EMA_GOODPUT= 15

    LAST_RTT = 16
    MIN_RTT = 17
    MAX_RTT = 18
    SRTT = 19
    VAR_RTT = 20

    TIMESTAMP = 21
    FINISHED = 22


class State(Enum):
    # From Mockets
    CURR_WINDOW_SIZE = 1

    SENT_BYTES = 2
    RCV_BYTES = 3
    SENT_GOOD_BYTES = 4
    SENT_BYTES_TIMEFRAME = 5
    SENT_GOOD_BYTES_TIMEFRAME = 6

    UNACK_BYTES = 7
    CUMULATIVE_RETRANSMISSIONS = 8
    RETRANSMISSIONS = 9
    EMA_RETRANSMISSIONS = 10

    # Other Params
    THROUGHPUT = 12
    GOODPUT = 13
    EMA_THROUGHPUT = 14
    EMA_GOODPUT = 15

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
CWND_UPPER_LIMIT = 9223372036854775807
STARTING_WINDOW_SIZE = 4000
