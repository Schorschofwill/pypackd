# pypackd

Unified Python serializer with msgspec MessagePack backend. One API for all your types — Pydantic, msgspec Structs, dataclasses, and every stdlib type.

## Installation

```bash
pip install pypackd
```

With Pydantic support:

```bash
pip install pypackd[pydantic]
```

## Usage

```python
from serializer import Serializer

# Serialize any supported type
data = Serializer.serialize(my_object)

# Deserialize with target type
obj = Serializer.deserialize(data, MyType)
```

### Primitives & Collections

```python
Serializer.deserialize(Serializer.serialize(42), int)           # 42
Serializer.deserialize(Serializer.serialize("hello"), str)      # "hello"
Serializer.deserialize(Serializer.serialize([1, 2, 3]), list)   # [1, 2, 3]
Serializer.deserialize(Serializer.serialize({10, 20}), set)     # {10, 20}
```

### Dataclasses

```python
from dataclasses import dataclass

@dataclass
class Point:
    x: float
    y: float

p = Point(3.14, 2.72)
data = Serializer.serialize(p)
Serializer.deserialize(data, Point)  # Point(x=3.14, y=2.72)
```

### msgspec Structs

```python
import msgspec

class Config(msgspec.Struct):
    host: str
    port: int
    debug: bool = False

cfg = Config(host="localhost", port=8080)
data = Serializer.serialize(cfg)
Serializer.deserialize(data, Config)  # Config(host='localhost', port=8080, debug=False)
```

### Pydantic Models

```python
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

class User(BaseModel):
    id: UUID
    name: str
    created_at: datetime

user = User(id=UUID("abcdef01-2345-6789-abcd-ef0123456789"), name="Georg", created_at=datetime.now())
data = Serializer.serialize(user)
Serializer.deserialize(data, User)  # User(id=UUID('abcdef01-...'), name='Georg', ...)
```

### Nested Types

Pydantic models with dataclass fields, nested Pydantic models, or any combination — it just works.

```python
@dataclass
class Address:
    street: str
    city: str

class Order(BaseModel):
    order_id: int
    customer: User
    shipping: Address
    items: list[str]

order = Order(order_id=1, customer=user, shipping=Address("Hauptstr. 1", "Berlin"), items=["Laptop"])
data = Serializer.serialize(order)
Serializer.deserialize(data, Order)  # Full roundtrip with all nested types
```

## Supported Types

| Category | Types |
|----------|-------|
| Primitives | `str`, `int`, `float`, `bool`, `None`, `bytes` |
| Collections | `list`, `dict`, `tuple`, `set`, `frozenset` |
| Datetime | `datetime`, `date`, `time`, `timedelta` |
| Stdlib | `UUID`, `Decimal`, `Enum` |
| Structured | `dataclass`, `NamedTuple`, `TypedDict`, `msgspec.Struct` |
| Pydantic | `BaseModel` (incl. computed fields, aliases, excluded fields, custom serializers) |
| Typing | `Optional`, `Union`, `Literal`, generics |

## How It Works

pypackd is a thin adapter layer over [msgspec](https://jcristharif.com/msgspec/), which handles all non-Pydantic types natively with zero overhead. For Pydantic models, pypackd auto-detects the model's features and chooses the fastest serialization path:

- **Simple models** → `obj.__dict__` (2-5x faster than `model_dump()`)
- **Models with computed fields, aliases, excluded fields, or custom serializers** → `model_dump(mode='python')` for correctness

Type classifications are cached, Encoder/Decoder instances are reused, and all cache writes are thread-safe.

## Error Handling

All errors are wrapped in a unified exception hierarchy:

```python
from serializer import SerializerError, SerializeError, DeserializeError

try:
    Serializer.deserialize(data, MyModel)
except DeserializeError as e:
    print(e)            # Descriptive message
    print(e.__cause__)  # Original pydantic/msgspec exception
```

## Requirements

- Python 3.10+
- msgspec >= 0.18
- pydantic >= 2.0 (optional)

## License

MIT
