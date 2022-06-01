"""Implementation of the Congestion Control Server"""

from __future__ import print_function
import asyncio
import logging
from typing import AsyncIterable

import grpc
from protos import congestion_control_pb2, congestion_control_pb2_grpc
from multiprocessing import Queue
from envs.utils.constants import Parameters


class CongestionControlService(congestion_control_pb2_grpc.
                               CongestionControlServicer):
    """Implements methods for Communication during the Congestion Control"""

    def __init__(self, action_queue: Queue, state_queue: Queue):
        self._action_queue = action_queue
        self._state_queue = state_queue

    # Main async coroutine for Bidirectional CongestionControl communication
    # with JMockets
    async def OptimizeCongestionControl(self,
                                        request_iterator: AsyncIterable[
                                            congestion_control_pb2.CommunicationState],
                                        unused_context) -> AsyncIterable[
                                            congestion_control_pb2.Action]:

        parameter = dict((param, 0) for param in Parameters)
        async for status in request_iterator:
            loop = asyncio.get_event_loop()

            parameter[Parameters.CURR_WINDOW_SIZE] = status.curr_window_size

            parameter[Parameters.SENT_BYTES] = status.cumulative_sent_bytes
            parameter[Parameters.RCV_BYTES] = status.cumulative_rcv_bytes
            parameter[Parameters.SENT_GOOD_BYTES] = status.cumulative_sent_good_bytes
            parameter[Parameters.SENT_BYTES_TIMEFRAME] = status.sent_bytes_timeframe
            parameter[Parameters.SENT_GOOD_BYTES_TIMEFRAME] = status.sent_good_bytes_timeframe;

            parameter[Parameters.UNACK_BYTES] = status.unack_bytes
            parameter[Parameters.CUMULATIVE_RETRANSMISSIONS] = status.cumulative_retransmissions
            parameter[Parameters.RETRANSMISSIONS] = status.retransmissions
            parameter[Parameters.EMA_RETRANSMISSIONS] = status.ema_retransmissions;

            parameter[Parameters.LAST_RTT] = status.last_rtt
            parameter[Parameters.MIN_RTT] = status.min_rtt
            parameter[Parameters.MAX_RTT] = status.max_rtt
            parameter[Parameters.SRTT] = status.srtt
            parameter[Parameters.VAR_RTT] = status.var_rtt

            parameter[Parameters.TIMESTAMP] = status.timestamp
            parameter[Parameters.FINISHED] = status.finished

            # Put in queue, note that queue is infinite aka doesn't block
            self._state_queue.put(parameter)

            action = await loop.run_in_executor(None,
                                                self._action_queue.get)

            logging.debug(f"GRPC SERVER - Action ready, sending {action} "
                              f"to Mockets")
            yield congestion_control_pb2.Action(cwnd_update=action)


async def serve(action_queue: Queue, state_queue: Queue, port: int) -> None:
    server = grpc.aio.server()
    congestion_control_pb2_grpc.add_CongestionControlServicer_to_server(
        CongestionControlService(action_queue, state_queue),
        server
    )
    server.add_insecure_port(f'[::]:{port}')
    logging.info('SERVER - Listening...')
    await server.start()
    await server.wait_for_termination()


def run(action_queue: Queue,
        state_queue: Queue,
        port: int) -> None:
    logging.basicConfig()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(
        serve(action_queue, state_queue, port))
