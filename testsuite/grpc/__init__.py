"""gRPC client for Kuadrant testsuite"""

import grpc
from grpc import StatusCode
from google.protobuf.json_format import MessageToDict
from google.protobuf.message_factory import GetMessageClass

from testsuite.httpx import ResultList
from testsuite.backend.grpc import grpcbin_pb2

SERVICE_DESCRIPTOR = grpcbin_pb2.DESCRIPTOR.services_by_name["GRPCBin"]


class GRPCResult:
    """Result from a gRPC request"""

    def __init__(self, code, error=None, response=None):
        self.code = code
        self.error = error
        self.response = response

    @property
    def status_code(self):
        """Returns gRPC status code"""
        return self.code

    def json(self):
        """Returns response as a dictionary"""
        if self.response is None:
            return None
        return MessageToDict(self.response, preserving_proto_field_name=True)

    def __str__(self):
        if self.error is None:
            return f"GRPCResult[code={self.code}]"
        return f"GRPCResult[code={self.code}, error={self.error.details()}]"


class GRPCClient:
    """gRPC client for making unary calls"""

    def __init__(self, host, *, hostname=None):
        options = []
        if hostname:
            options.append(("grpc.default_authority", hostname))
        self.channel = grpc.insecure_channel(host, options=options)

    def call(self, method, *, service="/grpcbin.GRPCBin", auth=None, headers=None):
        """Makes a unary gRPC call to the given method on the service."""
        metadata = []
        if auth:
            metadata.append(("authorization", f"Bearer {auth.token.access_token}"))
        if headers:
            metadata.extend((k.lower(), v) for k, v in headers.items())
        method = method.lstrip("/")
        make_call = self.channel.unary_unary(
            service + "/" + method,
            request_serializer=grpcbin_pb2.EmptyMessage.SerializeToString,
            response_deserializer=GetMessageClass(SERVICE_DESCRIPTOR.methods_by_name[method].output_type).FromString,
        )
        try:
            response = make_call(grpcbin_pb2.EmptyMessage(), metadata=metadata or None, timeout=10)
            return GRPCResult(StatusCode.OK, response=response)
        except grpc.RpcError as e:
            return GRPCResult(e.code(), error=e)  # pylint: disable=no-member

    def call_many(self, method, count, *, auth=None, **kwargs) -> ResultList:
        """Send multiple gRPC requests."""
        responses = ResultList()
        for _ in range(count):
            responses.append(self.call(method, auth=auth, **kwargs))
        return responses

    def close(self):
        """Close the gRPC channel"""
        self.channel.close()
