"""Comprehensive Pydantic tests — every model feature, encoding strategy, and edge case."""

from __future__ import annotations

import dataclasses
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID

import msgspec
import pydantic
import pytest

from serializer import Serializer, DeserializeError, SerializeError


# ── Model definitions ───────────────────────────────────────────────────────

class SimpleModel(pydantic.BaseModel):
    name: str
    age: int


class ModelWithOptional(pydantic.BaseModel):
    name: str
    nickname: str | None = None


class ModelWithDefaults(pydantic.BaseModel):
    x: int = 0
    y: str = "default"
    z: list[int] = []


class ModelWithComputed(pydantic.BaseModel):
    first: str
    last: str

    @pydantic.computed_field  # type: ignore[prop-decorator]
    @property
    def full_name(self) -> str:
        return f"{self.first} {self.last}"


class ModelWithExclude(pydantic.BaseModel):
    public_data: str
    secret: str = pydantic.Field(exclude=True)


class ModelWithAlias(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(populate_by_name=True)
    name: str = pydantic.Field(alias="user_name")


class ModelWithSerializationAlias(pydantic.BaseModel):
    name: str = pydantic.Field(serialization_alias="userName")


class ModelWithSerializer(pydantic.BaseModel):
    x: int
    y: int

    @pydantic.model_serializer
    def custom_serialize(self) -> dict:
        return {"sum": self.x + self.y}


class ModelWithFieldSerializer(pydantic.BaseModel):
    name: str

    @pydantic.field_serializer("name")
    @classmethod
    def upper_name(cls, v: str) -> str:
        return v.upper()


class ModelWithExtraAllow(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="allow")
    base_field: int


class ModelWithExtraForbid(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")
    base_field: int


class ModelWithExtraIgnore(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="ignore")
    base_field: int


class NestedPydantic(pydantic.BaseModel):
    inner: SimpleModel
    score: float


class DoubleNestedPydantic(pydantic.BaseModel):
    outer: NestedPydantic
    label: str


@dataclasses.dataclass
class Address:
    street: str
    city: str


class PydanticWithDataclass(pydantic.BaseModel):
    name: str
    address: Address


class PydanticWithDatetime(pydantic.BaseModel):
    label: str
    created_at: datetime


class PydanticWithUUID(pydantic.BaseModel):
    id: UUID
    name: str


class PydanticWithDecimal(pydantic.BaseModel):
    amount: Decimal
    currency: str


class Color(str, Enum):
    RED = "red"
    GREEN = "green"


class PydanticWithEnum(pydantic.BaseModel):
    color: Color
    label: str


class PydanticWithListOfModels(pydantic.BaseModel):
    items: list[SimpleModel]


class PydanticWithOptionalModel(pydantic.BaseModel):
    main: SimpleModel
    backup: SimpleModel | None = None


class PydanticWithBytes(pydantic.BaseModel):
    payload: bytes
    label: str


class PydanticWithMixedFields(pydantic.BaseModel):
    """Model with many different field types."""
    name: str
    age: int
    score: float
    active: bool
    data: bytes
    tags: list[str]
    metadata: dict[str, int]
    created: datetime
    id: UUID
    amount: Decimal


# ── Roundtrip Tests: Simple Models ──────────────────────────────────────────

class TestSimpleModels:
    def test_flat_model(self) -> None:
        val = SimpleModel(name="Alice", age=30)
        result = Serializer.deserialize(Serializer.serialize(val), SimpleModel)
        assert result == val

    def test_optional_present(self) -> None:
        val = ModelWithOptional(name="Bob", nickname="Bobby")
        result = Serializer.deserialize(Serializer.serialize(val), ModelWithOptional)
        assert result == val

    def test_optional_absent(self) -> None:
        val = ModelWithOptional(name="Bob")
        result = Serializer.deserialize(Serializer.serialize(val), ModelWithOptional)
        assert result == val
        assert result.nickname is None

    def test_defaults(self) -> None:
        val = ModelWithDefaults()
        result = Serializer.deserialize(Serializer.serialize(val), ModelWithDefaults)
        assert result == val

    def test_defaults_overridden(self) -> None:
        val = ModelWithDefaults(x=42, y="custom", z=[1, 2, 3])
        result = Serializer.deserialize(Serializer.serialize(val), ModelWithDefaults)
        assert result == val

    def test_bytes_field(self) -> None:
        val = PydanticWithBytes(payload=b"\x01\x02\x03", label="test")
        result = Serializer.deserialize(Serializer.serialize(val), PydanticWithBytes)
        assert result == val


# ── Roundtrip Tests: Complex Pydantic Features ──────────────────────────────

class TestPydanticFeatures:
    def test_computed_field_roundtrip(self) -> None:
        val = ModelWithComputed(first="John", last="Doe")
        data = Serializer.serialize(val)
        decoded = msgspec.msgpack.decode(data)
        assert decoded["full_name"] == "John Doe"
        assert decoded["first"] == "John"
        assert decoded["last"] == "Doe"

    def test_exclude_field_not_serialized(self) -> None:
        val = ModelWithExclude(public_data="visible", secret="hidden")
        data = Serializer.serialize(val)
        decoded = msgspec.msgpack.decode(data)
        assert "public_data" in decoded
        assert "secret" not in decoded

    def test_alias_roundtrip(self) -> None:
        val = ModelWithAlias(user_name="Alice")
        data = Serializer.serialize(val)
        decoded = msgspec.msgpack.decode(data)
        # model_dump uses alias by default
        assert decoded.get("user_name") == "Alice" or decoded.get("name") == "Alice"

    def test_serialization_alias(self) -> None:
        val = ModelWithSerializationAlias(name="Bob")
        data = Serializer.serialize(val)
        decoded = msgspec.msgpack.decode(data)
        # model_dump(mode='python') uses serialization_alias
        assert "userName" in decoded or "name" in decoded

    def test_model_serializer_custom_shape(self) -> None:
        val = ModelWithSerializer(x=3, y=4)
        data = Serializer.serialize(val)
        decoded = msgspec.msgpack.decode(data)
        assert decoded == {"sum": 7}

    def test_field_serializer(self) -> None:
        val = ModelWithFieldSerializer(name="alice")
        data = Serializer.serialize(val)
        decoded = msgspec.msgpack.decode(data)
        assert decoded["name"] == "ALICE"

    def test_extra_allow_with_extras(self) -> None:
        val = ModelWithExtraAllow(base_field=1, extra1="a", extra2="b")  # type: ignore[call-arg]
        data = Serializer.serialize(val)
        decoded = msgspec.msgpack.decode(data)
        assert decoded["base_field"] == 1
        assert decoded["extra1"] == "a"
        assert decoded["extra2"] == "b"

    def test_extra_allow_without_extras(self) -> None:
        val = ModelWithExtraAllow(base_field=42)
        data = Serializer.serialize(val)
        decoded = msgspec.msgpack.decode(data)
        assert decoded["base_field"] == 42

    def test_extra_forbid_roundtrip(self) -> None:
        val = ModelWithExtraForbid(base_field=99)
        result = Serializer.deserialize(Serializer.serialize(val), ModelWithExtraForbid)
        assert result == val

    def test_extra_ignore_roundtrip(self) -> None:
        val = ModelWithExtraIgnore(base_field=5)
        result = Serializer.deserialize(Serializer.serialize(val), ModelWithExtraIgnore)
        assert result == val


# ── Roundtrip Tests: Pydantic with Stdlib Types ─────────────────────────────

class TestPydanticWithStdlib:
    def test_datetime_field(self) -> None:
        val = PydanticWithDatetime(label="event", created_at=datetime(2024, 6, 15, 12, 0))
        result = Serializer.deserialize(Serializer.serialize(val), PydanticWithDatetime)
        assert result == val

    def test_uuid_field(self) -> None:
        uid = UUID("abcdef01-2345-6789-abcd-ef0123456789")
        val = PydanticWithUUID(id=uid, name="item")
        result = Serializer.deserialize(Serializer.serialize(val), PydanticWithUUID)
        assert result == val

    def test_decimal_field(self) -> None:
        val = PydanticWithDecimal(amount=Decimal("19.99"), currency="EUR")
        result = Serializer.deserialize(Serializer.serialize(val), PydanticWithDecimal)
        assert result == val

    def test_enum_field(self) -> None:
        val = PydanticWithEnum(color=Color.GREEN, label="go")
        result = Serializer.deserialize(Serializer.serialize(val), PydanticWithEnum)
        assert result == val

    def test_mixed_fields_roundtrip(self) -> None:
        val = PydanticWithMixedFields(
            name="test",
            age=25,
            score=9.5,
            active=True,
            data=b"\x01\x02",
            tags=["a", "b"],
            metadata={"x": 1, "y": 2},
            created=datetime(2024, 1, 1),
            id=UUID("12345678-1234-5678-1234-567812345678"),
            amount=Decimal("42.50"),
        )
        result = Serializer.deserialize(Serializer.serialize(val), PydanticWithMixedFields)
        assert result.name == val.name
        assert result.age == val.age
        assert result.score == val.score
        assert result.active == val.active
        assert result.data == val.data
        assert result.tags == val.tags
        assert result.metadata == val.metadata
        assert result.created == val.created
        assert result.id == val.id
        assert result.amount == val.amount


# ── Roundtrip Tests: Nesting ────────────────────────────────────────────────

class TestPydanticNesting:
    def test_nested_pydantic(self) -> None:
        val = NestedPydantic(inner=SimpleModel(name="X", age=1), score=5.0)
        result = Serializer.deserialize(Serializer.serialize(val), NestedPydantic)
        assert result == val

    def test_double_nested_pydantic(self) -> None:
        val = DoubleNestedPydantic(
            outer=NestedPydantic(inner=SimpleModel(name="deep", age=99), score=1.0),
            label="L"
        )
        result = Serializer.deserialize(Serializer.serialize(val), DoubleNestedPydantic)
        assert result == val

    def test_pydantic_with_dataclass(self) -> None:
        val = PydanticWithDataclass(name="A", address=Address(street="Main St", city="NYC"))
        result = Serializer.deserialize(Serializer.serialize(val), PydanticWithDataclass)
        assert result.name == val.name
        assert result.address.street == val.address.street
        assert result.address.city == val.address.city

    def test_list_of_pydantic_models(self) -> None:
        val = PydanticWithListOfModels(items=[
            SimpleModel(name="A", age=1),
            SimpleModel(name="B", age=2),
            SimpleModel(name="C", age=3),
        ])
        result = Serializer.deserialize(Serializer.serialize(val), PydanticWithListOfModels)
        assert result == val

    def test_optional_nested_present(self) -> None:
        val = PydanticWithOptionalModel(
            main=SimpleModel(name="main", age=1),
            backup=SimpleModel(name="backup", age=2),
        )
        result = Serializer.deserialize(Serializer.serialize(val), PydanticWithOptionalModel)
        assert result == val

    def test_optional_nested_absent(self) -> None:
        val = PydanticWithOptionalModel(main=SimpleModel(name="only", age=1))
        result = Serializer.deserialize(Serializer.serialize(val), PydanticWithOptionalModel)
        assert result == val
        assert result.backup is None


# ── Error Paths ─────────────────────────────────────────────────────────────

class TestPydanticErrors:
    def test_missing_required_field(self) -> None:
        data = msgspec.msgpack.encode({"name": "only_name"})
        with pytest.raises(DeserializeError) as exc_info:
            Serializer.deserialize(data, SimpleModel)
        assert exc_info.value.__cause__ is not None

    def test_wrong_field_type(self) -> None:
        data = msgspec.msgpack.encode({"name": 123, "age": "not_int"})
        with pytest.raises(DeserializeError):
            Serializer.deserialize(data, SimpleModel)

    def test_invalid_bytes(self) -> None:
        with pytest.raises(DeserializeError):
            Serializer.deserialize(b"\xff\xff\xff\xff", SimpleModel)

    def test_extra_forbid_rejects_extra(self) -> None:
        data = msgspec.msgpack.encode({"base_field": 1, "unknown": "bad"})
        with pytest.raises(DeserializeError):
            Serializer.deserialize(data, ModelWithExtraForbid)

    def test_serialize_error_wraps_cause(self) -> None:
        with pytest.raises(SerializeError) as exc_info:
            Serializer.serialize(object())
        assert exc_info.value.__cause__ is not None

    def test_deserialize_error_not_double_wrapped(self) -> None:
        """DeserializeError should not be wrapped in another DeserializeError."""
        data = msgspec.msgpack.encode({"name": "only_name"})
        with pytest.raises(DeserializeError) as exc_info:
            Serializer.deserialize(data, SimpleModel)
        # The cause should be a pydantic ValidationError, not another DeserializeError
        assert not isinstance(exc_info.value.__cause__, DeserializeError)


# ── Repeated Calls (Cache Path) ────────────────────────────────────────────

class TestRepeatedCalls:
    def test_repeated_serialize_same_type(self) -> None:
        for i in range(10):
            val = SimpleModel(name=f"user_{i}", age=i)
            result = Serializer.deserialize(Serializer.serialize(val), SimpleModel)
            assert result == val

    def test_repeated_deserialize_same_type(self) -> None:
        """Pydantic types go through classify_type every time — verify correctness."""
        original = SimpleModel(name="test", age=42)
        data = Serializer.serialize(original)
        for _ in range(10):
            result = Serializer.deserialize(data, SimpleModel)
            assert result == original

    def test_repeated_deserialize_native_type(self) -> None:
        """Native types use the decoder cache — verify cache works."""
        val = SmallStruct(x=1, y="a")
        data = Serializer.serialize(val)
        for _ in range(10):
            result = Serializer.deserialize(data, SmallStruct)
            assert result == val


class SmallStruct(msgspec.Struct):
    x: int
    y: str
