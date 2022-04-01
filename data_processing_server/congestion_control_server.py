"""Implementation of the Congestion Control Server"""

from __future__ import print_function
import os
import queue
import asyncio
import logging
from typing import AsyncIterable, Optional, Union

import numpy as np
import time
import grpc
from protos import congestion_control_pb2, congestion_control_pb2_grpc
from multiprocessing import Queue


class CongestionControlService(
    congestion_control_pb2_grpc.CongestionControlServicer):
    """Implements methods for Communication during the Congestion Control"""

    def __init__(self, action_queue: Queue, state_queue: Queue):
        self._action_queue = action_queue
        self._state_queue = state_queue

    # Main async coroutine for Bidirectional CongestionControl communication
    # with JMockets
    async def OptimizeCongestionControl(self,
                                        request_iterator: AsyncIterable[
                                            congestion_control_pb2.Parameter],
                                        unused_context) -> AsyncIterable[
        congestion_control_pb2.Action]:

        parameter = dict()
        async for status in request_iterator:
            # Run the I/O blocking Queue communication with Marlin
            # Environment in a different thread and wait for response
            loop = asyncio.get_event_loop()
            logging.debug("GRPC SERVER - Sending message...")
            parameter = {
                'value': status.value,
                'parameter_type': status.parameter_type,
                'timestamp': status.timestamp
            }
            await loop.run_in_executor(None, self._state_queue.put, parameter)

            try:
                action = await loop.run_in_executor(None,
                                                    lambda:
                                                    self._action_queue.get(
                                                        block=False))

            except queue.Empty:
                logging.debug("GRPC SERVER - Action not ready, continuing...")
                pass
            else:
                logging.debug(f"GRPC SERVER - Action ready, sending {action} "
                              f"to "
                              f"Mockets")
                yield congestion_control_pb2.Action(cwnd_update=action)


async def serve(action_queue: Queue, state_queue: Queue) -> None:
    server = grpc.aio.server()
    congestion_control_pb2_grpc.add_CongestionControlServicer_to_server(
        CongestionControlService(action_queue, state_queue),
        server
    )
    server.add_insecure_port('[::]:50051')
    logging.info('SERVER - Listening...')
    await server.start()
    await server.wait_for_termination()


def run(action_queue: Queue,
        state_queue: Queue) -> None:
    logging.basicConfig(level=logging.DEBUG)
    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    loop.run_until_complete(
        serve(action_queue, state_queue))
