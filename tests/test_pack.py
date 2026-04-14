"""Tests for self-describing pack/unpack with type-tagged serialization."""

from __future__ import annotations

import concurrent.futures
import dataclasses
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID

import msgspec
import pydantic
import pytest

from serializer import (
    DeserializeError,
    PackedResult,
    Serializer,
    SerializeError,
)


# -- Test models --


class PackModel(pydantic.BaseModel):
    name: str
    age: int


class AliasModel(pydantic.BaseModel):
    full_name: str = pydantic.Field(alias="fullName")

    model_config = pydantic.ConfigDict(populate_by_name=True)


class ComputedModel(pydantic.BaseModel):
    first: str
    last: str

    @pydantic.computed_field  # type: ignore[prop-decorator]
    @property
    def full(self) -> str:
        return f"{self.first} {self.last}"


class PackStruct(msgspec.Struct):
    x: int
    y: str


@dataclasses.dataclass
class PackPoint:
    x: float
    y: float


# -- PackedResult --


class TestPackedResult:
    def test_construction(self) -> None:
        r = PackedResult(value=42, type_name="int", is_custom=False)
        assert r.value == 42
        assert r.type_name == "int"
        assert r.is_custom is False

    def test_frozen_immutability(self) -> None:
        r = PackedResult(value="hello", type_name="str", is_custom=False)
        with pytest.raises(AttributeError, match="immutable"):
            r.value = "world"  # type: ignore[misc]

    def test_custom_type_result(self) -> None:
        r = PackedResult(value={"a": 1}, type_name="mod.MyClass", is_custom=True)
        assert r.is_custom is True
        assert r.type_name == "mod.MyClass"


# -- Pack --


class TestPack:
    def test_pack_int(self) -> None:
        data = Serializer.pack(42)
        assert isinstance(data, bytes)

    def test_pack_str(self) -> None:
        data = Serializer.pack("hello")
        assert isinstance(data, bytes)

    def test_pack_float(self) -> None:
        data = Serializer.pack(3.14)
        assert isinstance(data, bytes)

    def test_pack_bool(self) -> None:
        data = Serializer.pack(True)
        assert isinstance(data, bytes)

    def test_pack_none(self) -> None:
        data = Serializer.pack(None)
        assert isinstance(data, bytes)

    def test_pack_bytes(self) -> None:
        data = Serializer.pack(b"raw")
        assert isinstance(data, bytes)

    def test_pack_list(self) -> None:
        data = Serializer.pack([1, 2, 3])
        assert isinstance(data, bytes)

    def test_pack_dict(self) -> None:
        data = Serializer.pack({"key": "value"})
        assert isinstance(data, bytes)

    def test_pack_tuple(self) -> None:
        data = Serializer.pack((1, 2, 3))
        assert isinstance(data, bytes)

    def test_pack_set(self) -> None:
        data = Serializer.pack({1, 2, 3})
        assert isinstance(data, bytes)

    def test_pack_frozenset(self) -> None:
        data = Serializer.pack(frozenset([4, 5]))
        assert isinstance(data, bytes)

    def test_pack_datetime(self) -> None:
        data = Serializer.pack(datetime(2026, 1, 15, 12, 30))
        assert isinstance(data, bytes)

    def test_pack_date(self) -> None:
        data = Serializer.pack(date(2026, 1, 15))
        assert isinstance(data, bytes)

    def test_pack_time(self) -> None:
        data = Serializer.pack(time(12, 30, 45))
        assert isinstance(data, bytes)

    def test_pack_timedelta(self) -> None:
        data = Serializer.pack(timedelta(days=1, hours=2))
        assert isinstance(data, bytes)

    def test_pack_uuid(self) -> None:
        data = Serializer.pack(UUID("12345678-1234-5678-1234-567812345678"))
        assert isinstance(data, bytes)

    def test_pack_decimal(self) -> None:
        data = Serializer.pack(Decimal("3.14"))
        assert isinstance(data, bytes)

    def test_pack_pydantic_model(self) -> None:
        data = Serializer.pack(PackModel(name="Alice", age=30))
        assert isinstance(data, bytes)

    def test_pack_dataclass(self) -> None:
        data = Serializer.pack(PackPoint(x=1.0, y=2.0))
        assert isinstance(data, bytes)

    def test_pack_struct(self) -> None:
        data = Serializer.pack(PackStruct(x=1, y="a"))
        assert isinstance(data, bytes)

    def test_pack_tag_override(self) -> None:
        data = Serializer.pack({"key": "val"}, tag="MyAlias")
        assert isinstance(data, bytes)

    def test_pack_tag_collision_raises(self) -> None:
        with pytest.raises(SerializeError, match="collides with reserved"):
            Serializer.pack(42, tag="int")

    def test_pack_tag_collision_datetime(self) -> None:
        with pytest.raises(SerializeError, match="collides with reserved"):
            Serializer.pack({"a": 1}, tag="datetime")

    def test_pack_empty_tuple(self) -> None:
        data = Serializer.pack(())
        assert isinstance(data, bytes)

    def test_pack_empty_set(self) -> None:
        data = Serializer.pack(set())
        assert isinstance(data, bytes)

    def test_pack_empty_frozenset(self) -> None:
        data = Serializer.pack(frozenset())
        assert isinstance(data, bytes)

    def test_pack_empty_list(self) -> None:
        data = Serializer.pack([])
        assert isinstance(data, bytes)

    def test_pack_empty_dict(self) -> None:
        data = Serializer.pack({})
        assert isinstance(data, bytes)


