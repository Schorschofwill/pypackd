"""Comprehensive type coverage tests — every supported data type roundtrips correctly."""

from __future__ import annotations

import dataclasses
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from enum import Enum, IntEnum
from typing import NamedTuple, Optional, TypedDict
from uuid import UUID

import msgspec
import pytest

from serializer import Serializer, DeserializeError, SerializeError


# ── Primitives ──────────────────────────────────────────────────────────────

class TestPrimitives:
    def test_int_zero(self) -> None:
        assert Serializer.deserialize(Serializer.serialize(0), int) == 0

    def test_int_negative(self) -> None:
        assert Serializer.deserialize(Serializer.serialize(-42), int) == -42

    def test_int_large(self) -> None:
        val = 2**62
        assert Serializer.deserialize(Serializer.serialize(val), int) == val

    def test_float_zero(self) -> None:
        assert Serializer.deserialize(Serializer.serialize(0.0), float) == 0.0

    def test_float_negative(self) -> None:
        assert Serializer.deserialize(Serializer.serialize(-1.5), float) == -1.5

    def test_float_inf(self) -> None:
        val = float("inf")
        assert Serializer.deserialize(Serializer.serialize(val), float) == val

    def test_float_nan(self) -> None:
        import math
        data = Serializer.serialize(float("nan"))
        result = Serializer.deserialize(data, float)
        assert math.isnan(result)

    def test_str_empty(self) -> None:
        assert Serializer.deserialize(Serializer.serialize(""), str) == ""

    def test_str_unicode(self) -> None:
        val = "Ünïcödé 日本語 🎉"
        assert Serializer.deserialize(Serializer.serialize(val), str) == val

    def test_str_long(self) -> None:
        val = "x" * 100_000
        assert Serializer.deserialize(Serializer.serialize(val), str) == val

    def test_bool_true(self) -> None:
        assert Serializer.deserialize(Serializer.serialize(True), bool) is True

    def test_bool_false(self) -> None:
        assert Serializer.deserialize(Serializer.serialize(False), bool) is False

    def test_none(self) -> None:
        assert Serializer.deserialize(Serializer.serialize(None), type(None)) is None

    def test_bytes_empty(self) -> None:
        assert Serializer.deserialize(Serializer.serialize(b""), bytes) == b""

    def test_bytes_binary(self) -> None:
        val = bytes(range(256))
        assert Serializer.deserialize(Serializer.serialize(val), bytes) == val

    def test_bytes_large(self) -> None:
        val = b"\xab" * 100_000
        assert Serializer.deserialize(Serializer.serialize(val), bytes) == val


# ── Collections ─────────────────────────────────────────────────────────────

class TestCollections:
    def test_list_empty(self) -> None:
        assert Serializer.deserialize(Serializer.serialize([]), list) == []

    def test_list_mixed_types(self) -> None:
        val = [1, "two", 3.0, True, None, b"\x01"]
        assert Serializer.deserialize(Serializer.serialize(val), list) == val

    def test_list_nested(self) -> None:
        val = [[1, 2], [3, [4, 5]]]
        assert Serializer.deserialize(Serializer.serialize(val), list) == val

    def test_dict_empty(self) -> None:
        assert Serializer.deserialize(Serializer.serialize({}), dict) == {}

    def test_dict_nested(self) -> None:
        val = {"a": {"b": {"c": 1}}}
        assert Serializer.deserialize(Serializer.serialize(val), dict) == val

    def test_dict_mixed_values(self) -> None:
        val = {"int": 1, "str": "x", "list": [1, 2], "none": None, "bytes": b"\x01"}
        assert Serializer.deserialize(Serializer.serialize(val), dict) == val

    def test_tuple_to_list(self) -> None:
        """MessagePack has no tuple type — tuples encode as arrays, decode as lists."""
        data = Serializer.serialize((1, 2, 3))
        result = Serializer.deserialize(data, list)
        assert result == [1, 2, 3]

    def test_set_roundtrip(self) -> None:
        val = {1, 2, 3, 4, 5}
        result = Serializer.deserialize(Serializer.serialize(val), set)
        assert result == val

    def test_set_empty(self) -> None:
        result = Serializer.deserialize(Serializer.serialize(set()), set)
        assert result == set()

    def test_frozenset_roundtrip(self) -> None:
        val = frozenset({10, 20, 30})
        result = Serializer.deserialize(Serializer.serialize(val), frozenset)
        assert result == val


# ── Datetime Types ──────────────────────────────────────────────────────────

