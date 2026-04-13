# Serializer

Unified Python serializer with msgspec MessagePack backend. Supports all msgspec-native types plus Pydantic BaseModels.

## Project Structure

```
src/serializer/         # Library source
  _dispatch.py          # Type detection and cached dispatch (Pydantic vs native)
  _pydantic.py          # Pydantic enc_hook and deserialize_pydantic
  _core.py              # Serializer class (public API)
  _exceptions.py        # SerializerError, SerializeError, DeserializeError
tests/                  # pytest test suite
benchmarks/             # Performance benchmarks
docs/brainstorms/       # Requirements documents
docs/plans/             # Implementation plans
docs/solutions/         # Documented solutions and learnings, organized by category with YAML frontmatter (module, tags, problem_type)
```

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest
```

## Key Design Decisions

- msgspec handles all non-Pydantic types natively — the library is a thin Pydantic adapter
- `__dict__` fast-path for simple Pydantic models, `model_dump()` fallback for models with computed fields, excluded fields, aliases, or custom serializers
- Thread-safe type dispatch cache with `threading.Lock` on writes
- Custom exception hierarchy wrapping backend exceptions
