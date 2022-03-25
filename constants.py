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
    INFLIGHT_BYTES = 9
    ACKED_BYTES = 10
    SENT_BYTES_TIMEFRAME = 11
    ACKED_BYTES_IN_TIMEFRAME = 12
    THROUGHPUT = 13
    GOODPUT = 14
    EMA_THROUGHPUT = 15
    LAST_RTT = 16
    MIN_RTT = 17
    SRTT = 18
    VAR_RTT = 19



MAXIMUM_SEGMENT_SIZE = None
# Increment/Decrement in % to be applied to the cwnd
ACTIONS = (1, 0.33, 0.05, -0.05, -0.33, 0)
STATE = ['lrtt', 'rtt_min', 'srtt', 'rtt_var', 'cwnd_bytes', 'sent_bytes',
         'received_bytes', 'acked_bytes', 'inflight_bytes', 'writable_bytes',
         'throughput', 'goodput']
ALPHA = 1 / 8  # Alfa for Smoother RTT calc
BETA = 1 / 4  # Beta for RTT Var
