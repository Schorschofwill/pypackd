"""Tests for type coverage gaps — Union, Literal, typed tuples, complex
NamedTuple/TypedDict, collection edge cases, non-string dict keys,
and advanced Pydantic features (RootModel, model_validator, discriminated unions)."""

from __future__ import annotations

import dataclasses
from datetime import datetime, date, time, timedelta, timezone
from decimal import Decimal
from enum import Enum, IntEnum, Flag, IntFlag
from typing import Literal, NamedTuple, Optional, TypedDict, Union
from uuid import UUID, uuid4

import msgspec
import pydantic
import pytest

from serializer import Serializer, DeserializeError, SerializeError


# ── Union types ──────────────────────────────────────────────────────────────


class TestUnionTypes:
    """Roundtrip tests for Union[T1, T2] — not just Optional (T | None)."""

    def test_union_int_str_with_int(self) -> None:
        data = Serializer.serialize(42)
        assert Serializer.deserialize(data, Union[int, str]) == 42

    def test_union_int_str_with_str(self) -> None:
        data = Serializer.serialize("hello")
        assert Serializer.deserialize(data, Union[int, str]) == "hello"

    def test_union_int_float_with_float(self) -> None:
        data = Serializer.serialize(3.14)
        assert Serializer.deserialize(data, Union[int, float]) == 3.14

    def test_union_str_none_with_str(self) -> None:
        data = Serializer.serialize("value")
        assert Serializer.deserialize(data, Union[str, None]) == "value"

    def test_union_str_none_with_none(self) -> None:
        data = Serializer.serialize(None)
        assert Serializer.deserialize(data, Union[str, None]) is None

    def test_union_bool_int_str(self) -> None:
        data = Serializer.serialize(True)
        result = Serializer.deserialize(data, Union[bool, int, str])
        assert result is True

    def test_union_in_struct(self) -> None:
        class S(msgspec.Struct):
            val: Union[int, str]

        for v in [42, "hello"]:
            obj = S(val=v)
            data = Serializer.serialize(obj)
            result = Serializer.deserialize(data, S)
            assert result.val == v

    def test_union_in_list(self) -> None:
        data = Serializer.serialize([1, "two", 3])
        result = Serializer.deserialize(data, list[Union[int, str]])
        assert result == [1, "two", 3]


# ── Literal types ────────────────────────────────────────────────────────────


class TestLiteralTypes:
    def test_literal_string(self) -> None:
        data = Serializer.serialize("red")
        assert Serializer.deserialize(data, Literal["red", "green", "blue"]) == "red"

    def test_literal_int(self) -> None:
        data = Serializer.serialize(1)
        assert Serializer.deserialize(data, Literal[1, 2, 3]) == 1

    def test_literal_invalid_value_raises(self) -> None:
        data = Serializer.serialize("purple")
        with pytest.raises(DeserializeError):
            Serializer.deserialize(data, Literal["red", "green", "blue"])

    def test_literal_in_struct(self) -> None:
        class S(msgspec.Struct):
            color: Literal["red", "green", "blue"]

        obj = S(color="green")
        data = Serializer.serialize(obj)
        result = Serializer.deserialize(data, S)
        assert result.color == "green"


# ── Typed Tuples ─────────────────────────────────────────────────────────────


class TestTypedTuples:
    def test_homogeneous_tuple(self) -> None:
        data = Serializer.serialize((1, 2, 3))
        result = Serializer.deserialize(data, tuple[int, ...])
        assert result == (1, 2, 3)

    def test_heterogeneous_tuple(self) -> None:
        data = Serializer.serialize((1, "hi", 3.14))
        result = Serializer.deserialize(data, tuple[int, str, float])
        assert result == (1, "hi", 3.14)

    def test_empty_tuple(self) -> None:
        data = Serializer.serialize(())
        result = Serializer.deserialize(data, tuple[()])
        assert result == ()

    def test_tuple_with_optional(self) -> None:
        data = Serializer.serialize((1, None))
        result = Serializer.deserialize(data, tuple[int, Optional[str]])
        assert result == (1, None)

    def test_nested_tuple(self) -> None:
        data = Serializer.serialize(((1, 2), (3, 4)))
        result = Serializer.deserialize(data, tuple[tuple[int, int], tuple[int, int]])
        assert result == ((1, 2), (3, 4))


