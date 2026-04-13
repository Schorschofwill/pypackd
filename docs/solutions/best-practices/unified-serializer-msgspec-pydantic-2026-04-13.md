---
title: "Building a Unified Serializer with msgspec and Pydantic"
date: 2026-04-13
category: best-practices
module: serializer
problem_type: best_practice
component: tooling
severity: medium
applies_when:
  - Building a Python serializer that must handle multiple model systems (Pydantic, msgspec, dataclasses)
  - Wrapping msgspec for transparent Pydantic BaseModel support
  - Optimizing serialization performance in IPC/network scenarios
tags:
  - msgspec
  - pydantic
  - messagepack
  - serialization
  - enc-hook
  - performance
  - type-dispatch
---

# Building a Unified Serializer with msgspec and Pydantic

## Context

When building a Python library that serializes arbitrary types via MessagePack, the initial assumption was that many stdlib types (set, frozenset, datetime, UUID, Decimal, Enum, dataclasses, NamedTuple, TypedDict) would need custom `enc_hook`/`dec_hook` handling in msgspec. This led to over-scoping the project and planning unnecessary conversion logic. Additionally, using Pydantic's `obj.__dict__` as a fast serialization path has correctness pitfalls that aren't immediately obvious.

## Guidance

### 1. msgspec's native type coverage is much broader than commonly assumed

msgspec (0.21+) natively handles **all** of the following without any `enc_hook`:

| Category | Types |
|----------|-------|
| Primitives | str, int, float, bool, None, bytes |
| Collections | list, dict, tuple, set, frozenset |
| Datetime | datetime, date, time, timedelta |
| Stdlib | UUID, Decimal, Enum |
| Structured | msgspec.Struct, dataclass, NamedTuple, TypedDict |
| Typing | Optional, Union, Literal, generics |

**The only major Python model system msgspec does NOT handle natively is Pydantic BaseModel.** This means a "unified serializer" wrapping msgspec is really just a thin Pydantic adapter layer — all other types pass through with zero overhead.

### 2. Use `__dict__` for Pydantic serialization, but detect when `model_dump()` is required

`obj.__dict__` is 2-5x faster than `model_dump()` for flat Pydantic models because it avoids pydantic-core's Rust-backed recursive serialization pipeline. However, `__dict__` silently produces **wrong output** for models with:

- `@model_serializer` — custom serialization shape is bypassed entirely
- `Field(exclude=True)` — excluded fields leak into serialized data
- `@field_serializer` — custom field transformations are skipped
- `alias=` or `serialization_alias=` — wire bytes use Python attribute names instead of declared aliases
- `extra='allow'` — extra fields stored in `__pydantic_extra__` are dropped
- `@computed_field` — computed values are absent from output

**Detection at classification time:** Inspect the model class once, cache the decision:

```python
def _determine_strategy(tp: type) -> Strategy:
    has_computed = bool(getattr(tp, "model_computed_fields", None))
    config = getattr(tp, "model_config", {})
    has_extra = config.get("extra") == "allow"
    fields = getattr(tp, "model_fields", {})
    has_excluded = any(getattr(f, "exclude", False) for f in fields.values())
    has_alias = any(
        getattr(f, "alias", None) or getattr(f, "serialization_alias", None)
        for f in fields.values()
    )
    schema = getattr(tp, "__pydantic_core_schema__", {})
    has_serializer = schema.get("serialization", {}).get("type") in (
        "function-plain", "function-wrap"
    )
    if any([has_computed, has_extra, has_excluded, has_alias, has_serializer]):
        return Strategy.MODEL_DUMP
    return Strategy.DICT
```

### 3. Pydantic deserialization: untyped decode + model_validate works because of string coercion

msgspec encodes datetime as ISO 8601 strings, UUID as canonical strings, Decimal as strings. Untyped `msgspec.msgpack.decode(data)` returns these as plain Python strings. This is fine for the Pydantic path because `model_validate()` coerces strings to the correct types automatically.

For non-Pydantic types, use typed `msgspec.msgpack.Decoder(type=T)` which handles the conversion natively and can be cached per target type.

### 4. Thread-safe type dispatch with plain dict cache

Plain `dict[type, Callable]` lookup is the fastest caching strategy (~0ns lookup vs ~50-100ns for `lru_cache`). Use `threading.Lock` only for cache writes to future-proof for free-threaded Python (PEP 703). Cache reads are safe without the lock under CPython's GIL.

### 5. The enc_hook C→Python→C round-trip has measurable overhead

When msgspec encounters a non-native type during encoding, it calls `enc_hook` in Python, receives a dict, then re-encodes that dict in C. This C→Python→C boundary crossing adds ~600-800ns per Pydantic model. Pre-dispatching (classifying the type before calling encode) doesn't help because it adds overhead to the native path where enc_hook is never called.

**Accept the overhead for Pydantic types** — the alternative (pre-dispatch) makes native types slower while only marginally improving Pydantic types.

## Why This Matters

- **Over-scoping:** Assuming msgspec needs custom hooks for stdlib types leads to unnecessary code, unnecessary Phase 2 scoping, and wasted planning effort. Verify the library's actual capabilities before designing around assumed gaps.
- **Silent data corruption:** Using `__dict__` without detecting Pydantic serialization features produces structurally wrong wire data with no error — the most dangerous kind of bug. Fields are silently dropped, leaked, or transformed incorrectly.
- **Performance tradeoffs:** The intuition that "pre-converting should be faster" is wrong for this architecture. The enc_hook pattern is slower for Pydantic but faster overall because it adds zero overhead to native types.

## When to Apply

- Building any Python library that wraps msgspec for additional type support
- Choosing between `__dict__` and `model_dump()` for Pydantic serialization
- Designing a type-dispatch caching strategy for hot-path serialization
- Evaluating whether to pre-classify types before encoding vs letting enc_hook handle dispatch

## Examples

**Before (wrong assumption):**
```python
# Assumed these need enc_hook — they don't!
def enc_hook(obj):
    if isinstance(obj, set): return list(obj)
    if isinstance(obj, Decimal): return str(obj)
    if isinstance(obj, datetime): return obj.isoformat()
```

**After (correct — msgspec handles all of these natively):**
```python
# enc_hook only needed for Pydantic
def enc_hook(obj):
    if isinstance(obj, BaseModel):
        strategy = get_cached_strategy(type(obj))
        if strategy is Strategy.MODEL_DUMP:
            return obj.model_dump(mode="python")
        return obj.__dict__
    raise TypeError(f"Unsupported type: {type(obj).__qualname__}")
```

## Related

- [msgspec Supported Types](https://jcristharif.com/msgspec/supported-types.html)
- [msgspec Extending](https://jcristharif.com/msgspec/extending.html)
- [Pydantic v2 Serialization](https://docs.pydantic.dev/latest/concepts/serialization/)
- `docs/brainstorms/unified-serializer-requirements.md`
- `docs/plans/2026-04-13-001-feat-unified-serializer-plan.md`
