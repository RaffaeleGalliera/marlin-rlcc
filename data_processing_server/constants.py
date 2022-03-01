"""
Declares constant used for actions and mockets parameters
"""

MAXIMUM_SEGMENT_SIZE = None
# Increment/Decrement in % to be applied to the cwnd
ACTIONS = (1, 0.33, 0.05, -0.05, -0.33, 0)
ALPHA = 1 / 8  # Alfa for Smoother RTT calc
