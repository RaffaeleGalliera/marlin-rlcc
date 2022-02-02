# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
"""Client and server classes corresponding to protobuf-defined services."""
import grpc

from protos import congestion_control_pb2 as protos_dot_congestion__control__pb2


class CongestionControlStub(object):
    """Interface exported by the server
    """

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.OptimizeCongestionControl = channel.stream_stream(
                '/congestioncontrol.CongestionControl/OptimizeCongestionControl',
                request_serializer=protos_dot_congestion__control__pb2.TransmissionStatus.SerializeToString,
                response_deserializer=protos_dot_congestion__control__pb2.Action.FromString,
                )


class CongestionControlServicer(object):
    """Interface exported by the server
    """

    def OptimizeCongestionControl(self, request_iterator, context):
        """Define a Bidirectional streaming

        Accept a stream of TransmissionStatuses sent while the optimal action
        is waiting to be computed other TransmissionStatuses are recieved
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_CongestionControlServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'OptimizeCongestionControl': grpc.stream_stream_rpc_method_handler(
                    servicer.OptimizeCongestionControl,
                    request_deserializer=protos_dot_congestion__control__pb2.TransmissionStatus.FromString,
                    response_serializer=protos_dot_congestion__control__pb2.Action.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'congestioncontrol.CongestionControl', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))


 # This class is part of an EXPERIMENTAL API.
class CongestionControl(object):
    """Interface exported by the server
    """

    @staticmethod
    def OptimizeCongestionControl(request_iterator,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.stream_stream(request_iterator, target, '/congestioncontrol.CongestionControl/OptimizeCongestionControl',
            protos_dot_congestion__control__pb2.TransmissionStatus.SerializeToString,
            protos_dot_congestion__control__pb2.Action.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)