class TestDatetimeTypes:
    def test_datetime_naive(self) -> None:
        val = datetime(2024, 6, 15, 10, 30, 0)
        result = Serializer.deserialize(Serializer.serialize(val), datetime)
        assert result == val

    def test_datetime_with_tz(self) -> None:
        val = datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = Serializer.deserialize(Serializer.serialize(val), datetime)
        assert result == val

    def test_datetime_with_microseconds(self) -> None:
        val = datetime(2024, 1, 1, 0, 0, 0, 123456)
        result = Serializer.deserialize(Serializer.serialize(val), datetime)
        assert result == val

    def test_date(self) -> None:
        val = date(2024, 12, 31)
        result = Serializer.deserialize(Serializer.serialize(val), date)
        assert result == val

    def test_date_min(self) -> None:
        val = date(1, 1, 1)
        result = Serializer.deserialize(Serializer.serialize(val), date)
        assert result == val

    def test_time(self) -> None:
        val = time(23, 59, 59)
        result = Serializer.deserialize(Serializer.serialize(val), time)
        assert result == val

    def test_time_with_microseconds(self) -> None:
        val = time(12, 0, 0, 999999)
        result = Serializer.deserialize(Serializer.serialize(val), time)
        assert result == val

    def test_timedelta(self) -> None:
        val = timedelta(days=365, hours=5, minutes=30, seconds=15)
        result = Serializer.deserialize(Serializer.serialize(val), timedelta)
        assert result == val

    def test_timedelta_negative(self) -> None:
        val = timedelta(days=-1)
        result = Serializer.deserialize(Serializer.serialize(val), timedelta)
        assert result == val

    def test_timedelta_zero(self) -> None:
        val = timedelta()
        result = Serializer.deserialize(Serializer.serialize(val), timedelta)
        assert result == val


# ── Stdlib Types ────────────────────────────────────────────────────────────

class TestStdlibTypes:
    def test_uuid(self) -> None:
        val = UUID("12345678-1234-5678-1234-567812345678")
        result = Serializer.deserialize(Serializer.serialize(val), UUID)
        assert result == val

    def test_uuid_random(self) -> None:
        import uuid
        val = uuid.uuid4()
        result = Serializer.deserialize(Serializer.serialize(val), UUID)
        assert result == val

    def test_decimal(self) -> None:
        val = Decimal("3.14159265358979")
        result = Serializer.deserialize(Serializer.serialize(val), Decimal)
        assert result == val

    def test_decimal_negative(self) -> None:
        val = Decimal("-0.001")
        result = Serializer.deserialize(Serializer.serialize(val), Decimal)
        assert result == val

    def test_decimal_zero(self) -> None:
        val = Decimal("0")
        result = Serializer.deserialize(Serializer.serialize(val), Decimal)
        assert result == val

    def test_decimal_large(self) -> None:
        val = Decimal("99999999999999999.99")
        result = Serializer.deserialize(Serializer.serialize(val), Decimal)
        assert result == val

    def test_str_enum(self) -> None:
        class Color(str, Enum):
            RED = "red"
            GREEN = "green"

        result = Serializer.deserialize(Serializer.serialize(Color.RED), Color)
        assert result is Color.RED

    def test_int_enum(self) -> None:
        class Priority(IntEnum):
            LOW = 1
            HIGH = 2

        result = Serializer.deserialize(Serializer.serialize(Priority.HIGH), Priority)
        assert result is Priority.HIGH

    def test_plain_enum(self) -> None:
        class Status(Enum):
            ACTIVE = "active"
            INACTIVE = "inactive"

        result = Serializer.deserialize(Serializer.serialize(Status.ACTIVE), Status)
        assert result is Status.ACTIVE


# ── Structured Types ────────────────────────────────────────────────────────

class SmallStruct(msgspec.Struct):
    x: int
    y: str


class NestedStruct(msgspec.Struct):
    inner: SmallStruct
    label: str


class StructWithOptional(msgspec.Struct):
    name: str
    value: int | None = None


class StructWithDefaults(msgspec.Struct):
    a: int = 0
    b: str = "default"
    c: list[int] = []


@dataclasses.dataclass
class SimpleDataclass:
    x: float
    y: float


@dataclasses.dataclass
class NestedDataclass:
    point: SimpleDataclass
    label: str


@dataclasses.dataclass
class DataclassWithDefaults:
    a: int = 0
    b: str = "default"


class MyNamedTuple(NamedTuple):
    name: str
    value: int


class MyTypedDict(TypedDict):
    name: str
    age: int


class TestMsgspecStructs:
    def test_simple_struct(self) -> None:
        val = SmallStruct(x=42, y="hello")
        result = Serializer.deserialize(Serializer.serialize(val), SmallStruct)
        assert result == val

    def test_nested_struct(self) -> None:
        val = NestedStruct(inner=SmallStruct(x=1, y="a"), label="test")
        result = Serializer.deserialize(Serializer.serialize(val), NestedStruct)
        assert result == val

    def test_struct_with_optional_present(self) -> None:
        val = StructWithOptional(name="test", value=42)
        result = Serializer.deserialize(Serializer.serialize(val), StructWithOptional)
        assert result == val

    def test_struct_with_optional_absent(self) -> None:
        val = StructWithOptional(name="test")
        result = Serializer.deserialize(Serializer.serialize(val), StructWithOptional)
        assert result == val
        assert result.value is None

    def test_struct_with_defaults(self) -> None:
        val = StructWithDefaults()
        result = Serializer.deserialize(Serializer.serialize(val), StructWithDefaults)
        assert result == val


