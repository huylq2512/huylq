"""Permission codes and the default role -> permission matrix.

Code checks permissions (e.g. "customer:update"), never role names. Adding a new role or
changing what a role may do is then a data change, not a code change.

The matrix below is the baseline seed: `seed_rbac` inserts whatever is missing and never
deletes rows (extra permissions added at runtime survive; removed defaults are restored).
"""

from enum import StrEnum


class PermissionCode(StrEnum):
    USER_READ = "user:read"
    USER_MANAGE = "user:manage"  # create/disable users, assign roles
    ROLE_MANAGE = "role:manage"  # change what a role may do

    CUSTOMER_READ = "customer:read"
    CUSTOMER_CREATE = "customer:create"
    CUSTOMER_UPDATE = "customer:update"
    CUSTOMER_DELETE = "customer:delete"

    PRODUCT_READ = "product:read"
    PRODUCT_CREATE = "product:create"
    PRODUCT_UPDATE = "product:update"
    PRODUCT_DELETE = "product:delete"

    INVENTORY_READ = "inventory:read"
    INVENTORY_MOVE = "inventory:move"  # stock in / stock out
    INVENTORY_ADJUST = "inventory:adjust"

    ORDER_READ = "order:read"
    ORDER_CREATE = "order:create"
    ORDER_UPDATE = "order:update"
    ORDER_CONFIRM = "order:confirm"
    ORDER_CANCEL = "order:cancel"

    DOCUMENT_READ = "document:read"
    DOCUMENT_UPLOAD = "document:upload"
    DOCUMENT_DELETE = "document:delete"


P = PermissionCode

ROLE_ADMIN = "admin"
ROLE_MANAGER = "manager"
ROLE_SALES = "sales"
ROLE_WAREHOUSE = "warehouse"
ROLE_EMPLOYEE = "employee"

ROLE_DESCRIPTIONS: dict[str, str] = {
    ROLE_ADMIN: "Full access, including user and role management",
    ROLE_MANAGER: "Runs the business modules; cannot manage roles",
    ROLE_SALES: "Customers and sales orders",
    ROLE_WAREHOUSE: "Inventory movements and adjustments",
    ROLE_EMPLOYEE: "Read-only access to basic data and documents",
}

DEFAULT_ROLE_PERMISSIONS: dict[str, frozenset[PermissionCode]] = {
    ROLE_ADMIN: frozenset(PermissionCode),
    ROLE_MANAGER: frozenset(PermissionCode) - {P.USER_MANAGE, P.ROLE_MANAGE},
    ROLE_SALES: frozenset(
        {
            P.CUSTOMER_READ,
            P.CUSTOMER_CREATE,
            P.CUSTOMER_UPDATE,
            P.PRODUCT_READ,
            P.INVENTORY_READ,
            P.ORDER_READ,
            P.ORDER_CREATE,
            P.ORDER_UPDATE,
            P.ORDER_CONFIRM,
            P.DOCUMENT_READ,
        }
    ),
    ROLE_WAREHOUSE: frozenset(
        {
            P.PRODUCT_READ,
            P.INVENTORY_READ,
            P.INVENTORY_MOVE,
            P.INVENTORY_ADJUST,
            P.ORDER_READ,
            P.DOCUMENT_READ,
        }
    ),
    ROLE_EMPLOYEE: frozenset(
        {P.CUSTOMER_READ, P.PRODUCT_READ, P.DOCUMENT_READ}
    ),
}
