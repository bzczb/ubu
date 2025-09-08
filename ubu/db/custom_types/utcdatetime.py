# Entirely written by Claude Sonnet 4
"""UTC DateTime type for SQLAlchemy that ensures timezone-aware datetime objects."""

from datetime import UTC

from sqlalchemy import DateTime, TypeDecorator


class UTCDateTime(TypeDecorator):
    """Platform-independent UTC datetime type.

    Stores datetime as UTC in the database and returns timezone-aware
    datetime objects with UTC timezone when loaded from the database.

    By default, SQLAlchemy was returning naive datetime, which was too easily
    interpreted as local timezone.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Convert datetime to UTC before storing in database."""
        if value is not None:
            if value.tzinfo is None:
                # Assume naive datetime is already in UTC
                return value
            else:
                # Convert timezone-aware datetime to UTC
                return value.astimezone(UTC).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        """Convert datetime from database to UTC timezone-aware datetime."""
        if value is not None:
            # SQLite stores as naive datetime, but we know it's UTC
            return value.replace(tzinfo=UTC)
        return value
