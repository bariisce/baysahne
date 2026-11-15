import enum
import uuid

from sqlalchemy import Enum, Uuid
from sqlalchemy.orm import mapped_column


def str_enum(enum_cls: type[enum.Enum], name: str):
    """Portable string enum stored as VARCHAR with a CHECK constraint (easy to extend in migrations)."""
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )


def uuid_pk():
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
