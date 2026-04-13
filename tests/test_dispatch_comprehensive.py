"""Comprehensive dispatch tests — every classification path and cache behavior."""

from __future__ import annotations

import dataclasses
from typing import NamedTuple, TypedDict
from unittest.mock import patch

import msgspec
import pydantic
import pytest

from serializer._dispatch import (
    TypeCategory,
    PydanticStrategy,
    classify_type,
    classify_instance,
    get_pydantic_strategy,
    _type_cache,
    _pydantic_strategy_cache,
)


# ── Classification of all supported types ───────────────────────────────────

class TestClassifyAllTypes:
    """Every type that the serializer supports must classify correctly."""

    # Primitives
    def test_int(self) -> None:
        assert classify_type(int) == TypeCategory.NATIVE

    def test_float(self) -> None:
        assert classify_type(float) == TypeCategory.NATIVE

    def test_str(self) -> None:
        assert classify_type(str) == TypeCategory.NATIVE

    def test_bool(self) -> None:
        assert classify_type(bool) == TypeCategory.NATIVE

    def test_nonetype(self) -> None:
        assert classify_type(type(None)) == TypeCategory.NATIVE

    def test_bytes(self) -> None:
        assert classify_type(bytes) == TypeCategory.NATIVE

    # Collections
    def test_list(self) -> None:
        assert classify_type(list) == TypeCategory.NATIVE

    def test_dict(self) -> None:
        assert classify_type(dict) == TypeCategory.NATIVE

    def test_tuple(self) -> None:
        assert classify_type(tuple) == TypeCategory.NATIVE

    def test_set(self) -> None:
        assert classify_type(set) == TypeCategory.NATIVE

    def test_frozenset(self) -> None:
        assert classify_type(frozenset) == TypeCategory.NATIVE

    # Structured
    def test_msgspec_struct(self) -> None:
        class S(msgspec.Struct):
            x: int

        assert classify_type(S) == TypeCategory.NATIVE

    def test_dataclass(self) -> None:
        @dataclasses.dataclass
        class D:
            x: int

        assert classify_type(D) == TypeCategory.NATIVE

    def test_namedtuple(self) -> None:
        class NT(NamedTuple):
            x: int

        assert classify_type(NT) == TypeCategory.NATIVE

    def test_typeddict(self) -> None:
        class TD(TypedDict):
            x: int

        assert classify_type(TD) == TypeCategory.NATIVE

    # Pydantic
    def test_pydantic_basemodel(self) -> None:
        class M(pydantic.BaseModel):
            x: int

        assert classify_type(M) == TypeCategory.PYDANTIC

    def test_pydantic_subclass(self) -> None:
        class Base(pydantic.BaseModel):
            x: int

        class Child(Base):
            y: str

        assert classify_type(Child) == TypeCategory.PYDANTIC


# ── Strategy detection for every Pydantic feature ───────────────────────────

class TestStrategyDetection:
    def test_simple_model_uses_dict(self) -> None:
        class M(pydantic.BaseModel):
            x: int

        classify_type(M)
        assert get_pydantic_strategy(M) == PydanticStrategy.DICT

    def test_computed_field(self) -> None:
        class M(pydantic.BaseModel):
            x: int

            @pydantic.computed_field  # type: ignore[prop-decorator]
            @property
            def double(self) -> int:
                return self.x * 2

        classify_type(M)
        assert get_pydantic_strategy(M) == PydanticStrategy.MODEL_DUMP

    def test_extra_allow(self) -> None:
        class M(pydantic.BaseModel):
            model_config = pydantic.ConfigDict(extra="allow")
            x: int

        classify_type(M)
        assert get_pydantic_strategy(M) == PydanticStrategy.MODEL_DUMP

    def test_extra_forbid_uses_dict(self) -> None:
        class M(pydantic.BaseModel):
            model_config = pydantic.ConfigDict(extra="forbid")
            x: int

        classify_type(M)
        assert get_pydantic_strategy(M) == PydanticStrategy.DICT

    def test_extra_ignore_uses_dict(self) -> None:
        class M(pydantic.BaseModel):
            model_config = pydantic.ConfigDict(extra="ignore")
            x: int

        classify_type(M)
        assert get_pydantic_strategy(M) == PydanticStrategy.DICT

    def test_field_exclude(self) -> None:
        class M(pydantic.BaseModel):
            public: str
            secret: str = pydantic.Field(exclude=True)

        classify_type(M)
        assert get_pydantic_strategy(M) == PydanticStrategy.MODEL_DUMP

    def test_field_alias(self) -> None:
        class M(pydantic.BaseModel):
            name: str = pydantic.Field(alias="user_name")

        classify_type(M)
        assert get_pydantic_strategy(M) == PydanticStrategy.MODEL_DUMP

    def test_field_serialization_alias(self) -> None:
        class M(pydantic.BaseModel):
            name: str = pydantic.Field(serialization_alias="userName")

        classify_type(M)
        assert get_pydantic_strategy(M) == PydanticStrategy.MODEL_DUMP

    def test_model_serializer(self) -> None:
        class M(pydantic.BaseModel):
            x: int

            @pydantic.model_serializer
            def ser(self) -> dict:
                return {"val": self.x}

        classify_type(M)
        assert get_pydantic_strategy(M) == PydanticStrategy.MODEL_DUMP

    def test_field_serializer_uses_model_dump(self) -> None:
        class M(pydantic.BaseModel):
            name: str

            @pydantic.field_serializer("name")
            @classmethod
            def upper(cls, v: str) -> str:
                return v.upper()

        classify_type(M)
        strategy = get_pydantic_strategy(M)
        # field_serializer is detected via nested schema introspection
        assert strategy == PydanticStrategy.MODEL_DUMP