# ── Complex NamedTuple / TypedDict ───────────────────────────────────────────


class TestComplexNamedTuple:
    def test_namedtuple_with_list_field(self) -> None:
        class NT(NamedTuple):
            name: str
            scores: list[int]

        obj = NT(name="Alice", scores=[90, 85, 92])
        data = Serializer.serialize(obj)
        result = Serializer.deserialize(data, NT)
        assert result.name == "Alice"
        assert result.scores == [90, 85, 92]

    def test_namedtuple_with_dict_field(self) -> None:
        class NT(NamedTuple):
            name: str
            metadata: dict[str, int]

        obj = NT(name="Bob", metadata={"age": 30, "score": 100})
        data = Serializer.serialize(obj)
        result = Serializer.deserialize(data, NT)
        assert result.metadata == {"age": 30, "score": 100}

    def test_namedtuple_with_optional_field(self) -> None:
        class NT(NamedTuple):
            required: str
            optional: Optional[int] = None

        for obj in [NT("hello", 42), NT("hello", None), NT("hello")]:
            data = Serializer.serialize(obj)
            result = Serializer.deserialize(data, NT)
            assert result == obj

    def test_namedtuple_with_uuid_field(self) -> None:
        class NT(NamedTuple):
            id: UUID
            name: str

        uid = uuid4()
        obj = NT(id=uid, name="test")
        data = Serializer.serialize(obj)
        result = Serializer.deserialize(data, NT)
        assert result.id == uid
        assert result.name == "test"


class TestComplexTypedDict:
    def test_typeddict_with_list_field(self) -> None:
        class TD(TypedDict):
            name: str
            items: list[int]

        obj: TD = {"name": "test", "items": [1, 2, 3]}
        data = Serializer.serialize(obj)
        result = Serializer.deserialize(data, TD)
        assert result == obj

    def test_typeddict_with_nested_dict(self) -> None:
        class TD(TypedDict):
            data: dict[str, list[int]]

        obj: TD = {"data": {"a": [1, 2], "b": [3, 4]}}
        data = Serializer.serialize(obj)
        result = Serializer.deserialize(data, TD)
        assert result == obj

    def test_typeddict_with_optional_field(self) -> None:
        class TD(TypedDict, total=False):
            required: str
            optional: int

        obj_full: TD = {"required": "hello", "optional": 42}
        data = Serializer.serialize(obj_full)
        result = Serializer.deserialize(data, TD)
        assert result == obj_full

        obj_partial: TD = {"required": "hello"}
        data = Serializer.serialize(obj_partial)
        result = Serializer.deserialize(data, TD)
        assert result == obj_partial

    def test_typeddict_with_union_field(self) -> None:
        class TD(TypedDict):
            value: Union[int, str]

        for val in [42, "hello"]:
            obj: TD = {"value": val}
            data = Serializer.serialize(obj)
            result = Serializer.deserialize(data, TD)
            assert result["value"] == val


# ── Collection edge cases ────────────────────────────────────────────────────


