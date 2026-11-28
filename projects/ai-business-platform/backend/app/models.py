"""Imports every ORM model module so Base.metadata is complete.

Alembic (autogenerate) and tests import this; add new model modules here.
"""

from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.users import models as users_models  # noqa: F401
