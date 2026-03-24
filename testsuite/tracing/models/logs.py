"""Log-related data models for distributed tracing."""

from dataclasses import dataclass


@dataclass(frozen=True)
class LogField:
    """Represents a single field in a span log entry."""

    key: str
    value: str
    type: str = "string"


@dataclass(frozen=True)
class LogEntry:
    """
    Represents a log entry in a span.

    Note: Frozen to prevent accidental modification. The fields list is immutable
    from reassignment but its contents should not be modified.
    """

    timestamp: int
    fields: list[LogField]

    @classmethod
    def from_dict(cls, data: dict) -> "LogEntry":
        """Create LogEntry from Jaeger API response dict."""
        fields = []
        for f in data.get("fields", []):
            key = f.get("key", "").strip()
            if not key:  # Skip fields without keys or whitespace-only keys
                continue
            fields.append(
                LogField(key=key, value=f.get("value", ""), type=f.get("type", "string"))
            )
        return cls(timestamp=data.get("timestamp", 0), fields=fields)

    def get_field(self, key: str) -> str | None:
        """Get field value by key. Returns first match if multiple fields have same key."""
        for field in self.fields:
            if field.key == key:
                return field.value
        return None

    def has_field(self, key: str, value: str | None = None) -> bool:
        """Check if log entry has a field with exact value match."""
        field_value = self.get_field(key)
        if field_value is None:
            return False
        if value is None:
            return True
        return value == field_value

    def field_contains(self, key: str, substring: str) -> bool:
        """Check if field value contains substring (case-insensitive)."""
        field_value = self.get_field(key)
        if field_value is None:
            return False
        return substring.lower() in field_value.lower()