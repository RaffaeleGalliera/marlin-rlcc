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
    RETRANSMISSIONS = 8
    EMA_RETRANSMISSIONS = 9
    WRITABLE_BYTES = 10

    # Other Params

    THROUGHPUT = 11
    GOODPUT = 12
    EMA_THROUGHPUT = 13
    EMA_GOODPUT= 14

    LAST_RTT = 15
    MIN_RTT = 16
    MAX_RTT = 17
    SRTT = 18
    VAR_RTT = 19

    TIMESTAMP = 20
    FINISHED = 21


class State(Enum):
    # From Mockets
    CURR_WINDOW_SIZE = 1

    SENT_BYTES = 2
    RCV_BYTES = 3
    SENT_GOOD_BYTES = 4
    SENT_BYTES_TIMEFRAME = 5
    SENT_GOOD_BYTES_TIMEFRAME = 6

    UNACK_BYTES = 7
    RETRANSMISSIONS = 8
    EMA_RETRANSMISSIONS = 9

    # Other Params
    THROUGHPUT = 11
    GOODPUT = 12
    EMA_THROUGHPUT = 13
    EMA_GOODPUT = 14

    LAST_RTT = 15
    MIN_RTT = 16
    MAX_RTT = 17
    SRTT = 18
    VAR_RTT = 19


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