# -- Unpack roundtrips for all 17 stdlib types --


class TestUnpackRoundtrip:
    def test_roundtrip_int(self) -> None:
        result = Serializer.unpack(Serializer.pack(42))
        assert result.value == 42
        assert result.type_name == "int"
        assert result.is_custom is False

    def test_roundtrip_float(self) -> None:
        result = Serializer.unpack(Serializer.pack(3.14))
        assert result.value == 3.14
        assert result.type_name == "float"
        assert result.is_custom is False

    def test_roundtrip_str(self) -> None:
        result = Serializer.unpack(Serializer.pack("hello"))
        assert result.value == "hello"
        assert result.type_name == "str"
        assert result.is_custom is False

    def test_roundtrip_bool_true(self) -> None:
        result = Serializer.unpack(Serializer.pack(True))
        assert result.value is True
        assert result.type_name == "bool"
        assert result.is_custom is False

    def test_roundtrip_bool_false(self) -> None:
        result = Serializer.unpack(Serializer.pack(False))
        assert result.value is False
        assert result.type_name == "bool"
        assert result.is_custom is False

    def test_roundtrip_none(self) -> None:
        result = Serializer.unpack(Serializer.pack(None))
        assert result.value is None
        assert result.type_name == "NoneType"
        assert result.is_custom is False

    def test_roundtrip_bytes(self) -> None:
        result = Serializer.unpack(Serializer.pack(b"raw"))
        assert result.value == b"raw"
        assert result.type_name == "bytes"
        assert result.is_custom is False

    def test_roundtrip_list(self) -> None:
        result = Serializer.unpack(Serializer.pack([1, "two", 3.0]))
        assert result.value == [1, "two", 3.0]
        assert result.type_name == "list"
        assert result.is_custom is False

    def test_roundtrip_dict(self) -> None:
        result = Serializer.unpack(Serializer.pack({"a": 1, "b": 2}))
        assert result.value == {"a": 1, "b": 2}
        assert result.type_name == "dict"
        assert result.is_custom is False

    def test_roundtrip_tuple(self) -> None:
        result = Serializer.unpack(Serializer.pack((1, 2, 3)))
        assert result.value == (1, 2, 3)
        assert isinstance(result.value, tuple)
        assert result.type_name == "tuple"
        assert result.is_custom is False

    def test_roundtrip_set(self) -> None:
        result = Serializer.unpack(Serializer.pack({1, 2, 3}))
        assert result.value == {1, 2, 3}
        assert isinstance(result.value, set)
        assert result.type_name == "set"
        assert result.is_custom is False

    def test_roundtrip_frozenset(self) -> None:
        result = Serializer.unpack(Serializer.pack(frozenset([4, 5])))
        assert result.value == frozenset([4, 5])
        assert isinstance(result.value, frozenset)
        assert result.type_name == "frozenset"
        assert result.is_custom is False

    def test_roundtrip_datetime(self) -> None:
        val = datetime(2026, 1, 15, 12, 30, 45, 123456)
        result = Serializer.unpack(Serializer.pack(val))
        assert result.value == val
        assert result.type_name == "datetime"
        assert result.is_custom is False

    def test_roundtrip_date(self) -> None:
        val = date(2026, 1, 15)
        result = Serializer.unpack(Serializer.pack(val))
        assert result.value == val
        assert result.type_name == "date"
        assert result.is_custom is False

    def test_roundtrip_time(self) -> None:
        val = time(12, 30, 45)
        result = Serializer.unpack(Serializer.pack(val))
        assert result.value == val
        assert result.type_name == "time"
        assert result.is_custom is False

    def test_roundtrip_timedelta(self) -> None:
        val = timedelta(days=1, hours=2, minutes=30)
        result = Serializer.unpack(Serializer.pack(val))
        assert result.value == val
        assert result.type_name == "timedelta"
        assert result.is_custom is False

    def test_roundtrip_uuid(self) -> None:
        val = UUID("12345678-1234-5678-1234-567812345678")
        result = Serializer.unpack(Serializer.pack(val))
        assert result.value == val
        assert result.type_name == "UUID"
        assert result.is_custom is False

    def test_roundtrip_decimal(self) -> None:
        val = Decimal("3.14159")
        result = Serializer.unpack(Serializer.pack(val))
        assert result.value == val
        assert result.type_name == "Decimal"
        assert result.is_custom is False

    def test_roundtrip_empty_tuple(self) -> None:
        result = Serializer.unpack(Serializer.pack(()))
        assert result.value == ()
        assert isinstance(result.value, tuple)

    def test_roundtrip_empty_set(self) -> None:
        result = Serializer.unpack(Serializer.pack(set()))
        assert result.value == set()
        assert isinstance(result.value, set)

    def test_roundtrip_empty_frozenset(self) -> None:
        result = Serializer.unpack(Serializer.pack(frozenset()))
        assert result.value == frozenset()
        assert isinstance(result.value, frozenset)

    def test_nested_container_inner_tuple_stays_list(self) -> None:
        """Inner tuples are not reconstructed — they stay as lists."""
        result = Serializer.unpack(Serializer.pack([1, (2, 3)]))
        assert result.value == [1, [2, 3]]
        assert result.type_name == "list"


