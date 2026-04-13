"""Thread safety tests — concurrent access to serialize/deserialize and caches."""

from __future__ import annotations

import concurrent.futures
import dataclasses

import msgspec
import pydantic

from serializer import Serializer


class ThreadModel(pydantic.BaseModel):
    value: int
    label: str


class ThreadStruct(msgspec.Struct):
    x: int
    y: str


@dataclasses.dataclass
class ThreadDataclass:
    a: int
    b: str


class TestConcurrentSerialize:
    def test_concurrent_serialize_pydantic(self) -> None:
        """Multiple threads serializing different Pydantic models simultaneously."""
        def work(i: int) -> bytes:
            return Serializer.serialize(ThreadModel(value=i, label=f"item_{i}"))

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(work, i) for i in range(100)]
            results = [f.result() for f in futures]

        assert len(results) == 100
        assert all(isinstance(r, bytes) for r in results)

    def test_concurrent_serialize_native(self) -> None:
        """Multiple threads serializing structs simultaneously."""
        def work(i: int) -> bytes:
            return Serializer.serialize(ThreadStruct(x=i, y=f"s_{i}"))

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(work, i) for i in range(100)]
            results = [f.result() for f in futures]

        assert len(results) == 100

    def test_concurrent_serialize_mixed(self) -> None:
        """Multiple threads serializing different type systems simultaneously."""
        def work(i: int) -> bytes:
            if i % 3 == 0:
                return Serializer.serialize(ThreadModel(value=i, label=f"m_{i}"))
            elif i % 3 == 1:
                return Serializer.serialize(ThreadStruct(x=i, y=f"s_{i}"))
            else:
                return Serializer.serialize(ThreadDataclass(a=i, b=f"d_{i}"))

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(work, i) for i in range(100)]
            results = [f.result() for f in futures]

        assert len(results) == 100


class TestConcurrentDeserialize:
    def test_concurrent_deserialize_pydantic(self) -> None:
        """Multiple threads deserializing the same Pydantic type simultaneously."""
        data = Serializer.serialize(ThreadModel(value=42, label="test"))

        def work(_: int) -> ThreadModel:
            return Serializer.deserialize(data, ThreadModel)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(work, i) for i in range(100)]
            results = [f.result() for f in futures]

        assert all(r == ThreadModel(value=42, label="test") for r in results)

    def test_concurrent_deserialize_struct(self) -> None:
        """Multiple threads deserializing the same Struct type simultaneously."""
        data = Serializer.serialize(ThreadStruct(x=1, y="a"))

        def work(_: int) -> ThreadStruct:
            return Serializer.deserialize(data, ThreadStruct)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(work, i) for i in range(100)]
            results = [f.result() for f in futures]

        assert all(r == ThreadStruct(x=1, y="a") for r in results)

    def test_concurrent_classify_same_new_type(self) -> None:
        """Multiple threads classifying the same previously-unseen type simultaneously."""
        # Define a fresh type that has never been cached
        class FreshModel(pydantic.BaseModel):
            v: int

        from serializer._dispatch import classify_type, TypeCategory

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
            futures = [pool.submit(classify_type, FreshModel) for _ in range(50)]
            results = [f.result() for f in futures]

        assert all(r == TypeCategory.PYDANTIC for r in results)


class TestConcurrentRoundtrip:
    def test_concurrent_roundtrip_mixed(self) -> None:
        """Full roundtrip with mixed types from multiple threads."""
        pyd_data = Serializer.serialize(ThreadModel(value=1, label="p"))
        struct_data = Serializer.serialize(ThreadStruct(x=2, y="s"))
        dc_data = Serializer.serialize(ThreadDataclass(a=3, b="d"))

        def work(i: int) -> bool:
            if i % 3 == 0:
                r = Serializer.deserialize(pyd_data, ThreadModel)
                return r == ThreadModel(value=1, label="p")
            elif i % 3 == 1:
                r = Serializer.deserialize(struct_data, ThreadStruct)
                return r == ThreadStruct(x=2, y="s")
            else:
                r = Serializer.deserialize(dc_data, ThreadDataclass)
                return r == ThreadDataclass(a=3, b="d")

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(work, i) for i in range(100)]
            results = [f.result() for f in futures]

        assert all(results)
