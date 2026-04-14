"""Core Serializer class — the public API."""

from __future__ import annotations

import threading
from typing import Any, TypeVar

import msgspec

from serializer._dispatch import TypeCategory, classify_type
from serializer._exceptions import DeserializeError, SerializeError
from serializer._pack import PackedResult, reconstruct_value, resolve_tag
from serializer._pydantic import deserialize_pydantic, pydantic_enc_hook

T = TypeVar("T")

_encoder = msgspec.msgpack.Encoder(enc_hook=pydantic_enc_hook)

_PYDANTIC_SENTINEL = object()

_decoder_cache: dict[type, msgspec.msgpack.Decoder[Any] | object] = {}
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
    def pack(obj: Any, *, tag: str | None = None) -> bytes:
        """Serialize an object with a self-describing type tag.

        Encodes the object as a msgpack array ``[tag, data]`` where ``tag``
        identifies the type for later reconstruction via :meth:`unpack`.

        For stdlib types, the tag is the type name (e.g. ``"int"``,
        ``"datetime"``). For custom types (Pydantic, dataclass, Struct),
        the tag is the fully-qualified class name.

        Args:
            obj: The object to serialize.
            tag: Optional override tag. Must not collide with reserved
                stdlib tag names.

        Raises:
            SerializeError: If the object cannot be serialized or the
                tag collides with a reserved stdlib tag.
        """
        try:
            resolved_tag = resolve_tag(obj, tag)
            return _encode([resolved_tag, obj])
        except SerializeError:
            raise
        except Exception as exc:
            raise SerializeError(
                f"Failed to pack object of type {type(obj).__qualname__!r}: {exc}"
            ) from exc

    @staticmethod
    def unpack(data: bytes) -> PackedResult:
        """Deserialize self-describing packed bytes.

        Decodes a ``[tag, data]`` msgpack array and reconstructs the value
        based on the type tag. Stdlib types are automatically reconstructed;
        custom types are returned as raw decoded data with metadata.

        Returns:
            A :class:`PackedResult` with the value, type name, and
            ``is_custom`` flag.

        Raises:
            DeserializeError: If the data is corrupt, not in the expected
                format, or the tag/data combination is invalid.
        """
        try:
            raw = msgspec.msgpack.decode(data)
        except Exception as exc:
            raise DeserializeError(
                f"Failed to decode packed data: {exc}"
            ) from exc

        if not isinstance(raw, list) or len(raw) != 2:
            raise DeserializeError(
                "Expected a [tag, data] array, got "
                f"{type(raw).__name__} with {len(raw) if isinstance(raw, list) else 'N/A'} elements"
            )

        tag_value, payload = raw
        if not isinstance(tag_value, str):
            raise DeserializeError(
                f"Tag must be a string, got {type(tag_value).__name__!r}"
            )

        try:
            return reconstruct_value(tag_value, payload)
        except (SerializeError, DeserializeError):
            raise
        except Exception as exc:
            raise DeserializeError(
                f"Failed to reconstruct value for tag {tag_value!r}: {exc}"
            ) from exc

    @staticmethod
    def deserialize(data: bytes, target_type: type[T]) -> T:
        """Deserialize MessagePack bytes into the specified target type.

        For Pydantic models, decodes to dict then reconstructs via model_validate().
        For all other types, uses a cached msgspec Decoder for maximum performance.
        """
        try:
            # Hot path: try/except is faster than .get() for cache hits
            try:
                decoder = _decoder_cache[target_type]
            except KeyError:
                # Cold path: classify and cache (once per type)
                category = classify_type(target_type)
                if category == TypeCategory.PYDANTIC:
                    with _decoder_lock:
                        _decoder_cache[target_type] = _PYDANTIC_SENTINEL
                    return deserialize_pydantic(data, target_type)  # type: ignore[return-value]

                decoder = msgspec.msgpack.Decoder(type=target_type)
                with _decoder_lock:
                    _decoder_cache[target_type] = decoder
                return decoder.decode(data)  # type: ignore[return-value]

            # Hot path continues: check for Pydantic sentinel
            if decoder is _PYDANTIC_SENTINEL:
                return deserialize_pydantic(data, target_type)  # type: ignore[return-value]
            return decoder.decode(data)  # type: ignore[return-value]
        except (SerializeError, DeserializeError):
            raise
        except Exception as exc:
            raise DeserializeError(
                f"Failed to deserialize into {target_type.__qualname__!r}: {exc}"
            ) from exc