# -- Custom types roundtrip --


class TestCustomTypeRoundtrip:
    def test_pydantic_model(self) -> None:
        model = PackModel(name="Alice", age=30)
        result = Serializer.unpack(Serializer.pack(model))
        assert result.value == {"name": "Alice", "age": 30}
        assert "PackModel" in result.type_name
        assert result.is_custom is True

    def test_pydantic_model_with_alias(self) -> None:
        """Pydantic model using MODEL_DUMP strategy (has aliases)."""
        model = AliasModel(fullName="Bob Smith")
        result = Serializer.unpack(Serializer.pack(model))
        assert result.is_custom is True
        assert isinstance(result.value, dict)

    def test_pydantic_model_with_computed_field(self) -> None:
        """Pydantic model with computed field uses MODEL_DUMP strategy."""
        model = ComputedModel(first="Jane", last="Doe")
        result = Serializer.unpack(Serializer.pack(model))
        assert result.is_custom is True
        assert result.value["full"] == "Jane Doe"

    def test_dataclass(self) -> None:
        point = PackPoint(x=1.0, y=2.0)
        result = Serializer.unpack(Serializer.pack(point))
        assert result.value == {"x": 1.0, "y": 2.0}
        assert "PackPoint" in result.type_name
        assert result.is_custom is True

    def test_struct(self) -> None:
        item = PackStruct(x=1, y="a")
        result = Serializer.unpack(Serializer.pack(item))
        assert result.value == {"x": 1, "y": "a"}
        assert "PackStruct" in result.type_name
        assert result.is_custom is True

    def test_tag_override(self) -> None:
        model = PackModel(name="Alice", age=30)
        result = Serializer.unpack(Serializer.pack(model, tag="MyAlias"))
        assert result.type_name == "MyAlias"
        assert result.is_custom is True
        assert result.value == {"name": "Alice", "age": 30}

    def test_tag_override_on_stdlib_type(self) -> None:
        """Tag override on a list makes it custom."""
        result = Serializer.unpack(Serializer.pack([1, 2], tag="my_list"))
        assert result.type_name == "my_list"
        assert result.is_custom is True
        assert result.value == [1, 2]

    def test_fully_qualified_name_includes_module(self) -> None:
        result = Serializer.unpack(Serializer.pack(PackModel(name="X", age=1)))
        # Module should include tests.test_pack or __main__ or similar
        assert "." in result.type_name
        assert "PackModel" in result.type_name


# -- Error paths --


