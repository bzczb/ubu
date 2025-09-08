# Attribution:
# https://gist.github.com/gmolveau/7caeeefe637679005a7bb9ae1b5e421e?permalink_comment_id=4158031#gistcomment-4158031

import uuid

from sqlalchemy import CHAR, UUID, TypeDecorator


class sUUID(TypeDecorator):
    """Platform-independent UUID type.
    If dialect is PostgreSQL, it uses the native UUID type.
    Otherwise, uses CHAR(36) to store UUIDs as strings.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(UUID())
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return str(uuid.UUID(value)).lower()
            else:
                return str(value).lower()

    def _uuid_value(self, value):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(value)
            return value

    def process_result_value(self, value, dialect):
        return self._uuid_value(value)

    def sort_key_function(self, value):
        return self._uuid_value(value)
