"""Implementation of the Congestion Control Server"""

import asyncio
import logging
from typing import AsyncIterable, Optional, Union
from functools import wraps, partial
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

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
def make_action(parameter: int) -> congestion_control_pb2.Action:
    print("Sending action to take")
    return congestion_control_pb2.Action(cwnd_update=parameter)


# Just a placeholder for the time being
def compute_statistics(parameter_1: int,
                       parameter_2: int,
                       parameter_3: int) -> None:
    print(
        f"Received param_1 {parameter_1} param_2 {parameter_2} param_3"
        f" {parameter_3}")


def get_prediction(action_queue: Queue):
    action = action_queue.get()
    print(action)
    return action


def put_state(state_queue: Queue):
    state_queue.put(1)


class CongestionControlService(
    congestion_control_pb2_grpc.CongestionControlServicer):
    """Implements methods for Communication during the Congestion Control"""

    def __init__(self, action_queue, state_queue):
        self._action_queue = action_queue
        self._state_queue = state_queue

    async def OptimizeCongestionControl(self,
                                        request_iterator: AsyncIterable[
                                            congestion_control_pb2.TransmissionStatus],
                                        unused_context) -> AsyncIterable[
        congestion_control_pb2.Action]:
        async for status in request_iterator:
            await asyncio.sleep(0.1)
            compute_statistics(
                status.parameter_1,
                status.parameter_2,
                status.parameter_3
            )

            await asyncio.get_event_loop().run_in_executor(None, put_state,
                                                           self._state_queue)
            prediction = await asyncio.get_event_loop().run_in_executor(None,
                                                                        get_prediction,
                                                                        self._action_queue)
            yield make_action(prediction)


async def serve(action_queue: Queue, state_queue: Queue) -> None:
    server = grpc.aio.server()
    congestion_control_pb2_grpc.add_CongestionControlServicer_to_server(
        CongestionControlService(action_queue, state_queue),
        server
    )
    server.add_insecure_port('[::]:50051')
    print('Listening...')
    await server.start()
    await server.wait_for_termination()


def run(action_queue: Queue,
        state_queue: Queue) -> None:
    logging.basicConfig()
    asyncio.get_event_loop().run_until_complete(
        serve(action_queue, state_queue))
