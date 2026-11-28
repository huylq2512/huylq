import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, String, Table, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin
from app.modules.auth.models import Role

# role_id is RESTRICT: deleting a role that is still assigned must fail loudly rather than
# silently strip users of access. Deleting a user removes their assignments (CASCADE).
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="RESTRICT"), primary_key=True),
    # PK (user_id, role_id) serves "roles of a user"; this serves "users of a role".
    Index("ix_user_roles_role_id", "role_id"),
)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("email <> ''", name="email_not_empty"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    roles: Mapped[list[Role]] = relationship(
        secondary=user_roles, lazy="selectin", order_by="Role.name"
    )

    @property
    def permission_codes(self) -> frozenset[str]:
        """Union of the permissions of all the user's roles (loaded eagerly via selectin)."""
        return frozenset(p.code for role in self.roles for p in role.permissions)


# Case-insensitive uniqueness: "A@x.com" and "a@x.com" are the same account.
# Declared after the class because the expression needs the mapped column.
Index("uq_users_email_lower", func.lower(User.email), unique=True)