class TestPackUnpackErrors:
    def test_unpack_corrupted_bytes(self) -> None:
        with pytest.raises(DeserializeError):
            Serializer.unpack(b"\xff\xfe\xfd")

    def test_unpack_not_array(self) -> None:
        data = msgspec.msgpack.encode(42)
        with pytest.raises(DeserializeError, match="\\[tag, data\\] array"):
            Serializer.unpack(data)

    def test_unpack_wrong_array_length(self) -> None:
        data = msgspec.msgpack.encode([1, 2, 3])
        with pytest.raises(DeserializeError):
            Serializer.unpack(data)

    def test_unpack_single_element_array(self) -> None:
        data = msgspec.msgpack.encode(["int"])
        with pytest.raises(DeserializeError):
            Serializer.unpack(data)

    def test_unpack_non_string_tag(self) -> None:
        data = msgspec.msgpack.encode([42, "data"])
        with pytest.raises(DeserializeError, match="Tag must be a string"):
            Serializer.unpack(data)

    def test_unpack_tag_data_mismatch_datetime(self) -> None:
        data = msgspec.msgpack.encode(["datetime", "not-a-valid-date"])
        with pytest.raises(DeserializeError):
            Serializer.unpack(data)

    def test_unpack_tag_data_mismatch_uuid(self) -> None:
        data = msgspec.msgpack.encode(["UUID", "not-a-uuid"])
        with pytest.raises(DeserializeError):
            Serializer.unpack(data)

    def test_unpack_tag_data_mismatch_wrong_type(self) -> None:
        """Tag says datetime but data is an int, not a string."""
        data = msgspec.msgpack.encode(["datetime", 42])
        with pytest.raises(DeserializeError):
            Serializer.unpack(data)

    def test_unpack_error_has_cause(self) -> None:
        data = msgspec.msgpack.encode(["datetime", "invalid"])
        with pytest.raises(DeserializeError) as exc_info:
            Serializer.unpack(data)
        assert exc_info.value.__cause__ is not None

    def test_pack_tag_collision_all_reserved(self) -> None:
        """All 17 reserved tags should raise on collision."""
        from serializer._pack import RESERVED_TAGS

        for tag in RESERVED_TAGS:
            with pytest.raises(SerializeError, match="collides"):
                Serializer.pack({"x": 1}, tag=tag)

    def test_unpack_container_coerce_non_iterable_payload(self) -> None:
        """Container-coerce tags with non-iterable payloads raise DeserializeError."""
        for tag in ("set", "tuple", "frozenset"):
            data = msgspec.msgpack.encode([tag, None])
            with pytest.raises(DeserializeError):
                Serializer.unpack(data)

    def test_unpack_container_coerce_int_payload(self) -> None:
        """Container-coerce tags with int payloads raise DeserializeError."""
        data = msgspec.msgpack.encode(["tuple", 42])
        with pytest.raises(DeserializeError):
            Serializer.unpack(data)

    def test_pack_serialize_error_has_cause(self) -> None:
        """Non-serializable objects produce SerializeError with cause."""

        class Unsupported:
            pass

        with pytest.raises(SerializeError) as exc_info:
            Serializer.pack(Unsupported())
        assert exc_info.value.__cause__ is not None


# -- Thread safety --


class TestPackUnpackThreadSafety:
    def test_concurrent_pack_mixed_types(self) -> None:
        """Multiple threads packing different types simultaneously."""

        def work(i: int) -> bytes:
            if i % 4 == 0:
                return Serializer.pack(i)
            elif i % 4 == 1:
                return Serializer.pack(datetime(2026, 1, i % 28 + 1))
            elif i % 4 == 2:
                return Serializer.pack(PackModel(name=f"u{i}", age=i))
            else:
                return Serializer.pack((i, i + 1))

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(work, i) for i in range(100)]
            results = [f.result() for f in futures]

        assert len(results) == 100
        assert all(isinstance(r, bytes) for r in results)

    def test_concurrent_unpack_mixed_types(self) -> None:
        """Multiple threads unpacking different types simultaneously."""
        packed_data = [
            Serializer.pack(42),
            Serializer.pack("hello"),
            Serializer.pack(datetime(2026, 1, 1)),
            Serializer.pack(Decimal("9.99")),
            Serializer.pack((1, 2)),
            Serializer.pack({3, 4}),
        ]

        def work(i: int) -> PackedResult:
            return Serializer.unpack(packed_data[i % len(packed_data)])

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(work, i) for i in range(100)]
            results = [f.result() for f in futures]

        assert len(results) == 100
        assert all(isinstance(r, PackedResult) for r in results)

    def test_concurrent_roundtrip(self) -> None:
        """Full roundtrip from multiple threads — verifies correctness."""

        def work(i: int) -> bool:
            val = i * 100
            result = Serializer.unpack(Serializer.pack(val))
            return result.value == val and result.is_custom is False

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(work, i) for i in range(100)]
            results = [f.result() for f in futures]

        assert all(results)


# -- Existing API unchanged --


class TestExistingApiUnchanged:
    def test_serialize_still_works(self) -> None:
        data = Serializer.serialize(42)
        assert Serializer.deserialize(data, int) == 42

    def test_serialize_pydantic_still_works(self) -> None:
        model = PackModel(name="Test", age=1)
        data = Serializer.serialize(model)
        result = Serializer.deserialize(data, PackModel)
        assert result == model

    def test_serialize_struct_still_works(self) -> None:
        item = PackStruct(x=1, y="a")
        data = Serializer.serialize(item)
        result = Serializer.deserialize(data, PackStruct)
        assert result == item
