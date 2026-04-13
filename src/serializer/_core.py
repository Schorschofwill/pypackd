"""Core Serializer class — the public API."""

from __future__ import annotations

import threading
from typing import Any, TypeVar

import msgspec

from serializer._dispatch import TypeCategory, classify_type
from serializer._exceptions import DeserializeError, SerializeError
from serializer._pydantic import deserialize_pydantic, pydantic_enc_hook

T = TypeVar("T")

_encoder = msgspec.msgpack.Encoder(enc_hook=pydantic_enc_hook)

_decoder_cache: dict[type, msgspec.msgpack.Decoder[Any]] = {}
_decoder_lock = threading.Lock()

# Pre-resolve for hot path — avoid repeated attribute lookups
_encode = _encoder.encode


class Serializer:
    """Unified serializer with msgspec MessagePack backend.

    Provides static methods for serializing and deserializing Python objects.
    Supports all msgspec-native types plus Pydantic BaseModels transparently.

    Usage::

        data = Serializer.serialize(my_object)
        obj = Serializer.deserialize(data, MyType)
    """

    __slots__ = ()

    @staticmethod
    def serialize(obj: Any) -> bytes:
        """Serialize any supported Python object to MessagePack bytes.

        Pydantic BaseModels are handled transparently via enc_hook.
        All msgspec-native types (primitives, collections, dataclasses,
        Structs, datetime, UUID, Decimal, etc.) pass through directly.
        """
        try:
            return _encode(obj)
        except Exception as exc:
            raise SerializeError(
                f"Failed to serialize object of type {type(obj).__qualname__!r}: {exc}"
            ) from exc

    @staticmethod
    def deserialize(data: bytes, target_type: type[T]) -> T:
        """Deserialize MessagePack bytes into the specified target type.

        For Pydantic models, decodes to dict then reconstructs via model_validate().
        For all other types, uses a cached msgspec Decoder for maximum performance.
        """
        try:
            # Hot path: check decoder cache directly
            decoder = _decoder_cache.get(target_type)
            if decoder is not None:
                return decoder.decode(data)  # type: ignore[return-value]

            # Cold path: classify and cache
            category = classify_type(target_type)
            if category == TypeCategory.PYDANTIC:
                return deserialize_pydantic(data, target_type)  # type: ignore[return-value]

            decoder = msgspec.msgpack.Decoder(type=target_type)
            with _decoder_lock:
                _decoder_cache[target_type] = decoder
            return decoder.decode(data)  # type: ignore[return-value]
        except (SerializeError, DeserializeError):
            raise
        except Exception as exc:
            raise DeserializeError(
                f"Failed to deserialize into {target_type.__qualname__!r}: {exc}"
            ) from exc
