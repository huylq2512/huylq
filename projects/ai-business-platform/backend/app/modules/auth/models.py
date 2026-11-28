"""RBAC tables: roles, permissions and the role -> permission link."""

from sqlalchemy import Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

# Pure link table (no extra columns), so a Core Table is enough; no mapped class needed.
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "permission_id", Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True
    ),
)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    description: Mapped[str | None] = mapped_column(String(255))

    # selectin: loaded with one extra SELECT; implicit lazy loading cannot work in async.
    permissions: Mapped[list["Permission"]] = relationship(
        secondary=role_permissions, lazy="selectin", order_by="Permission.code"
    )


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True)  # "resource:action"
    description: Mapped[str | None] = mapped_column(String(255))
