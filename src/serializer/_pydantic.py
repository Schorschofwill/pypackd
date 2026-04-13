"""Pydantic encoding and decoding support for the serializer."""

from __future__ import annotations

from typing import Any

from serializer._dispatch import (
    PydanticStrategy,
    classify_type,
    get_pydantic_strategy,
    TypeCategory,
)


def pydantic_enc_hook(obj: Any) -> Any:
    """enc_hook for msgspec Encoder that handles Pydantic BaseModels.

    Returns a dict representation that msgspec can natively encode.
    Nested Pydantic models are handled automatically by msgspec calling
    this hook again for each non-native value.
    """
    from pydantic import BaseModel

    if isinstance(obj, BaseModel):
        tp = type(obj)
        classify_type(tp)
        strategy = get_pydantic_strategy(tp)

        if strategy == PydanticStrategy.MODEL_DUMP:
            return obj.model_dump(mode="python")
        else:
            return obj.__dict__

    raise TypeError(
        f"Cannot serialize object of type {type(obj).__qualname__!r}. "
        "Only Pydantic BaseModels, msgspec Structs, dataclasses, "
        "and msgspec-native types are supported."
    )


def deserialize_pydantic(data: bytes, target_type: type) -> Any:
    """Deserialize MessagePack bytes into a Pydantic model.

    Decodes to a raw dict via msgspec, then reconstructs the model
    using model_validate() for correctness guarantees.
    """
    import msgspec

    decoded = msgspec.msgpack.decode(data)
    return target_type.model_validate(decoded)
