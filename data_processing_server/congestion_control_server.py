"""Implementation of the Congestion Control Server"""

from __future__ import print_function
import os

os.environ['PYTHONASYNCIODEBUG'] = '1'
import asyncio
import logging
from typing import AsyncIterable, Optional, Union
from functools import wraps, partial
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

import numpy as np
import time
import grpc
from protos import congestion_control_pb2, congestion_control_pb2_grpc
from multiprocessing import Queue


def background_awaitable(
        func=None,
        *,
        loop: Optional[asyncio.AbstractEventLoop] = None,
        executor: Optional[
            Union[ThreadPoolExecutor, ProcessPoolExecutor]] = None
):
    """
    Background awaitable decorator.
    Wrap any synchronous method or function with this
    decorator for non-blocking background execution.
    For fire-and-forget, simply call the function and method.
    It will execute in the background in a non-blocking fashion.
    To wait for the result (non-blocking), simply await the Future.
    You can await future objects at later points in your program to
    simply retrieve the result or handle any exceptions.
    Note: fire-and-forget behavior does not raise Exceptions on
    the main event loop. Awaiting the future does.
    """
    # use partial func to make args optional
    if func is None:
        return partial(background_awaitable, loop=loop, executor=executor)

    # get or create event loop if None
    if loop is None:
        loop = asyncio.get_event_loop()

    @wraps(func)
    def wrapper(*args, **kwargs) -> asyncio.Future:
        # use non-local loop
        nonlocal loop
        # self heal loop on close
        if loop.is_closed():
            loop = asyncio.get_event_loop()
        # bind kwargs and run in passed executor ->
        # if None, will run in asyncio loop's default executor
        wrapped_func = partial(func, **kwargs)
        awaitable = loop.run_in_executor(
            executor, wrapped_func, *args
        )
        return awaitable

    return wrapper


# Just a placeholder for the time being
def compute_statistics(cumulative_received_bytes: int,
                       cumulative_sent_bytes: int,
                       cumulative_sent_good_bytes: int,
                       current_window_size: int,
                       last_receive_timestamp: int,
                       unack_bytes: int,
                       retransmissions: int,
                       chunk_rtt: int,
                       min_acknowledge_time: int) -> None:
    print(f"SERVER RECEIVED - Cumulative Receive bytes:"
          f" {cumulative_received_bytes}")
    print(f"SERVER RECEIVED - Cumulative Sent bytes:"
          f" {cumulative_sent_bytes}")
    print(f"SERVER RECEIVED - Cumulative Sent good bytes:"
          f" {cumulative_sent_good_bytes}")
    print(f"SERVER RECEIVED - Current Window Size: {current_window_size}")
    print(f"SERVER RECEIVED - Last Received Timestamp (Micro):"
          f" {last_receive_timestamp}")
    print(f"SERVER RECEIVED - Unack Bytes: {unack_bytes}")
    print(f"SERVER RECEIVED - Retransmissions: {retransmissions}")
    print(f"SERVER RECEIVED - Chunk RTT (Micro): {chunk_rtt}")
    print(f"SERVER RECEIVED - Min Ack Time (Micro): {min_acknowledge_time}")


class CongestionControlService(
    congestion_control_pb2_grpc.CongestionControlServicer):
    """Implements methods for Communication during the Congestion Control"""

    def __init__(self, action_queue, state_queue):
        self._action_queue = action_queue
        self._state_queue = state_queue
        self._message_n = 0

    def _send_state(self, parameter):
        self._state_queue.put(parameter)

    def _get_action(self):
        return self._action_queue.get()

    # Sends an action reading and writing on the two pipes shared with the
    # main process
    def _make_action(self,
                     parameters: np.array) -> congestion_control_pb2.Action:
        self._send_state(parameters)
        action = self._get_action()
        print("SERVER - Received Action: ", action)
        return congestion_control_pb2.Action(cwnd_update=action)

    # Main async coroutine for Bidirectional CongestionControl communication
    # with JMockets
    async def OptimizeCongestionControl(self,
                                        request_iterator: AsyncIterable[
                                            congestion_control_pb2.TransmissionStatus],
                                        unused_context) -> AsyncIterable[
        congestion_control_pb2.Action]:
        async for status in request_iterator:
            compute_statistics(
                status.cumulative_received_bytes,
                status.cumulative_sent_bytes,
                status.cumulative_sent_good_bytes,
                status.current_window_size,
                status.last_receive_time,
                status.unack_bytes,
                status.retransmissions,
                status.chunk_rtt,
                status.min_acknowledge_time
            )
            parameters = np.array([
                status.cumulative_received_bytes,
                status.cumulative_sent_bytes,
                status.cumulative_sent_good_bytes,
                status.current_window_size,
                status.last_receive_time,
                status.unack_bytes,
                status.retransmissions,
                status.chunk_rtt,
                status.min_acknowledge_time
            ])
            self._message_n += 1

            if self._message_n == 3:
                self._message_n = 0

                # Run the I/O blocking Queue communication with Marlin
                # Environment in a different thread and wait for response
                action = await asyncio.get_event_loop(). \
                    run_in_executor(None,
                                    self._make_action,
                                    parameters)
                yield action


async def serve(action_queue: Queue, state_queue: Queue) -> None:
    server = grpc.aio.server()
    congestion_control_pb2_grpc.add_CongestionControlServicer_to_server(
        CongestionControlService(action_queue, state_queue),
        server
    )
    server.add_insecure_port('[::]:50051')
    print('SERVER - Listening...')
    await server.start()
    await server.wait_for_termination()


def run(action_queue: Queue,
        state_queue: Queue) -> None:
    logging.basicConfig(level=logging.DEBUG)
    loop = asyncio.new_event_loop()
    loop.set_debug(True)
    asyncio.set_event_loop(loop)
    loop.run_until_complete(
        serve(action_queue, state_queue))
