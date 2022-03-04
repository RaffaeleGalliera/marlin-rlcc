"""
Declares constant used for actions and mockets parameters
"""

MAXIMUM_SEGMENT_SIZE = None
# Increment/Decrement in % to be applied to the cwnd
ACTIONS = (1, 0.33, 0.05, -0.05, -0.33, 0)
STATE = ['lrtt', 'rtt_min', 'srtt', 'cwnd_bytes', 'sent_bytes',
         'received_bytes', 'inflight_bytes', 'writable_bytes', 'throughput']
ALPHA = 1 / 8  # Alfa for Smoother RTT calc