class TestDataclasses:
    def test_simple_dataclass(self) -> None:
        val = SimpleDataclass(x=1.0, y=2.0)
        result = Serializer.deserialize(Serializer.serialize(val), SimpleDataclass)
        assert result == val

    def test_nested_dataclass(self) -> None:
        val = NestedDataclass(point=SimpleDataclass(x=1.0, y=2.0), label="origin")
        result = Serializer.deserialize(Serializer.serialize(val), NestedDataclass)
        assert result == val

    def test_dataclass_with_defaults(self) -> None:
        val = DataclassWithDefaults()
        result = Serializer.deserialize(Serializer.serialize(val), DataclassWithDefaults)
        assert result == val


class TestNamedTupleAndTypedDict:
    def test_namedtuple(self) -> None:
        val = MyNamedTuple(name="Alice", value=42)
        result = Serializer.deserialize(Serializer.serialize(val), MyNamedTuple)
        assert result == val
        assert isinstance(result, MyNamedTuple)

    def test_typeddict(self) -> None:
        val: MyTypedDict = {"name": "Bob", "age": 30}
        result = Serializer.deserialize(Serializer.serialize(val), MyTypedDict)
        assert result == val


# ── Typed Generics ──────────────────────────────────────────────────────────

class TestTypedGenerics:
    def test_list_of_ints(self) -> None:
        val = [1, 2, 3]
        result = Serializer.deserialize(Serializer.serialize(val), list[int])
        assert result == val

    def test_list_of_structs(self) -> None:
        val = [SmallStruct(x=1, y="a"), SmallStruct(x=2, y="b")]
        result = Serializer.deserialize(Serializer.serialize(val), list[SmallStruct])
        assert result == val

    def test_dict_str_int(self) -> None:
        val = {"a": 1, "b": 2}
        result = Serializer.deserialize(Serializer.serialize(val), dict[str, int])
        assert result == val

    def test_dict_str_list(self) -> None:
        val = {"nums": [1, 2, 3], "strs": [4, 5]}
        result = Serializer.deserialize(Serializer.serialize(val), dict[str, list[int]])
        assert result == val

    def test_set_of_ints(self) -> None:
        val = {10, 20, 30}
        result = Serializer.deserialize(Serializer.serialize(val), set[int])
        assert result == val

    def test_optional_present(self) -> None:
        val: int | None = 42
        result = Serializer.deserialize(Serializer.serialize(val), int | None)
        assert result == 42

    def test_optional_none(self) -> None:
        val: int | None = None
        result = Serializer.deserialize(Serializer.serialize(val), int | None)
        assert result is None

    def test_list_of_dataclasses(self) -> None:
        val = [SimpleDataclass(x=1.0, y=2.0), SimpleDataclass(x=3.0, y=4.0)]
        result = Serializer.deserialize(Serializer.serialize(val), list[SimpleDataclass])
        assert result == val


# ── Complex Nesting ─────────────────────────────────────────────────────────

@dataclasses.dataclass
class Address:
    street: str
    city: str


class Tag(msgspec.Struct):
    key: str
    value: str


class TestComplexNesting:
    def test_dict_of_lists_of_dicts(self) -> None:
        val = {"users": [{"name": "A", "age": 1}, {"name": "B", "age": 2}]}
        result = Serializer.deserialize(Serializer.serialize(val), dict)
        assert result == val

    def test_list_of_dicts_of_lists(self) -> None:
        val = [{"items": [1, 2, 3]}, {"items": [4, 5, 6]}]
        result = Serializer.deserialize(Serializer.serialize(val), list)
        assert result == val

    def test_struct_containing_list_of_structs(self) -> None:
        class Container(msgspec.Struct):
            items: list[SmallStruct]

        val = Container(items=[SmallStruct(x=1, y="a"), SmallStruct(x=2, y="b")])
        result = Serializer.deserialize(Serializer.serialize(val), Container)
        assert result == val

    def test_dataclass_containing_list_of_dataclasses(self) -> None:
        @dataclasses.dataclass
        class Team:
            members: list[SimpleDataclass]

        val = Team(members=[SimpleDataclass(x=1.0, y=2.0), SimpleDataclass(x=3.0, y=4.0)])
        result = Serializer.deserialize(Serializer.serialize(val), Team)
        assert result == val

    def test_deeply_nested_dicts(self) -> None:
        val: dict = {"a": {"b": {"c": {"d": {"e": 42}}}}}
        result = Serializer.deserialize(Serializer.serialize(val), dict)
        assert result == val
