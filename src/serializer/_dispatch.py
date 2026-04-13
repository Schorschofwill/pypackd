"""Type detection and dispatch cache for serialization paths."""

from __future__ import annotations

import enum
import threading
from typing import Any

import msgspec


class TypeCategory(enum.Enum):
    PYDANTIC = "pydantic"
    NATIVE = "native"


class PydanticStrategy(enum.Enum):
    DICT = "dict"
    MODEL_DUMP = "model_dump"


_BaseModel: type | None = None
_pydantic_available: bool | None = None


def _check_pydantic() -> bool:
    global _BaseModel, _pydantic_available
    if _pydantic_available is not None:
        return _pydantic_available
    try:
        from pydantic import BaseModel
        _BaseModel = BaseModel
        _pydantic_available = True
    except ImportError:
        _pydantic_available = False
    return _pydantic_available


def get_base_model() -> type | None:
    """Return the cached pydantic.BaseModel class, or None if pydantic is not installed."""
    _check_pydantic()
    return _BaseModel


def _is_pydantic_type(tp: type) -> bool:
    if _check_pydantic():
        return isinstance(tp, type) and issubclass(tp, _BaseModel)  # type: ignore[arg-type]
    if hasattr(tp, "model_validate") and hasattr(tp, "model_fields"):
        raise ImportError(
            f"Type {tp.__name__!r} looks like a Pydantic model but pydantic is not installed. "
            "Install it with: pip install serializer[pydantic]"
        )
    return False


def _determine_pydantic_strategy(tp: type) -> PydanticStrategy:
    has_computed = bool(getattr(tp, "model_computed_fields", None))
    config = getattr(tp, "model_config", {})
    has_extra = config.get("extra") == "allow"

    # Check for fields with exclude=True, aliases, or custom serializers
    model_fields = getattr(tp, "model_fields", {})
    has_excluded = any(
        getattr(f, "exclude", False) for f in model_fields.values()
    )
    has_alias = any(
        getattr(f, "alias", None) is not None
        or getattr(f, "serialization_alias", None) is not None
        for f in model_fields.values()
    )

    # Check for @model_serializer (top-level)
    schema = getattr(tp, "__pydantic_core_schema__", {})
    serialization = schema.get("serialization", {})
    has_custom_serializer = serialization.get("type") in (
        "function-plain",
        "function-wrap",
    )

    # Check for @field_serializer on any field (nested in field schemas)
    if not has_custom_serializer:
        fields_schema = schema.get("schema", {}).get("fields", {})
        for field_schema in fields_schema.values():
            field_ser = field_schema.get("schema", {}).get("serialization", {})
            if field_ser.get("type") in ("function-plain", "function-wrap"):
                has_custom_serializer = True
                break

    if (
        has_computed
        or has_extra
        or has_excluded
        or has_alias
        or has_custom_serializer
    ):
        return PydanticStrategy.MODEL_DUMP
    return PydanticStrategy.DICT


_type_cache: dict[type, TypeCategory] = {}
_pydantic_strategy_cache: dict[type, PydanticStrategy] = {}
_cache_lock = threading.Lock()


def classify_type(tp: type) -> TypeCategory:
    try:
        return _type_cache[tp]
    except KeyError:
        pass

    if _is_pydantic_type(tp):
        category = TypeCategory.PYDANTIC
        strategy = _determine_pydantic_strategy(tp)
        with _cache_lock:
            _type_cache[tp] = category
            _pydantic_strategy_cache[tp] = strategy
    else:
        category = TypeCategory.NATIVE
        with _cache_lock:
            _type_cache[tp] = category

    return category


def get_pydantic_strategy(tp: type) -> PydanticStrategy:
    try:
        return _pydantic_strategy_cache[tp]
    except KeyError:
        raise RuntimeError(
            f"get_pydantic_strategy called for {tp.__qualname__!r} before classify_type. "
            "Call classify_type(tp) first."
        ) from None


def classify_instance(obj: Any) -> TypeCategory:
    return classify_type(type(obj))
