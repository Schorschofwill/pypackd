"""Unified Python serializer with msgspec MessagePack backend."""

from serializer._core import Serializer
from serializer._exceptions import DeserializeError, SerializeError, SerializerError
from serializer._pack import PackedResult

__all__ = [
    "Serializer",
    "PackedResult",
    "SerializerError",
    "SerializeError",
    "DeserializeError",
]
