# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: protos/congestion_control.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x1fprotos/congestion_control.proto\x12\x11\x63ongestioncontrol\"\x96\x03\n\x12\x43ommunicationState\x12\x18\n\x10\x63urr_window_size\x18\x01 \x01(\x03\x12\x1d\n\x15\x63umulative_sent_bytes\x18\x02 \x01(\x03\x12\x1c\n\x14\x63umulative_rcv_bytes\x18\x03 \x01(\x03\x12\"\n\x1a\x63umulative_sent_good_bytes\x18\x04 \x01(\x03\x12\x1c\n\x14sent_bytes_timeframe\x18\x05 \x01(\x03\x12!\n\x19sent_good_bytes_timeframe\x18\x06 \x01(\x03\x12\x13\n\x0bunack_bytes\x18\x07 \x01(\x03\x12\x17\n\x0fretransmissions\x18\x08 \x01(\x03\x12\x1e\n\x16\x63umulative_packet_loss\x18\t \x01(\x03\x12\x10\n\x08last_rtt\x18\n \x01(\x03\x12\x0f\n\x07min_rtt\x18\x0b \x01(\x03\x12\x0f\n\x07max_rtt\x18\x0c \x01(\x03\x12\x0c\n\x04srtt\x18\r \x01(\x02\x12\x0f\n\x07var_rtt\x18\x0e \x01(\x02\x12\x11\n\ttimestamp\x18\x0f \x01(\x03\x12\x10\n\x08\x66inished\x18\x10 \x01(\x08\"\x1d\n\x06\x41\x63tion\x12\x13\n\x0b\x63wnd_update\x18\x01 \x01(\x03\x32x\n\x11\x43ongestionControl\x12\x63\n\x19OptimizeCongestionControl\x12%.congestioncontrol.CommunicationState\x1a\x19.congestioncontrol.Action\"\x00(\x01\x30\x01\x42\x1a\x42\x16\x43ongestionControlProtoP\x01\x62\x06proto3')



_COMMUNICATIONSTATE = DESCRIPTOR.message_types_by_name['CommunicationState']
_ACTION = DESCRIPTOR.message_types_by_name['Action']
CommunicationState = _reflection.GeneratedProtocolMessageType('CommunicationState', (_message.Message,), {
  'DESCRIPTOR' : _COMMUNICATIONSTATE,
  '__module__' : 'protos.congestion_control_pb2'
  # @@protoc_insertion_point(class_scope:congestioncontrol.CommunicationState)
  })
_sym_db.RegisterMessage(CommunicationState)

Action = _reflection.GeneratedProtocolMessageType('Action', (_message.Message,), {
  'DESCRIPTOR' : _ACTION,
  '__module__' : 'protos.congestion_control_pb2'
  # @@protoc_insertion_point(class_scope:congestioncontrol.Action)
  })
_sym_db.RegisterMessage(Action)

_CONGESTIONCONTROL = DESCRIPTOR.services_by_name['CongestionControl']
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  DESCRIPTOR._serialized_options = b'B\026CongestionControlProtoP\001'
  _COMMUNICATIONSTATE._serialized_start=55
  _COMMUNICATIONSTATE._serialized_end=461
  _ACTION._serialized_start=463
  _ACTION._serialized_end=492
  _CONGESTIONCONTROL._serialized_start=494
  _CONGESTIONCONTROL._serialized_end=614
# @@protoc_insertion_point(module_scope)