class TestCollectionEdgeCases:
    def test_set_of_strings(self) -> None:
        val = {"a", "b", "c"}
        data = Serializer.serialize(val)
        result = Serializer.deserialize(data, set[str])
        assert result == val

    def test_set_of_floats(self) -> None:
        val = {1.1, 2.2, 3.3}
        data = Serializer.serialize(val)
        result = Serializer.deserialize(data, set[float])
        assert result == val

    def test_set_of_uuids(self) -> None:
        ids = {uuid4(), uuid4(), uuid4()}
        data = Serializer.serialize(ids)
        result = Serializer.deserialize(data, set[UUID])
        assert result == ids

    def test_frozenset_of_strings(self) -> None:
        val = frozenset(["x", "y", "z"])
        data = Serializer.serialize(val)
        result = Serializer.deserialize(data, frozenset[str])
        assert result == val

    def test_frozenset_of_ints(self) -> None:
        val = frozenset([10, 20, 30])
        data = Serializer.serialize(val)
        result = Serializer.deserialize(data, frozenset[int])
        assert result == val

    def test_empty_set_typed(self) -> None:
        data = Serializer.serialize(set())
        result = Serializer.deserialize(data, set[int])
        assert result == set()

    def test_empty_frozenset_typed(self) -> None:
        data = Serializer.serialize(frozenset())
        result = Serializer.deserialize(data, frozenset[str])
        assert result == frozenset()

    def test_dict_int_keys(self) -> None:
        val = {1: "one", 2: "two", 3: "three"}
        data = Serializer.serialize(val)
        result = Serializer.deserialize(data, dict[int, str])
        assert result == val

    def test_dict_uuid_keys(self) -> None:
        k1, k2 = uuid4(), uuid4()
        val = {k1: "a", k2: "b"}
        data = Serializer.serialize(val)
        result = Serializer.deserialize(data, dict[UUID, str])
        assert result == val

    def test_nested_complex_collections(self) -> None:
        """list[dict[str, set[int]]] roundtrip."""
        val = [{"a": {1, 2}, "b": {3}}, {"c": {4, 5, 6}}]
        data = Serializer.serialize(val)
        result = Serializer.deserialize(data, list[dict[str, set[int]]])
        assert result == val

    def test_dict_with_tuple_values(self) -> None:
        val = {"point": (1, 2, 3)}
        data = Serializer.serialize(val)
        result = Serializer.deserialize(data, dict[str, tuple[int, int, int]])
        assert result == {"point": (1, 2, 3)}


# ── Enum edge cases ─────────────────────────────────────────────────────────


class TestEnumEdgeCases:
    def test_flag_enum(self) -> None:
        class Perm(Flag):
            READ = 1
            WRITE = 2
            EXEC = 4

        data = Serializer.serialize(Perm.READ)
        result = Serializer.deserialize(data, Perm)
        assert result == Perm.READ

    def test_intflag_enum(self) -> None:
        class Perm(IntFlag):
            READ = 1
            WRITE = 2
            EXEC = 4

        data = Serializer.serialize(Perm.READ | Perm.WRITE)
        result = Serializer.deserialize(data, Perm)
        assert result == Perm.READ | Perm.WRITE

    def test_int_enum_in_list(self) -> None:
        class Priority(IntEnum):
            LOW = 1
            HIGH = 2

        data = Serializer.serialize([Priority.LOW, Priority.HIGH])
        result = Serializer.deserialize(data, list[Priority])
        assert result == [Priority.LOW, Priority.HIGH]


# ── Datetime edge cases ─────────────────────────────────────────────────────


class TestDatetimeEdgeCases:
    def test_datetime_with_fixed_offset(self) -> None:
        tz = timezone(timedelta(hours=5, minutes=30))
        dt = datetime(2026, 1, 15, 10, 30, 0, tzinfo=tz)
        data = Serializer.serialize(dt)
        result = Serializer.deserialize(data, datetime)
        # msgspec normalizes to UTC
        assert result == dt.astimezone(timezone.utc)

    def test_datetime_min_max(self) -> None:
        for dt in [datetime.min, datetime(9999, 12, 31, 23, 59, 59)]:
            data = Serializer.serialize(dt)
            result = Serializer.deserialize(data, datetime)
            assert result == dt

    def test_time_with_microseconds(self) -> None:
        t = time(12, 30, 45, 123456)
        data = Serializer.serialize(t)
        result = Serializer.deserialize(data, time)
        assert result == t

    def test_timedelta_large(self) -> None:
        td = timedelta(days=365 * 10, hours=5, microseconds=123)
        data = Serializer.serialize(td)
        result = Serializer.deserialize(data, timedelta)
        assert result == td


# ── Decimal edge cases ───────────────────────────────────────────────────────


