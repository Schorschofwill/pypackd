"""Pydantic encoding and decoding support for the serializer."""

from __future__ import annotations

from typing import Any, TypeVar

import msgspec

from serializer._dispatch import (
    PydanticStrategy,
    TypeCategory,
    _pydantic_strategy_cache,
    classify_type,
)
from serializer._exceptions import DeserializeError

T = TypeVar("T")


def pydantic_enc_hook(obj: Any) -> Any:
    """enc_hook for msgspec Encoder that handles Pydantic BaseModels.

    Returns a dict representation that msgspec can natively encode.
    Nested Pydantic models are handled automatically by msgspec calling
    this hook again for each non-native value.
    """
    tp = type(obj)

    # Hot path: single dict lookup on existing strategy cache
    try:
        strategy = _pydantic_strategy_cache[tp]
    except KeyError:
        # Cold path: classify type (populates both _type_cache and
        # _pydantic_strategy_cache for Pydantic types)
        category = classify_type(tp)
        if category is not TypeCategory.PYDANTIC:
            raise TypeError(
                f"Cannot serialize object of type {tp.__qualname__!r}. "
                "Only Pydantic BaseModels, msgspec Structs, dataclasses, "
                "and msgspec-native types are supported."
            )
        strategy = _pydantic_strategy_cache[tp]

    if strategy is PydanticStrategy.MODEL_DUMP:
        return obj.model_dump(mode="python")
    return obj.__dict__


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
