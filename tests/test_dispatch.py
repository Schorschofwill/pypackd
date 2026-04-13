"""Tests for type detection and dispatch cache."""

from __future__ import annotations

import dataclasses

import msgspec
import pydantic
import pytest

from serializer._dispatch import (
    TypeCategory,
    PydanticStrategy,
    classify_instance,
    classify_type,
    get_pydantic_strategy,
    _type_cache,
)


class MyPydanticModel(pydantic.BaseModel):
    name: str
    age: int


class MyStruct(msgspec.Struct):
    x: int
    y: str


@dataclasses.dataclass
class MyDataclass:
    value: int


class PydanticWithComputed(pydantic.BaseModel):
    first: str
    last: str

    @pydantic.computed_field  # type: ignore[prop-decorator]
    @property
    def full_name(self) -> str:
        return f"{self.first} {self.last}"


class PydanticWithExtra(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="allow")
    x: int


class PydanticWithExclude(pydantic.BaseModel):
    public: str
    secret: str = pydantic.Field(exclude=True)


class PydanticWithAlias(pydantic.BaseModel):
    name: str = pydantic.Field(alias="user_name")


class PydanticWithSerializer(pydantic.BaseModel):
    x: int
    y: int

    @pydantic.model_serializer
    def custom_serialize(self) -> dict:
        return {"sum": self.x + self.y}


class TestClassifyType:
    def test_pydantic_model(self) -> None:
        assert classify_type(MyPydanticModel) == TypeCategory.PYDANTIC

    def test_msgspec_struct(self) -> None:
        assert classify_type(MyStruct) == TypeCategory.NATIVE

    def test_dataclass(self) -> None:
        assert classify_type(MyDataclass) == TypeCategory.NATIVE

    def test_primitive_int(self) -> None:
        assert classify_type(int) == TypeCategory.NATIVE

    def test_primitive_str(self) -> None:
        assert classify_type(str) == TypeCategory.NATIVE

    def test_dict_type(self) -> None:
        assert classify_type(dict) == TypeCategory.NATIVE

    def test_list_type(self) -> None:
        assert classify_type(list) == TypeCategory.NATIVE

    def test_none_type(self) -> None:
        assert classify_type(type(None)) == TypeCategory.NATIVE


class TestClassifyInstance:
    def test_pydantic_instance(self) -> None:
        obj = MyPydanticModel(name="test", age=1)
        assert classify_instance(obj) == TypeCategory.PYDANTIC

    def test_struct_instance(self) -> None:
        obj = MyStruct(x=1, y="a")
        assert classify_instance(obj) == TypeCategory.NATIVE

    def test_dataclass_instance(self) -> None:
        obj = MyDataclass(value=42)
        assert classify_instance(obj) == TypeCategory.NATIVE


class TestCacheHit:
    def test_second_call_hits_cache(self) -> None:
        classify_type(MyPydanticModel)
        assert MyPydanticModel in _type_cache
        result = classify_type(MyPydanticModel)
        assert result == TypeCategory.PYDANTIC


class TestPydanticStrategy:
    def test_simple_model_uses_dict(self) -> None:
        classify_type(MyPydanticModel)
        assert get_pydantic_strategy(MyPydanticModel) == PydanticStrategy.DICT

    def test_computed_field_uses_model_dump(self) -> None:
        classify_type(PydanticWithComputed)
        assert get_pydantic_strategy(PydanticWithComputed) == PydanticStrategy.MODEL_DUMP

    def test_extra_allow_uses_model_dump(self) -> None:
        classify_type(PydanticWithExtra)
        assert get_pydantic_strategy(PydanticWithExtra) == PydanticStrategy.MODEL_DUMP

    def test_excluded_field_uses_model_dump(self) -> None:
        classify_type(PydanticWithExclude)
        assert get_pydantic_strategy(PydanticWithExclude) == PydanticStrategy.MODEL_DUMP

    def test_alias_uses_model_dump(self) -> None:
        classify_type(PydanticWithAlias)
        assert get_pydantic_strategy(PydanticWithAlias) == PydanticStrategy.MODEL_DUMP

    def test_model_serializer_uses_model_dump(self) -> None:
        classify_type(PydanticWithSerializer)
        assert get_pydantic_strategy(PydanticWithSerializer) == PydanticStrategy.MODEL_DUMP
