"""Tests for Pydantic encoding via enc_hook."""

from __future__ import annotations

import dataclasses

import msgspec
import pydantic
import pytest

from serializer._pydantic import pydantic_enc_hook


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


class ModelWithComputed(pydantic.BaseModel):
    first: str
    last: str

    @pydantic.computed_field  # type: ignore[prop-decorator]
    @property
    def full_name(self) -> str:
        return f"{self.first} {self.last}"


class ModelWithExtra(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="allow")
    x: int


# Shared encoder with enc_hook
encoder = msgspec.msgpack.Encoder(enc_hook=pydantic_enc_hook)


class TestFlatModel:
    def test_flat_model_encodes(self) -> None:
        obj = SimpleModel(name="Alice", age=30)
        data = encoder.encode(obj)
        decoded = msgspec.msgpack.decode(data)
        assert decoded == {"name": "Alice", "age": 30}

    def test_model_with_none(self) -> None:
        class OptModel(pydantic.BaseModel):
            val: str | None = None

        obj = OptModel()
        data = encoder.encode(obj)
        decoded = msgspec.msgpack.decode(data)
        assert decoded == {"val": None}

    def test_model_with_bytes(self) -> None:
        class ByteModel(pydantic.BaseModel):
            payload: bytes

        obj = ByteModel(payload=b"\x01\x02\x03")
        data = encoder.encode(obj)
        decoded = msgspec.msgpack.decode(data)
        assert decoded == {"payload": b"\x01\x02\x03"}


class TestNestedModels:
    def test_nested_pydantic(self) -> None:
        obj = NestedPydantic(inner=SimpleModel(name="Bob", age=25), value=3.14)
        data = encoder.encode(obj)
        decoded = msgspec.msgpack.decode(data)
        assert decoded == {"inner": {"name": "Bob", "age": 25}, "value": 3.14}

    def test_nested_dataclass(self) -> None:
        obj = ModelWithDataclass(name="Eve", address=Address(street="123 Main", city="NYC"))
        data = encoder.encode(obj)
        decoded = msgspec.msgpack.decode(data)
        assert decoded == {"name": "Eve", "address": {"street": "123 Main", "city": "NYC"}}


class TestComputedAndExtra:
    def test_computed_field_included(self) -> None:
        obj = ModelWithComputed(first="John", last="Doe")
        data = encoder.encode(obj)
        decoded = msgspec.msgpack.decode(data)
        assert decoded["full_name"] == "John Doe"
        assert decoded["first"] == "John"
        assert decoded["last"] == "Doe"

    def test_extra_fields_preserved(self) -> None:
        obj = ModelWithExtra(x=1, y=2, z=3)  # type: ignore[call-arg]
        data = encoder.encode(obj)
        decoded = msgspec.msgpack.decode(data)
        assert decoded["x"] == 1
        assert decoded["y"] == 2
        assert decoded["z"] == 3


class TestErrorPaths:
    def test_unsupported_type_raises(self) -> None:
        with pytest.raises(TypeError, match="Cannot serialize"):
            pydantic_enc_hook(object())


class TestIntegration:
    def test_encoded_bytes_decode_to_matching_dict(self) -> None:
        obj = SimpleModel(name="Test", age=99)
        data = encoder.encode(obj)
        decoded = msgspec.msgpack.decode(data)
        assert decoded["name"] == obj.name
        assert decoded["age"] == obj.age
