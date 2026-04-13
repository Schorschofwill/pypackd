"""Pydantic encoding and decoding support for the serializer."""

from __future__ import annotations

from typing import Any, TypeVar

import msgspec

from serializer._dispatch import (
    PydanticStrategy,
    classify_type,
    get_pydantic_strategy,
)
from serializer._exceptions import DeserializeError

T = TypeVar("T")

# Cache the BaseModel check to avoid repeated imports
_BaseModel: type | None = None


def _get_base_model() -> type:
    global _BaseModel
    if _BaseModel is None:
        from pydantic import BaseModel
        _BaseModel = BaseModel
    return _BaseModel


def pydantic_enc_hook(obj: Any) -> Any:
    """enc_hook for msgspec Encoder that handles Pydantic BaseModels.

    Returns a dict representation that msgspec can natively encode.
    Nested Pydantic models are handled automatically by msgspec calling
    this hook again for each non-native value.
    """
    BM = _get_base_model()
    if isinstance(obj, BM):
        tp = type(obj)
        classify_type(tp)
        strategy = get_pydantic_strategy(tp)

        if strategy is PydanticStrategy.MODEL_DUMP:
            return obj.model_dump(mode="python")
        return obj.__dict__

    raise TypeError(
        f"Cannot serialize object of type {type(obj).__qualname__!r}. "
        "Only Pydantic BaseModels, msgspec Structs, dataclasses, "
        "and msgspec-native types are supported."
    )


def deserialize_pydantic(data: bytes, target_type: type[T]) -> T:
    """Deserialize MessagePack bytes into a Pydantic model.

    Decodes to a raw dict via msgspec, then reconstructs the model
    using model_validate() for correctness guarantees.
    """
    try:
        decoded = msgspec.msgpack.decode(data)
        return target_type.model_validate(decoded)  # type: ignore[return-value]
    except Exception as exc:
        raise DeserializeError(
            f"Failed to deserialize into {target_type.__qualname__!r}: {exc}"
        ) from exc
