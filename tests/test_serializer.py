"""Integration tests for the public Serializer API."""

from __future__ import annotations

import dataclasses
from datetime import datetime, date, timedelta
from decimal import Decimal
from enum import Enum
from uuid import UUID

import msgspec
import pydantic
import pytest

from serializer import Serializer, SerializeError, DeserializeError, SerializerError


# -- Test models --

class SimpleModel(pydantic.BaseModel):
    name: str
    age: int


class MyStruct(msgspec.Struct):
    x: int
    y: str


@dataclasses.dataclass
class Point:
    x: float
    y: float


class Color(Enum):
    RED = "red"
    GREEN = "green"


class NestedPydanticModel(pydantic.BaseModel):
    inner: SimpleModel
    score: float


@dataclasses.dataclass
class Address:
    street: str
    city: str


class ModelWithDataclass(pydantic.BaseModel):
    name: str
    address: Address


class ModelWithDatetime(pydantic.BaseModel):
    label: str
    created_at: datetime


# -- Primitive roundtrips --

class TestPrimitiveRoundtrips:
    def test_int(self) -> None:
        assert Serializer.deserialize(Serializer.serialize(42), int) == 42

    def test_float(self) -> None:
        assert Serializer.deserialize(Serializer.serialize(3.14), float) == 3.14

    def test_str(self) -> None:
        assert Serializer.deserialize(Serializer.serialize("hello"), str) == "hello"

    def test_bool(self) -> None:
        assert Serializer.deserialize(Serializer.serialize(True), bool) is True

    def test_none(self) -> None:
        assert Serializer.deserialize(Serializer.serialize(None), type(None)) is None

    def test_bytes(self) -> None:
        assert Serializer.deserialize(Serializer.serialize(b"\x01\x02"), bytes) == b"\x01\x02"


# -- Collection roundtrips --

class TestCollectionRoundtrips:
    def test_list(self) -> None:
        val = [1, 2, 3]
        assert Serializer.deserialize(Serializer.serialize(val), list) == val

    def test_dict(self) -> None:
        val = {"a": 1, "b": 2}
        assert Serializer.deserialize(Serializer.serialize(val), dict) == val

    def test_tuple(self) -> None:
        val = (1, "a", True)
        data = Serializer.serialize(val)
        result = Serializer.deserialize(data, list)
        assert result == [1, "a", True]


# -- Stdlib type roundtrips --

class TestStdlibTypeRoundtrips:
    def test_uuid(self) -> None:
        val = UUID("12345678-1234-5678-1234-567812345678")
        result = Serializer.deserialize(Serializer.serialize(val), UUID)
        assert result == val

    def test_decimal(self) -> None:
        val = Decimal("3.14159")
        result = Serializer.deserialize(Serializer.serialize(val), Decimal)
        assert result == val

    def test_date(self) -> None:
        val = date(2024, 6, 15)
        result = Serializer.deserialize(Serializer.serialize(val), date)
        assert result == val

    def test_timedelta(self) -> None:
        val = timedelta(days=1, hours=2, minutes=30)
        result = Serializer.deserialize(Serializer.serialize(val), timedelta)
        assert result == val

    def test_enum(self) -> None:
        val = Color.RED
        result = Serializer.deserialize(Serializer.serialize(val), Color)
        assert result == val


# -- Structured type roundtrips --

class TestStructuredRoundtrips:
    def test_msgspec_struct(self) -> None:
        original = MyStruct(x=10, y="test")
        data = Serializer.serialize(original)
        result = Serializer.deserialize(data, MyStruct)
        assert result == original

    def test_dataclass(self) -> None:
        original = Point(x=1.0, y=2.0)
        data = Serializer.serialize(original)
        result = Serializer.deserialize(data, Point)
        assert result == original

    def test_pydantic_model(self) -> None:
        original = SimpleModel(name="Alice", age=30)
        data = Serializer.serialize(original)
        result = Serializer.deserialize(data, SimpleModel)
        assert result == original

    def test_nested_dataclass_in_pydantic(self) -> None:
        original = ModelWithDataclass(name="Bob", address=Address(street="123 Main", city="NYC"))
        data = Serializer.serialize(original)
        result = Serializer.deserialize(data, ModelWithDataclass)
        assert result.name == original.name
        assert result.address.street == original.address.street
        assert result.address.city == original.address.city

    def test_nested_pydantic_in_pydantic(self) -> None:
        original = NestedPydanticModel(inner=SimpleModel(name="X", age=1), score=9.5)
        data = Serializer.serialize(original)
        result = Serializer.deserialize(data, NestedPydanticModel)
        assert result == original

    def test_pydantic_with_datetime(self) -> None:
        original = ModelWithDatetime(label="test", created_at=datetime(2024, 6, 15, 10, 30))
        data = Serializer.serialize(original)
        result = Serializer.deserialize(data, ModelWithDatetime)
        assert result.created_at == original.created_at


# -- Edge cases --

class TestEdgeCases:
    def test_empty_dict(self) -> None:
        assert Serializer.deserialize(Serializer.serialize({}), dict) == {}

    def test_empty_list(self) -> None:
        assert Serializer.deserialize(Serializer.serialize([]), list) == []

    def test_empty_bytes(self) -> None:
        assert Serializer.deserialize(Serializer.serialize(b""), bytes) == b""

    def test_large_nested_structure(self) -> None:
        val = {"data": [{"k": i, "v": [i * 2]} for i in range(100)]}
        result = Serializer.deserialize(Serializer.serialize(val), dict)
        assert result == val

    def test_dataclass_with_defaults(self) -> None:
        @dataclasses.dataclass
        class WithDefault:
            a: int = 0
            b: str = "default"

        original = WithDefault()
        data = Serializer.serialize(original)
        result = Serializer.deserialize(data, WithDefault)
        assert result == original


# -- Error paths --

class TestErrorPaths:
    def test_serialize_unsupported_type(self) -> None:
        with pytest.raises(SerializeError, match="object"):
            Serializer.serialize(object())

    def test_deserialize_invalid_bytes(self) -> None:
        with pytest.raises(DeserializeError):
            Serializer.deserialize(b"\xff\xff\xff\xff", int)

    def test_deserialize_wrong_type(self) -> None:
        data = Serializer.serialize("hello")
        with pytest.raises(DeserializeError):
            Serializer.deserialize(data, int)

    def test_exceptions_inherit_from_base(self) -> None:
        assert issubclass(SerializeError, SerializerError)
        assert issubclass(DeserializeError, SerializerError)

    def test_serialize_error_has_cause(self) -> None:
        with pytest.raises(SerializeError) as exc_info:
            Serializer.serialize(object())
        assert exc_info.value.__cause__ is not None

    def test_deserialize_error_has_cause(self) -> None:
        with pytest.raises(DeserializeError) as exc_info:
            Serializer.deserialize(b"\xff\xff", int)
        assert exc_info.value.__cause__ is not None


# -- Import test --

class TestImports:
    def test_import_serializer(self) -> None:
        from serializer import Serializer as S
        assert hasattr(S, "serialize")
        assert hasattr(S, "deserialize")

    def test_import_exceptions(self) -> None:
        from serializer import SerializerError, SerializeError, DeserializeError
        assert issubclass(SerializeError, SerializerError)


# -- Integration --

class TestIntegration:
    def test_sender_receiver_pattern(self) -> None:
        """Simulate IPC: sender serializes, receiver deserializes."""
        original = SimpleModel(name="IPC_Test", age=42)
        wire_bytes = Serializer.serialize(original)
        received = Serializer.deserialize(wire_bytes, SimpleModel)
        assert received == original
