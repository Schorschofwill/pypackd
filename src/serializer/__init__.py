"""Unified Python serializer with msgspec MessagePack backend."""

from serializer._core import Serializer
from serializer._exceptions import DeserializeError, SerializeError, SerializerError

__all__ = [
    "Serializer",
    "SerializerError",
    "SerializeError",
    "DeserializeError",
]
