"""Self-describing pack/unpack support with type-tagged serialization."""

from __future__ import annotations

import threading
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import msgspec

from serializer._exceptions import DeserializeError, SerializeError

# --- PackedResult -----------------------------------------------------------


class PackedResult(msgspec.Struct, frozen=True):
    """Result of an unpack() operation.

    Attributes:
        value: The deserialized value. For stdlib types, the reconstructed
            Python type; for custom types, the raw msgpack-decoded data.
        type_name: The type tag string (e.g. "int", "datetime",
            "myapp.models.MyModel").
        is_custom: True when the type tag is not a known stdlib type,
            indicating the caller must reconstruct the object themselves.
    """

    value: Any
    type_name: str
    is_custom: bool


# --- Tag registry ------------------------------------------------------------

# The 17 stdlib types supported by pack/unpack.
STDLIB_TYPES: frozenset[type] = frozenset(
    {
        str,
        int,
        float,
        bool,
        type(None),
        bytes,
        list,
        dict,
        tuple,
        set,
        frozenset,
        datetime,
        date,
        time,
        timedelta,
        UUID,
        Decimal,
    }
)

# Reserved tag strings — one per stdlib type via type.__name__.
RESERVED_TAGS: frozenset[str] = frozenset(t.__name__ for t in STDLIB_TYPES)

# --- Three-tier reconstruction ------------------------------------------------

# Tier 1: identity types — untyped msgspec decode returns the correct Python
# type directly. No reconstruction needed.
_IDENTITY_TAGS: frozenset[str] = frozenset(
    {"str", "int", "float", "bool", "NoneType", "bytes", "list", "dict"}
)

# Tier 2: container-coerced types — untyped decode returns list, coerce via
# the container constructor.
_CONTAINER_COERCE: dict[str, type] = {
    "tuple": tuple,
    "set": set,
    "frozenset": frozenset,
}

# Tier 3: string-decoded types — untyped decode returns str, reconstruct via
# re-encode + typed Decoder(type=T).
_TYPED_DECODE_MAP: dict[str, type] = {
    "datetime": datetime,
    "date": date,
    "time": time,
    "timedelta": timedelta,
    "UUID": UUID,
    "Decimal": Decimal,
}

# --- Typed decoder cache for string-decoded reconstruction -------------------
# Separate from _core._decoder_cache to avoid _PYDANTIC_SENTINEL complexity
# and to keep the _core → _pack dependency direction clean.

_typed_decoder_cache: dict[type, msgspec.msgpack.Decoder[Any]] = {}
_typed_decoder_lock = threading.Lock()

# Plain encoder for re-encoding string values — no enc_hook needed since
# the value is always a plain string.
_str_encoder = msgspec.msgpack.Encoder()
_str_encode = _str_encoder.encode


# --- Reconstruction helpers --------------------------------------------------


def reconstruct_value(tag: str, raw_value: Any) -> PackedResult:
    """Reconstruct a value based on its type tag.

    Routes through the three-tier dispatch:
    1. Identity tags → return as-is
    2. Container-coerced tags → apply constructor
    3. Typed-decode tags → re-encode string, typed decode
    4. Unknown tags → custom type (is_custom=True)
    """
    if tag in _IDENTITY_TAGS:
        return PackedResult(value=raw_value, type_name=tag, is_custom=False)

    if tag in _CONTAINER_COERCE:
        coerced = _CONTAINER_COERCE[tag](raw_value)
        return PackedResult(value=coerced, type_name=tag, is_custom=False)

    if tag in _TYPED_DECODE_MAP:
        target_type = _TYPED_DECODE_MAP[tag]
        reconstructed = _typed_decode(target_type, raw_value)
        return PackedResult(value=reconstructed, type_name=tag, is_custom=False)

    # Unknown tag → custom type
    return PackedResult(value=raw_value, type_name=tag, is_custom=True)


def _typed_decode(target_type: type, raw_value: Any) -> Any:
    """Re-encode a string value and decode it with a typed Decoder."""
    try:
        decoder = _typed_decoder_cache[target_type]
    except KeyError:
        decoder = msgspec.msgpack.Decoder(type=target_type)
        with _typed_decoder_lock:
            _typed_decoder_cache[target_type] = decoder

    try:
        return decoder.decode(_str_encode(raw_value))
    except Exception as exc:
        raise DeserializeError(
            f"Failed to reconstruct {target_type.__name__!r} from tag data: {exc}"
        ) from exc


def resolve_tag(obj: Any, tag: str | None) -> str:
    """Determine the type tag for an object.

    If tag is provided, validates it doesn't collide with reserved tags.
    Otherwise, auto-detects: stdlib types get their __name__, custom types
    get their fully-qualified module.qualname.
    """
    if tag is not None:
        if tag in RESERVED_TAGS:
            raise SerializeError(
                f"Custom tag {tag!r} collides with reserved stdlib tag"
            )
        return tag

    obj_type = type(obj)
    if obj_type in STDLIB_TYPES:
        return obj_type.__name__

    # Custom type — fully-qualified name
    module = obj_type.__module__
    qualname = obj_type.__qualname__
    if not module:
        return qualname
    return f"{module}.{qualname}"
