"""Benchmarks comparing Serializer overhead vs native msgspec."""

from __future__ import annotations

import dataclasses
import timeit

import msgspec
import pydantic

from serializer import Serializer


# -- Test fixtures --

class SmallStruct(msgspec.Struct):
    a: int
    b: str
    c: float
    d: bool
    e: bytes


@dataclasses.dataclass
class SmallDataclass:
    a: int
    b: str
    c: float
    d: bool
    e: bytes


class SmallPydantic(pydantic.BaseModel):
    a: int
    b: str
    c: float
    d: bool
    e: bytes


SMALL_STRUCT = SmallStruct(a=42, b="hello", c=3.14, d=True, e=b"\x01")
SMALL_DC = SmallDataclass(a=42, b="hello", c=3.14, d=True, e=b"\x01")
SMALL_PYD = SmallPydantic(a=42, b="hello", c=3.14, d=True, e=b"\x01")


def bench(label: str, fn, *, number: int = 100_000, warmup: int = 1000) -> float:
    for _ in range(warmup):
        fn()
    total = timeit.timeit(fn, number=number)
    per_call_ns = (total / number) * 1e9
    print(f"  {label:.<55s} {per_call_ns:>8.0f} ns/call")
    return per_call_ns


def main() -> None:
    native_enc = msgspec.msgpack.Encoder()
    native_dec_struct = msgspec.msgpack.Decoder(SmallStruct)
    native_dec_dc = msgspec.msgpack.Decoder(SmallDataclass)

    struct_bytes = native_enc.encode(SMALL_STRUCT)
    dc_bytes = native_enc.encode(SMALL_DC)
    pyd_bytes = Serializer.serialize(SMALL_PYD)

    print("\n=== SERIALIZE ===\n")

    native_struct = bench("native msgspec encode (Struct)", lambda: native_enc.encode(SMALL_STRUCT))
    ser_struct = bench("Serializer.serialize (Struct)", lambda: Serializer.serialize(SMALL_STRUCT))
    overhead = ((ser_struct - native_struct) / native_struct) * 100
    print(f"  -> Struct overhead: {overhead:.1f}% (target: <5%)\n")

    native_dc = bench("native msgspec encode (dataclass)", lambda: native_enc.encode(SMALL_DC))
    ser_dc = bench("Serializer.serialize (dataclass)", lambda: Serializer.serialize(SMALL_DC))
    overhead = ((ser_dc - native_dc) / native_dc) * 100
    print(f"  -> Dataclass overhead: {overhead:.1f}% (target: <15%)\n")

    baseline_pyd = bench(
        "pydantic model_dump + msgspec encode",
        lambda: native_enc.encode(SMALL_PYD.model_dump(mode="python")),
    )
    ser_pyd = bench("Serializer.serialize (Pydantic)", lambda: Serializer.serialize(SMALL_PYD))
    ratio = ser_pyd / baseline_pyd
    print(f"  -> Pydantic ratio vs baseline: {ratio:.2f}x (target: ~1.0x parity)\n")

    print("\n=== DESERIALIZE ===\n")

    native_struct_dec = bench("native msgspec decode (Struct)", lambda: native_dec_struct.decode(struct_bytes))
    ser_struct_dec = bench("Serializer.deserialize (Struct)", lambda: Serializer.deserialize(struct_bytes, SmallStruct))
    overhead = ((ser_struct_dec - native_struct_dec) / native_struct_dec) * 100
    print(f"  -> Struct decode overhead: {overhead:.1f}%\n")

    native_dc_dec = bench("native msgspec decode (dataclass)", lambda: native_dec_dc.decode(dc_bytes))
    ser_dc_dec = bench("Serializer.deserialize (dataclass)", lambda: Serializer.deserialize(dc_bytes, SmallDataclass))
    overhead = ((ser_dc_dec - native_dc_dec) / native_dc_dec) * 100
    print(f"  -> Dataclass decode overhead: {overhead:.1f}%\n")

    baseline_pyd_dec = bench(
        "msgspec decode + model_validate",
        lambda: SmallPydantic.model_validate(msgspec.msgpack.decode(pyd_bytes)),
    )
    ser_pyd_dec = bench("Serializer.deserialize (Pydantic)", lambda: Serializer.deserialize(pyd_bytes, SmallPydantic))
    ratio = ser_pyd_dec / baseline_pyd_dec
    print(f"  -> Pydantic decode ratio vs baseline: {ratio:.2f}x\n")


if __name__ == "__main__":
    main()
