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

    LAST_RTT = 12
    MIN_RTT = 13
    MAX_RTT = 14
    SRTT = 15
    VAR_RTT = 16

    TIMESTAMP = 17
    FINISHED = 18

    ACKED_BYTES_TIMEFRAME = 19


class Statistic(Enum):
    LAST = 1
    MEAN = 2
    STD = 3
    MIN = 4
    MAX = 5
    EMA = 6
    DIFF = 7


class State(Enum):
    # From Mockets
    CURR_WINDOW_SIZE = 1

    SENT_BYTES_TIMEFRAME = 5
    SENT_GOOD_BYTES_TIMEFRAME = 6

    UNACK_BYTES = 7
    RETRANSMISSIONS = 9

    LAST_RTT = 12
    MIN_RTT = 13
    MAX_RTT = 14
    SRTT = 15
    VAR_RTT = 16

    ACKED_BYTES_TIMEFRAME = 19

    # Other Params
    THROUGHPUT = 101
    GOODPUT = 102

    PACKETS_TRANSMITTED = 103

MAXIMUM_SEGMENT_SIZE = None
# Increment/Decrement in % to be applied to the cwnd
ALPHA = 1 / 8  # Alfa for EMA
GRPC_FLOAT_UPPER_LIMIT = 100000
CWND_UPPER_LIMIT_BYTES = 150000
LINK_BANDWIDTH_KB = 150
PACKET_SIZE_KB = 1.444
UNIT_FACTOR = 1000
