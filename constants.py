"""
Declares constant used for actions and mockets parameters
"""

MAXIMUM_SEGMENT_SIZE = None
# Increment/Decrement in % to be applied to the cwnd
ACTIONS = (1, 0.33, 0.05, -0.05, -0.33, 0)
STATE = ['lrtt', 'rtt_min', 'srtt', 'rtt_var', 'cwnd_bytes', 'sent_bytes',
         'received_bytes', 'acked_bytes', 'inflight_bytes', 'writable_bytes',
         'throughput']
ALPHA = 1 / 8  # Alfa for Smoother RTT calc
BETA = 1 / 4  # Beta for RTT Var