class TestDecimalEdgeCases:
    def test_decimal_very_small(self) -> None:
        val = Decimal("0.000000001")
        data = Serializer.serialize(val)
        result = Serializer.deserialize(data, Decimal)
        assert result == val

    def test_decimal_negative_exponent(self) -> None:
        val = Decimal("1E-10")
        data = Serializer.serialize(val)
        result = Serializer.deserialize(data, Decimal)
        assert result == val

    def test_decimal_in_struct(self) -> None:
        class S(msgspec.Struct):
            price: Decimal

        obj = S(price=Decimal("19.99"))
        data = Serializer.serialize(obj)
        result = Serializer.deserialize(data, S)
        assert result.price == Decimal("19.99")


# ── Pydantic RootModel ──────────────────────────────────────────────────────


class TestPydanticRootModel:
    def test_root_model_list(self) -> None:
        MyList = pydantic.RootModel[list[int]]
        obj = MyList([1, 2, 3])
        data = Serializer.serialize(obj)
        result = Serializer.deserialize(data, MyList)
        assert result.root == [1, 2, 3]

    def test_root_model_dict(self) -> None:
        MyDict = pydantic.RootModel[dict[str, int]]
        obj = MyDict({"a": 1, "b": 2})
        data = Serializer.serialize(obj)
        result = Serializer.deserialize(data, MyDict)
        assert result.root == {"a": 1, "b": 2}

    def test_root_model_set(self) -> None:
        MySet = pydantic.RootModel[set[str]]
        obj = MySet({"x", "y"})
        data = Serializer.serialize(obj)
        result = Serializer.deserialize(data, MySet)
        assert result.root == {"x", "y"}

    def test_root_model_empty_list(self) -> None:
        MyList = pydantic.RootModel[list[int]]
        obj = MyList([])
        data = Serializer.serialize(obj)
        result = Serializer.deserialize(data, MyList)
        assert result.root == []

    def test_root_model_with_nested_pydantic(self) -> None:
        class Item(pydantic.BaseModel):
            name: str
            value: int

        MyList = pydantic.RootModel[list[Item]]
        obj = MyList([Item(name="a", value=1), Item(name="b", value=2)])
        data = Serializer.serialize(obj)
        result = Serializer.deserialize(data, MyList)
        assert len(result.root) == 2
        assert result.root[0].name == "a"
        assert result.root[1].value == 2


# ── Pydantic model_validator ─────────────────────────────────────────────────


class TestPydanticModelValidator:
    def test_model_validator_after(self) -> None:
        class M(pydantic.BaseModel):
            x: int
            y: int

            @pydantic.model_validator(mode="after")
            def check_sum(self) -> M:
                if self.x + self.y > 100:
                    raise ValueError("sum too large")
                return self

        obj = M(x=10, y=20)
        data = Serializer.serialize(obj)
        result = Serializer.deserialize(data, M)
        assert result.x == 10
        assert result.y == 20

    def test_model_validator_after_rejects_on_deserialize(self) -> None:
        class M(pydantic.BaseModel):
            x: int
            y: int

            @pydantic.model_validator(mode="after")
            def check_sum(self) -> M:
                if self.x + self.y > 100:
                    raise ValueError("sum too large")
                return self

        # Serialize valid data, then forge invalid bytes
        valid = M(x=10, y=20)
        data = Serializer.serialize(valid)

        # Forge bytes with x=60, y=50 (sum=110 > 100)
        import msgspec as ms
        forged = ms.msgpack.encode({"x": 60, "y": 50})
        with pytest.raises(DeserializeError, match="sum too large"):
            Serializer.deserialize(forged, M)

    def test_model_validator_before(self) -> None:
        class M(pydantic.BaseModel):
            name: str

            @pydantic.model_validator(mode="before")
            @classmethod
            def uppercase_name(cls, values: dict) -> dict:
                if isinstance(values, dict) and "name" in values:
                    values["name"] = values["name"].upper()
                return values

        obj = M(name="HELLO")
        data = Serializer.serialize(obj)
        result = Serializer.deserialize(data, M)
        assert result.name == "HELLO"


# ── Pydantic with Literal fields ────────────────────────────────────────────