# ── Cache behavior ──────────────────────────────────────────────────────────

class TestCacheBehavior:
    def test_cache_hit_returns_same_result(self) -> None:
        class M(pydantic.BaseModel):
            x: int

        r1 = classify_type(M)
        r2 = classify_type(M)
        assert r1 == r2 == TypeCategory.PYDANTIC

    def test_cache_populated_after_classify(self) -> None:
        class M2(pydantic.BaseModel):
            x: int

        classify_type(M2)
        assert M2 in _type_cache

    def test_strategy_cache_populated_for_pydantic(self) -> None:
        class M3(pydantic.BaseModel):
            x: int

        classify_type(M3)
        assert M3 in _pydantic_strategy_cache

    def test_strategy_cache_not_populated_for_native(self) -> None:
        # Native types don't get strategy entries
        classify_type(int)
        assert int not in _pydantic_strategy_cache

    def test_get_strategy_uncached_raises_runtime_error(self) -> None:
        """get_pydantic_strategy for an uncached type raises RuntimeError."""
        class NeverClassified(pydantic.BaseModel):
            x: int

        # Don't call classify_type — go directly to get_pydantic_strategy
        with pytest.raises(RuntimeError, match="before classify_type"):
            get_pydantic_strategy(NeverClassified)


# ── classify_instance ───────────────────────────────────────────────────────

class TestClassifyInstance:
    def test_pydantic_instance(self) -> None:
        class M(pydantic.BaseModel):
            x: int

        assert classify_instance(M(x=1)) == TypeCategory.PYDANTIC

    def test_struct_instance(self) -> None:
        class S(msgspec.Struct):
            x: int

        assert classify_instance(S(x=1)) == TypeCategory.NATIVE

    def test_primitive_instance(self) -> None:
        assert classify_instance(42) == TypeCategory.NATIVE
        assert classify_instance("hello") == TypeCategory.NATIVE
        assert classify_instance(None) == TypeCategory.NATIVE

    def test_dict_instance(self) -> None:
        assert classify_instance({"a": 1}) == TypeCategory.NATIVE

    def test_list_instance(self) -> None:
        assert classify_instance([1, 2]) == TypeCategory.NATIVE


# ── Pydantic not installed simulation ───────────────────────────────────────

class TestPydanticNotInstalled:
    def test_duck_type_raises_import_error(self) -> None:
        """When pydantic is 'not installed', a duck-typed class raises ImportError."""

        class FakePydantic:
            model_validate = None
            model_fields = {}

        with patch("serializer._dispatch._pydantic_available", False), \
             patch("serializer._dispatch._BaseModel", None):
            from serializer._dispatch import _is_pydantic_type
            with pytest.raises(ImportError, match="looks like a Pydantic model"):
                _is_pydantic_type(FakePydantic)

    def test_regular_class_returns_false(self) -> None:
        """When pydantic is 'not installed', a regular class returns False."""

        class RegularClass:
            pass

        with patch("serializer._dispatch._pydantic_available", False), \
             patch("serializer._dispatch._BaseModel", None):
            from serializer._dispatch import _is_pydantic_type
            assert _is_pydantic_type(RegularClass) is False
