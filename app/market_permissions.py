"""Market authorization policy.

SEO/Marketing roles are deliberately Market-only and do not inherit Manager or
Administrator capabilities.  Keep this module independent from Scorer/Travel/Sports.
"""
from __future__ import annotations

MARKET_STAFF_ROLES = frozenset({
    "admin", "manager", "seo_viewer", "seo_editor", "seo_reviewer",
    "marketing_editor", "seo_admin",
})
SEO_MARKETING_ROLES = frozenset({
    "seo_viewer", "seo_editor", "seo_reviewer", "marketing_editor", "seo_admin",
})
PRIVILEGED_ACCOUNT_ROLES = frozenset({"admin", "manager", *SEO_MARKETING_ROLES})

ROLE_PERMISSIONS = {
    "admin": {"*"},
    "manager": {
        "market.catalog.manage", "market.orders.view", "market.offers.create",
        "market.support.manage", "market.users.view_customers",
    },
    "seo_viewer": {"seo.view", "seo.audit.view"},
    "seo_editor": {"seo.view", "seo.audit.view", "seo.draft.edit"},
    "seo_reviewer": {"seo.view", "seo.audit.view", "seo.review", "seo.publish"},
    "marketing_editor": {"seo.view", "seo.audit.view", "marketing.draft.edit"},
    "seo_admin": {
        "seo.view", "seo.audit.view", "seo.settings.manage",
    },
    "customer": set(),
}

def has_permission(role: str | None, permission: str) -> bool:
    permissions = ROLE_PERMISSIONS.get((role or "").lower(), set())
    return "*" in permissions or permission in permissions


def role_privileges():
    return {
        "admin": {"label": "Administrator", "privileges": ["Full Market administration", "Manage users and roles", "All SEO/Marketing permissions"]},
        "manager": {"label": "Manager / Staff (Power-user)", "privileges": ["Operational Market management", "No SEO/Marketing administration by inheritance"]},
        "seo_viewer": {"label": "SEO Viewer", "privileges": ["View SEO data and audit history", "No edit, publish, user, order, payment or catalog administration"]},
        "seo_editor": {"label": "SEO Editor", "privileges": ["View SEO data", "Create/edit SEO drafts", "Cannot publish or administer Market"]},
        "seo_reviewer": {"label": "SEO Reviewer", "privileges": ["Review SEO drafts", "Publish approved SEO changes", "Cannot administer users, payments, orders or catalog"]},
        "marketing_editor": {"label": "Marketing Campaign Editor", "privileges": ["View SEO context", "Create/edit marketing drafts", "No SEO publish or Market administration"]},
        "seo_admin": {"label": "Technical SEO Administrator", "privileges": ["SEO settings, review and publishing", "No Market administrator/manager privileges"]},
        "customer": {"label": "Customer", "privileges": ["Storefront/customer account only", "No administration access"]},
    }
