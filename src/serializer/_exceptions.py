"""Custom exception hierarchy for the serializer."""


class SerializerError(Exception):
    """Base exception for all serializer errors."""


class SerializeError(SerializerError):
    """Raised when serialization fails."""


class DeserializeError(SerializerError):
    """Raised when deserialization fails."""
