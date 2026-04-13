"""Pydantic encoding and decoding support for the serializer."""

from __future__ import annotations

from typing import Any

from serializer._dispatch import (
    PydanticStrategy,
    _pydantic_strategy_cache,
    classify_type,
)

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
        # Fast path: check strategy cache directly (avoids classify_type overhead)
        strategy = _pydantic_strategy_cache.get(tp)
        if strategy is None:
            classify_type(tp)
            strategy = _pydantic_strategy_cache.get(tp, PydanticStrategy.DICT)

        if strategy is PydanticStrategy.MODEL_DUMP:
            return obj.model_dump(mode="python")
        return obj.__dict__

    raise TypeError(
        f"Cannot serialize object of type {type(obj).__qualname__!r}. "
        "Only Pydantic BaseModels, msgspec Structs, dataclasses, "
        "and msgspec-native types are supported."
    )


def convert_pydantic_to_dict(obj: Any) -> dict[str, Any]:
    """Convert a Pydantic model to a dict for serialization.

    Used by Serializer.serialize() to pre-convert before encoding,
    avoiding the C→Python→C enc_hook round-trip overhead.
    """
    tp = type(obj)
    strategy = _pydantic_strategy_cache.get(tp)
    if strategy is None:
        classify_type(tp)
        strategy = _pydantic_strategy_cache.get(tp, PydanticStrategy.DICT)

    if strategy is PydanticStrategy.MODEL_DUMP:
        return obj.model_dump(mode="python")
    return obj.__dict__


def deserialize_pydantic(data: bytes, target_type: type) -> Any:
    """Deserialize MessagePack bytes into a Pydantic model.

    Decodes to a raw dict via msgspec, then reconstructs the model
    using model_validate() for correctness guarantees.
    """
    import msgspec

    decoded = msgspec.msgpack.decode(data)
    return target_type.model_validate(decoded)
