"""Tests for Pydantic decoding path."""

from __future__ import annotations

import dataclasses
from datetime import datetime

import msgspec
import pydantic
import pytest

from serializer._exceptions import DeserializeError
from serializer._pydantic import pydantic_enc_hook, deserialize_pydantic


class SimpleModel(pydantic.BaseModel):
    name: str
    age: int


class NestedPydantic(pydantic.BaseModel):
    inner: SimpleModel
    value: float


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


encoder = msgspec.msgpack.Encoder(enc_hook=pydantic_enc_hook)


class TestFlatDeserialization:
    def test_flat_model(self) -> None:
        original = SimpleModel(name="Alice", age=30)
        data = encoder.encode(original)
        result = deserialize_pydantic(data, SimpleModel)
        assert result == original

    def test_model_with_datetime(self) -> None:
        original = ModelWithDatetime(label="test", created_at=datetime(2024, 1, 1, 12, 0))
        data = encoder.encode(original)
        result = deserialize_pydantic(data, ModelWithDatetime)
        assert result.label == original.label
        assert result.created_at == original.created_at
        assert isinstance(result.created_at, datetime)


class TestNestedDeserialization:
    def test_nested_pydantic(self) -> None:
        original = NestedPydantic(inner=SimpleModel(name="Bob", age=25), value=3.14)
        data = encoder.encode(original)
        result = deserialize_pydantic(data, NestedPydantic)
        assert result == original
        assert isinstance(result.inner, SimpleModel)

    def test_nested_dataclass(self) -> None:
        original = ModelWithDataclass(name="Eve", address=Address(street="123 Main", city="NYC"))
        data = encoder.encode(original)
        result = deserialize_pydantic(data, ModelWithDataclass)
        assert result.name == original.name
        assert result.address.street == original.address.street
        assert result.address.city == original.address.city


class TestEdgeCases:
    def test_extra_fields_in_bytes(self) -> None:
        data = msgspec.msgpack.encode({"name": "Test", "age": 1, "extra": "ignored"})
        result = deserialize_pydantic(data, SimpleModel)
        assert result.name == "Test"
        assert result.age == 1


class TestErrorPaths:
    def test_missing_required_field(self) -> None:
        data = msgspec.msgpack.encode({"name": "Test"})
        with pytest.raises(DeserializeError) as exc_info:
            deserialize_pydantic(data, SimpleModel)
        assert isinstance(exc_info.value.__cause__, pydantic.ValidationError)

    def test_wrong_field_types(self) -> None:
        data = msgspec.msgpack.encode({"name": 123, "age": "not_int"})
        with pytest.raises(DeserializeError) as exc_info:
            deserialize_pydantic(data, SimpleModel)
        assert isinstance(exc_info.value.__cause__, pydantic.ValidationError)

    def test_invalid_msgpack_bytes(self) -> None:
        with pytest.raises(DeserializeError) as exc_info:
            deserialize_pydantic(b"\xff\xff\xff", SimpleModel)
        assert isinstance(exc_info.value.__cause__, msgspec.DecodeError)


class TestRoundtrip:
    def test_full_roundtrip_with_nested_dataclass(self) -> None:
        original = ModelWithDataclass(name="Charlie", address=Address(street="456 Oak", city="LA"))
        data = encoder.encode(original)
        result = deserialize_pydantic(data, ModelWithDataclass)
        assert result.name == original.name
        assert result.address.street == original.address.street
        assert result.address.city == original.address.city

    def test_full_roundtrip_nested_pydantic(self) -> None:
        original = NestedPydantic(inner=SimpleModel(name="X", age=1), value=0.0)
        data = encoder.encode(original)
        result = deserialize_pydantic(data, NestedPydantic)
        assert result == original