class TestPydanticLiteral:
    def test_pydantic_with_literal_field(self) -> None:
        class M(pydantic.BaseModel):
            status: Literal["active", "inactive"]
            name: str

        obj = M(status="active", name="test")
        data = Serializer.serialize(obj)
        result = Serializer.deserialize(data, M)
        assert result.status == "active"
        assert result.name == "test"

    def test_discriminated_union_via_literal(self) -> None:
        """Test Pydantic models that use Literal for manual discrimination."""

        class Cat(pydantic.BaseModel):
            pet_type: Literal["cat"]
            meow: str

        class Dog(pydantic.BaseModel):
            pet_type: Literal["dog"]
            bark: str

        cat = Cat(pet_type="cat", meow="meow!")
        data = Serializer.serialize(cat)
        result = Serializer.deserialize(data, Cat)
        assert result.pet_type == "cat"
        assert result.meow == "meow!"

        dog = Dog(pet_type="dog", bark="woof!")
        data = Serializer.serialize(dog)
        result = Serializer.deserialize(data, Dog)
        assert result.pet_type == "dog"
        assert result.bark == "woof!"


# ── Pydantic inheritance ────────────────────────────────────────────────────


class TestPydanticInheritance:
    def test_simple_inheritance(self) -> None:
        class Base(pydantic.BaseModel):
            name: str

        class Child(Base):
            age: int

        obj = Child(name="Alice", age=30)
        data = Serializer.serialize(obj)
        result = Serializer.deserialize(data, Child)
        assert result.name == "Alice"
        assert result.age == 30

    def test_multi_level_inheritance(self) -> None:
        class A(pydantic.BaseModel):
            x: int

        class B(A):
            y: int

        class C(B):
            z: int

        obj = C(x=1, y=2, z=3)
        data = Serializer.serialize(obj)
        result = Serializer.deserialize(data, C)
        assert result.x == 1
        assert result.y == 2
        assert result.z == 3


# ── Empty / minimal structures ───────────────────────────────────────────────


class TestEmptyStructures:
    def test_empty_struct(self) -> None:
        class Empty(msgspec.Struct):
            pass

        obj = Empty()
        data = Serializer.serialize(obj)
        result = Serializer.deserialize(data, Empty)
        assert isinstance(result, Empty)

    def test_empty_dataclass(self) -> None:
        @dataclasses.dataclass
        class Empty:
            pass

        obj = Empty()
        data = Serializer.serialize(obj)
        result = Serializer.deserialize(data, Empty)
        assert isinstance(result, Empty)

    def test_empty_pydantic(self) -> None:
        class Empty(pydantic.BaseModel):
            pass

        obj = Empty()
        data = Serializer.serialize(obj)
        result = Serializer.deserialize(data, Empty)
        assert isinstance(result, Empty)


# ── Struct with Union/Literal/Optional combos ────────────────────────────────


class TestStructAdvancedTyping:
    def test_struct_with_union(self) -> None:
        class S(msgspec.Struct):
            value: Union[int, str]
            label: str

        for val in [42, "hello"]:
            obj = S(value=val, label="test")
            data = Serializer.serialize(obj)
            result = Serializer.deserialize(data, S)
            assert result.value == val

    def test_struct_with_literal(self) -> None:
        class S(msgspec.Struct):
            mode: Literal["fast", "slow"]

        obj = S(mode="fast")
        data = Serializer.serialize(obj)
        result = Serializer.deserialize(data, S)
        assert result.mode == "fast"

    def test_dataclass_with_union(self) -> None:
        @dataclasses.dataclass
        class DC:
            value: Union[int, str]

        for val in [42, "hello"]:
            obj = DC(value=val)
            data = Serializer.serialize(obj)
            result = Serializer.deserialize(data, DC)
            assert result.value == val

    def test_dataclass_with_literal(self) -> None:
        @dataclasses.dataclass
        class DC:
            status: Literal["on", "off"]

        obj = DC(status="on")
        data = Serializer.serialize(obj)
        result = Serializer.deserialize(data, DC)
        assert result.status == "on"
