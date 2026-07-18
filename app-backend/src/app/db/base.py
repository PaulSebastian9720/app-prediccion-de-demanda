"""Base declarativa de SQLAlchemy compartida por todos los modelos."""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Convencion de nombres explicita para que Alembic genere nombres de
# constraints predecibles y estables entre migraciones autogeneradas.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Clase base declarativa para todos los modelos ORM."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
