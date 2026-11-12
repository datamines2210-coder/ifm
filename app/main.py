import base64, json, logging, time, uuid, io, csv, hashlib, hmac, secrets, smtplib, threading, urllib.request, shutil, html, re, re
from collections import Counter
from pathlib import Path
from urllib.parse import quote
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field, EmailStr, HttpUrl, field_validator
from .config import settings
from .logging_config import configure_logging, request_context
from .models import PRODUCTS, Product
from .services import PaymentService, AlertService
from .payments.cashfree import CashfreeGateway
from .logistics.dispatch import DispatchService
from .auth import hash_password, verify_password, create_token, decode_token, touch_session, revoke_session
from .market_permissions import MARKET_STAFF_ROLES, SEO_MARKETING_ROLES, PRIVILEGED_ACCOUNT_ROLES, ROLE_PERMISSIONS, has_permission, role_privileges
from .seo_repository import (list_documents as list_seo_documents, get_document as get_seo_document, list_revisions as list_seo_revisions, create_draft as create_seo_draft, submit_review as submit_seo_review, approve_revision as approve_seo_revision, publish_revision as publish_seo_revision, rollback_to_revision as rollback_seo_revision, list_audit as list_seo_audit)
from .seo_delivery import published as public_seo, head_tags as seo_head_tags, page_html as seo_page_html, product_path as seo_product_path, category_path as seo_category_path, slugify as seo_slugify, base_url as seo_base_url

# Extended services are mounted opportunistically below. They own their own
# databases and identity/session stores; a failure in one must not prevent the
# Market application from starting.
from .db import (init_db, find_user_by_email, find_user_by_login, find_user, create_user, create_order, get_order,
                 get_order_by_gateway_reference, set_order_status, add_payment, list_catalog, catalog_product, save_catalog_product,
                 delete_catalog_product, list_users, update_user_password, update_user_role,
                 get_payment_settings, save_payment_settings, list_site_content, save_site_content,
                 get_admin_password_hash, save_admin_password, get_admin_profile, update_admin_profile,
                 list_orders_for_user, list_orders, get_payment_for_order, create_feedback, list_feedback_for_user,
                 list_feedback, update_feedback_status, log_auth_event, list_auth_logs, get_delivery,
                 list_archived_auth_logs, delete_auth_logs_by_filter, run_auth_log_retention_maintenance,
                 get_customer_profile, update_customer_profile, update_user_details, list_auth_sessions, admin_revoke_auth_session, delete_user_admin, list_offers, save_offer, delete_offer, create_login_otp, consume_login_otp, find_accounts_by_phone, list_category_media, save_category_media, list_category_settings, save_category_settings, rename_category, delete_category_settings, category_diagnostics, update_category_by_id, save_category_image_by_id, delete_category_by_id, merge_category_by_id, import_catalog_atomic, force_delete_categories, get_catalog_template_config, save_catalog_template_config, archive_catalog_products, catalog_products_referenced_by_orders, hard_delete_catalog_products, set_order_gateway_reference, create_payment_transaction, update_payment_transaction, get_payment_transaction_by_provider_order, list_payment_transactions)

configure_logging(settings.log_level)
log = logging.getLogger("app")
BASE = Path(__file__).resolve().parent.parent
payment = PaymentService()
cashfree = CashfreeGateway()
dispatch = DispatchService()
alerts = AlertService()
metrics = Counter()

def row_product(row):
    values = dict(row)
    return Product(**{key: values[key] for key in Product.__dataclass_fields__})

def branded_page(filename: str) -> HTMLResponse:
    # Lets the storefront brand be swapped (merger/acquisition) via config, not code edits.
    html = (BASE / "static" / filename).read_text(encoding="utf-8")
    return HTMLResponse(html.replace("{{BRAND_NAME}}", settings.app_name))

app = FastAPI(title=settings.app_name, version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET","POST","PUT","DELETE"], allow_headers=["*"])
app.middleware("http")(request_context)


def _mount_extended_service(name: str) -> bool:
    """Mount one optional service without making Market startup depend on it."""
    try:
        if name == "scorer":
            from .scorer.router import router
        elif name == "travel":
            from .travel.database import init_db as service_init_db
            from .travel.router import router
            service_init_db()
        elif name == "sports":
            from .sports.database import init_db as service_init_db
            from .sports.router import router
            service_init_db()
        else:
            raise ValueError(f"Unknown extended service: {name}")
        app.include_router(router)
        log.info("extended_service_mounted service=%s", name)
        return True
    except Exception:
        # Isolation boundary: Market remains healthy even when an optional
        # service cannot import, initialize its own DB, or mount its router.
        log.exception("extended_service_degraded service=%s", name)
        return False


# Spinout: Market no longer imports, initializes, or mounts Community services.
# Set MARKET_EXTENDED_MODE=legacy only for a controlled emergency rollback.
import os as _spinout_os
from fastapi.responses import RedirectResponse as _SpinoutRedirect
_MARKET_EXTENDED_MODE = _spinout_os.getenv("MARKET_EXTENDED_MODE", "redirect").strip().lower()
if _MARKET_EXTENDED_MODE not in ("legacy", "redirect"):
    raise RuntimeError("MARKET_EXTENDED_MODE must be legacy or redirect")
_COMMUNITY_BASE_URL = _spinout_os.getenv("COMMUNITY_BASE_URL", "http://localhost:8030").rstrip("/")
if not (_COMMUNITY_BASE_URL.startswith("http://") or _COMMUNITY_BASE_URL.startswith("https://")):
    raise RuntimeError("COMMUNITY_BASE_URL must be an absolute HTTP(S) URL")
EXTENDED_SERVICE_STATUS = (
    {name: _mount_extended_service(name) for name in ("travel", "sports", "scorer")}
    if _MARKET_EXTENDED_MODE == "legacy" else {}
)

init_db()
# Run retention maintenance at startup as well as on auth events, so an idle deployment
# still archives after 1 year and purges only after the full 4-year retention window.
if not settings.database_url.startswith(('mysql+pymysql://', 'mariadb+pymysql://')):
    run_auth_log_retention_maintenance(force=True)
else:
    # Do not run write-capable startup maintenance on the migration candidate.
    pass

class Signup(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    username: str = Field(min_length=3, max_length=80)
    email: EmailStr
    phone: str = Field(min_length=10, max_length=10, pattern=r'^\d{10}$')
    password: str = Field(min_length=8, max_length=128)

class Login(BaseModel):
    email: str = Field(min_length=1, max_length=200)
    password: str = Field(max_length=128)

class CheckoutItem(BaseModel):
    product_id: str
    quantity: int = Field(ge=1, le=99)
class Checkout(BaseModel):
    customer_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    phone: str = Field(min_length=8, max_length=20)
    pincode: str = Field(min_length=6, max_length=6)
    address: str = Field(min_length=5, max_length=500)
    delivery_date: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    delivery_slot: str = Field(pattern=r'^(09:00-10:00|10:00-11:00|11:00-12:00|12:00-13:00|13:00-14:00|14:00-15:00|15:00-16:00|16:00-17:00|17:00-18:00|18:00-19:00|19:00-20:00)$')
    items: list[CheckoutItem] = Field(min_length=1)
    user_id: str | None = None
    # Customer gateway pick from the secure-checkout prompt. Cashfree is primary; Razorpay is backup.
    payment_method: str | None = Field(default=None, pattern='^(cashfree|razorpay)$')
    coupon_code: str = Field(default="", max_length=80)

class PaymentTestRequest(BaseModel):
    confirm_live: bool = False

class PaymentVerify(BaseModel):
    order_id: str
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

class AUBankWebhook(BaseModel):
    reference_id: str
    payment_id: str
    status: str = Field(pattern='^(paid|failed)$')

class PasswordChange(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class AdminPasswordReset(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)

class BankDetailsUpdate(BaseModel):
    bank_name: str = Field(min_length=2, max_length=120)
    bank_account_masked: str = Field(min_length=4, max_length=40)
    ifsc: str = Field(min_length=4, max_length=20)

class OtpRequest(BaseModel):
    identity: str = Field(min_length=1, max_length=200)
    password: str = Field(default="", max_length=128)
    password: str = Field(default="", max_length=128)

class OtpVerify(BaseModel):
    identity: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=6, max_length=6, pattern=r'^\d{6}$')

class PaymentSettings(BaseModel):
    provider: str = Field(pattern='^(razorpay|upi|cashfree)$')
    razorpay_checkout_url: str = Field(default='https://pages.razorpay.com/tifa', max_length=1000)
    upi_id: str = Field(default='', max_length=200)
    upi_name: str = Field(default='', max_length=120)
    upi_redirect_url: str = Field(default='', max_length=1000)

class FeedbackIn(BaseModel):
    order_id: str = Field(default='', max_length=80)
    subject: str = Field(min_length=2, max_length=160)
    message: str = Field(default='', max_length=2000)
    rating: int | None = Field(default=None, ge=1, le=5)

class FeedbackStatusUpdate(BaseModel):
    status: str = Field(pattern='^(new|reviewed|resolved)$')
    response: str = Field(default='', max_length=2000)

class OrderStatusUpdate(BaseModel):
    status: str = Field(pattern='^(created|paid|payment_verification_failed|cancelled|refunded)$')

class DeliveryStatusUpdate(BaseModel):
    status: str = Field(pattern='^(pending|assigned|packed|dispatched|in_transit|out_for_delivery|delivered|delivery_failed|returned)$')
    tracking_number: str | None = Field(default=None, max_length=120)

class AuthLogCleanupFilter(BaseModel):
    mode: str = Field(pattern='^(custom|weekly|monthly|yearly)$')
    start_at: int | None = None
    end_at: int | None = None
    target: str = Field(default='archive', pattern='^(live|archive|both)$')

class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    username: str = Field(min_length=3, max_length=80)
    email: EmailStr
    phone: str = Field(min_length=10, max_length=10, pattern=r'^\d{10}$')
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(default='customer', pattern='^(customer|manager|admin|seo_viewer|seo_editor|seo_reviewer|marketing_editor|seo_admin)$')

class UserRoleUpdate(BaseModel):
    role: str = Field(pattern='^(customer|manager|admin|seo_viewer|seo_editor|seo_reviewer|marketing_editor|seo_admin)$')

class BulkUserDelete(BaseModel):
    user_ids: list[str] = Field(min_length=1, max_length=500)
    stale_days: int = Field(default=90, ge=1, le=3650)
    include_never_used: bool = True
    deletion_mode: str = Field(default='stale', pattern='^(stale|manual)$')

class BuiltinAdminUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    username: str = Field(min_length=3, max_length=80)
    email: EmailStr
    phone: str = Field(min_length=10, max_length=10, pattern=r'^\d{10}$')

class AccountDetailsUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    username: str = Field(default='', max_length=80)
    phone: str = Field(default='', max_length=20)

class AddressUpdate(BaseModel):
    address_line1: str = Field(default='', max_length=200)
    address_line2: str = Field(default='', max_length=200)
    city: str = Field(default='', max_length=100)
    state: str = Field(default='', max_length=100)
    pincode: str = Field(default='', max_length=12)
    locality: str = Field(default='', max_length=160)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

class AdminCustomerProfileUpdate(AccountDetailsUpdate, AddressUpdate):
    bank_name: str = Field(default='', max_length=120)
    bank_account_masked: str = Field(default='', max_length=40)
    ifsc: str = Field(default='', max_length=20)

class SiteContent(BaseModel):
    key: str = Field(min_length=2, max_length=100)
    value: str = Field(default='', max_length=2000)
    image: str = Field(default='', max_length=1000)
    link: str = Field(default='', max_length=1000)
    active: bool = True

class ImageUpload(BaseModel):
    data_url: str = Field(min_length=30, max_length=8_000_000)
    filename: str = Field(default='product-image', max_length=120)

class AdminLogin(BaseModel):
    email: str = Field(min_length=1, max_length=200)
    password: str = Field(max_length=128)

class CatalogItem(BaseModel):
    id: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=2, max_length=160)
    category: str = Field(min_length=2, max_length=80)
    state: str = Field(min_length=2, max_length=80)
    price: float = Field(ge=0)
    mrp: float = Field(ge=0)
    unit: str = Field(min_length=1, max_length=40)
    description: str = Field(max_length=1000)
    image: str = Field(default="", max_length=1000)
    parent_url: str = Field(default="", max_length=1000)
    active: bool = True
    status: str = Field(default='live', pattern='^(live|coming_soon|archived)$')

class BulkCatalogUpload(BaseModel):
    data_url: str = Field(min_length=30, max_length=20_000_000)
    filename: str = Field(max_length=200)
    validate_only: bool = False
    mode: str = Field(default='update', pattern='^(update|authoritative)$')

class BulkCatalogAction(BaseModel):
    product_ids: list[str] = Field(min_length=1, max_length=500)

class TemplateConfig(BaseModel):
    fields: list[str]

class CategorySettings(BaseModel):
    display_name: str = Field(min_length=2,max_length=80)
    description: str = Field(default='',max_length=500)
    active: bool = True
    sort_order: int = Field(default=100,ge=0,le=9999)
    new_category: str = Field(default='',max_length=80)


class SeoRevisionInput(BaseModel):
    resource_type: str = Field(pattern='^(site|page|product|category)$')
    resource_key: str = Field(min_length=1, max_length=500)
    title: str = Field(default='', max_length=200)
    meta_description: str = Field(default='', max_length=500)
    canonical_url: str = Field(default='', max_length=1000)
    robots: str = Field(default='index,follow', pattern='^(index|noindex),(follow|nofollow)$')
    og_title: str = Field(default='', max_length=200)
    og_description: str = Field(default='', max_length=500)
    og_image: str = Field(default='', max_length=1000)
    structured_data_json: str = Field(default='', max_length=50000)
    notes: str = Field(default='', max_length=2000)

class SeoRollbackInput(BaseModel):
    target_revision_id: str = Field(min_length=5, max_length=80)

class OfferItem(BaseModel):
    id: str = Field(min_length=2,max_length=80)
    title: str = Field(min_length=2,max_length=180)
    slogan: str = Field(default='',max_length=300)
    description: str = Field(default='',max_length=2000)
    offer_type: str = Field(default='informational',pattern='^(informational|percentage|fixed)$')
    value: float = Field(default=0,ge=0)
    code: str = Field(default='',max_length=80)
    scope: str = Field(default='site',pattern='^(site|category|product)$')
    target: str = Field(default='',max_length=160)
    image: str = Field(default='',max_length=1000)
    cta_text: str = Field(default='',max_length=100)
    cta_link: str = Field(default='',max_length=1000)
    placement: str = Field(default='offers',pattern='^(hero|offers|catalog)$')
    status: str = Field(default='draft',pattern='^(draft|active|scheduled|paused)$')
    priority: int = Field(default=100,ge=0,le=9999)
    start_at: int | None = None
    end_at: int | None = None

@app.get("/api/health")
def health():
    return {"status":"ok","service":settings.app_name,"environment":settings.environment}

@app.get("/api/ready")
def ready():
    return {"status":"ready","catalog_count":len(list_catalog())}

@app.get("/metrics")
def metrics_endpoint():
    return "\n".join(f'app_requests_total{{route="{k}"}} {v}' for k,v in metrics.items()) + "\n"

@app.get("/api/catalog")
def catalog(q: str = "", category: str = "", state: str = ""):
    metrics["catalog"] += 1
    ql = q.lower().strip()
    items = [row_product(p) for p in list_catalog()]
    if ql:
        items = [p for p in items if ql in (p.name + " " + p.description + " " + p.state + " " + p.category + " " + p.unit).lower()]
    if category:
        items = [p for p in items if p.category.lower() == category.lower()]
    if state:
        items = [p for p in items if p.state.lower() == state.lower()]
    all_items = [row_product(p) for p in list_catalog()]
    settings_rows={r["category"]:dict(r) for r in list_category_settings()}
    categories=sorted({p.category for p in all_items if settings_rows.get(p.category,{}).get("active",1)}, key=lambda c:(settings_rows.get(c,{}).get("sort_order",100),c.lower()))
    return {"items":[p.__dict__ for p in items], "categories":categories, "states":sorted({p.state for p in all_items}), "category_media":{c:settings_rows.get(c,{}).get("image","") for c in categories}, "category_details":{c:{"display_name":settings_rows.get(c,{}).get("display_name") or c,"description":settings_rows.get(c,{}).get("description") or ''} for c in categories}}

def admin_required(request: Request):
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(401, "Administrator login required")
    data = decode_token(header[7:])
    if not data or data.get("role") not in {"admin", "manager"}:
        raise HTTPException(403, "Administrator access required")
    if not touch_session(data, request.client.host if request.client else "", request.headers.get("user-agent", "")[:500]):
        raise HTTPException(401, "Session expired after 4 hours of inactivity. Please sign in again.")
    return data

def administrator_only(request: Request):
    user=admin_required(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "Administrator access required")
    return user


def market_permission_required(permission: str):
    """Server-side permission dependency for Phase 1 and later SEO endpoints."""
    def dependency(request: Request):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise HTTPException(401, "Market staff login required")
        data = decode_token(header[7:])
        if not data:
            raise HTTPException(401, "Invalid or expired session")
        if not touch_session(data, request.client.host if request.client else "", request.headers.get("user-agent", "")[:500]):
            raise HTTPException(401, "Session expired after 4 hours of inactivity. Please sign in again.")
        if not has_permission(data.get("role"), permission):
            log_auth_event(f"log_{uuid.uuid4().hex[:16]}", int(time.time()), "authorization_denied", False, data.get("sub", ""), data.get("email", ""), request.client.host if request.client else "", request.headers.get("user-agent", "")[:500], f"permission={permission};role={data.get('role','')}")
            raise HTTPException(403, "Permission denied")
        return data
    return dependency

ROLE_PRIVILEGES = role_privileges()

@app.get("/api/admin/roles", tags=["Admin"])
def admin_roles(_: dict = Depends(administrator_only)):
    return {"items":[{"role":key, **value} for key,value in ROLE_PRIVILEGES.items()]}


@app.get("/api/admin/seo/access", tags=["SEO Security"])
def seo_access(user: dict = Depends(market_permission_required("seo.view"))):
    """Phase-1 authorization probe; no SEO content or configuration is exposed."""
    return {"status":"authorized","role":user.get("role"),"permissions":sorted(ROLE_PERMISSIONS.get(user.get("role"), set())) if user.get("role") != "admin" else ["*"]}

def _seo_transition(call, *args):
    try:
        return call(*args)
    except KeyError as exc:
        raise HTTPException(404, str(exc).strip("'"))
    except (ValueError, __import__('json').JSONDecodeError) as exc:
        raise HTTPException(409, str(exc))

@app.get("/api/admin/seo/integrations/status", tags=["SEO Measurement"])
def seo_integration_status(_: dict = Depends(market_permission_required("seo.view"))):
    from .seo_measurement import status
    return {"items": status()}

@app.get("/api/admin/seo/integrations/{provider}/snapshots", tags=["SEO Measurement"])
def seo_integration_snapshots(provider: str, limit: int = 30, _: dict = Depends(market_permission_required("seo.view"))):
    from .seo_measurement import snapshots
    try: return {"items": snapshots(provider, limit)}
    except ValueError as exc: raise HTTPException(400, str(exc))

@app.post("/api/admin/seo/integrations/{provider}/refresh", tags=["SEO Measurement"])
def seo_integration_refresh(provider: str, user: dict = Depends(market_permission_required("seo.settings.manage"))):
    from .seo_measurement import refresh
    try: return refresh(provider, user.get("sub", ""))
    except ValueError as exc: raise HTTPException(409, str(exc))

@app.get("/api/admin/seo/health/scan", tags=["SEO Diagnostics"])
def seo_health_scan(_: dict = Depends(market_permission_required("seo.view"))):
    """Bounded read-only inspection of server-rendered Market pages; no network requests."""
    from .seo_health import inspect_pages
    from urllib.parse import urlparse
    from xml.etree import ElementTree as ET
    pages=[]
    def capture(path, render):
        try:
            response=render()
            pages.append((path, response.status_code, response.body.decode("utf-8", "replace")))
        except HTTPException as exc:
            pages.append((path,exc.status_code,""))
    capture("/",index)
    products=[row_product(r) for r in list_catalog()]
    for product in products[:18]:
        path=seo_product_path(product.id)
        capture(path,lambda pid=product.id: seo_product_page(pid))
    for category in sorted({p.category for p in products})[:11]:
        path=seo_category_path(category)
        capture(path,lambda slug=seo_slugify(category):seo_category_page(slug))
    sitemap=ET.fromstring(sitemap_xml().body)
    urls={urlparse(el.text or "").path for el in sitemap.iter() if el.tag.endswith("}loc")}
    return inspect_pages(pages,seo_base_url(),urls)

@app.get("/api/admin/seo/documents", tags=["SEO Publishing"])
def seo_documents(resource_type: str = "", resource_key: str = "", _: dict = Depends(market_permission_required("seo.view"))):
    return {"items": list_seo_documents(resource_type, resource_key)}

@app.get("/api/admin/seo/documents/{document_id}", tags=["SEO Publishing"])
def seo_document(document_id: str, _: dict = Depends(market_permission_required("seo.view"))):
    document=get_seo_document(document_id)
    if not document: raise HTTPException(404, "SEO document not found")
    return {"document":document,"revisions":list_seo_revisions(document_id)}

@app.post("/api/admin/seo/drafts", tags=["SEO Publishing"])
def seo_create_draft(data: SeoRevisionInput, user: dict = Depends(market_permission_required("seo.draft.edit"))):
    payload=data.model_dump(); resource_type=payload.pop("resource_type"); resource_key=payload.pop("resource_key")
    try:
        revision=create_seo_draft(resource_type,resource_key,payload,user.get("sub", ""),user.get("role", ""))
    except (ValueError, __import__('json').JSONDecodeError) as exc:
        raise HTTPException(400, str(exc))
    return {"status":"draft_created","revision":revision}

@app.post("/api/admin/seo/revisions/{revision_id}/submit", tags=["SEO Publishing"])
def seo_submit(revision_id: str, user: dict = Depends(market_permission_required("seo.draft.edit"))):
    return {"status":"in_review","revision":_seo_transition(submit_seo_review,revision_id,user.get("sub", ""),user.get("role", ""))}

@app.post("/api/admin/seo/revisions/{revision_id}/approve", tags=["SEO Publishing"])
def seo_approve(revision_id: str, user: dict = Depends(market_permission_required("seo.review"))):
    return {"status":"approved","revision":_seo_transition(approve_seo_revision,revision_id,user.get("sub", ""),user.get("role", ""))}

@app.post("/api/admin/seo/revisions/{revision_id}/publish", tags=["SEO Publishing"])
def seo_publish(revision_id: str, user: dict = Depends(market_permission_required("seo.publish"))):
    return {"status":"published","revision":_seo_transition(publish_seo_revision,revision_id,user.get("sub", ""),user.get("role", ""))}

@app.post("/api/admin/seo/documents/{document_id}/rollback", tags=["SEO Publishing"])
def seo_rollback(document_id: str, data: SeoRollbackInput, user: dict = Depends(market_permission_required("seo.publish"))):
    return {"status":"rollback_draft_created","revision":_seo_transition(rollback_seo_revision,document_id,data.target_revision_id,user.get("sub", ""),user.get("role", ""))}

@app.get("/api/admin/seo/audit", tags=["SEO Publishing"])
def seo_audit(document_id: str = "", limit: int = 200, _: dict = Depends(market_permission_required("seo.audit.view"))):
    return {"items":list_seo_audit(document_id,limit)}

@app.post("/api/admin/login", tags=["Admin"])
def admin_login(data: AdminLogin, request: Request):
    ip = request.client.host if request.client else ""
    ua = request.headers.get("user-agent", "")[:500]
    if data.email.lower() in {settings.admin_email.lower(), settings.admin_username.lower()} and verify_password(data.password, get_admin_password_hash()):
        log_auth_event(f"log_{uuid.uuid4().hex[:16]}", int(time.time()), "admin_login_success", True, "admin", data.email, ip, ua, "administrator login")
        return {"token": create_token("admin", data.email, role="admin"), "admin": {"email": data.email, "role": "admin"}}
    user = find_user_by_login(data.email)
    if not user or user['role'] not in MARKET_STAFF_ROLES or not verify_password(data.password, user['password_hash']):
        log_auth_event(f"log_{uuid.uuid4().hex[:16]}", int(time.time()), "admin_login_failed", False, "", data.email, ip, ua, "invalid administrator credentials")
        raise HTTPException(401, "Invalid administrator credentials")
    log_auth_event(f"log_{uuid.uuid4().hex[:16]}", int(time.time()), "admin_login_success", True, user['id'], data.email, ip, ua, f"role={user['role']}")
    return {"token": create_token(user['id'], user['email'], role=user['role']), "admin": {"email": user['email'], "role": user['role']}}

@app.get("/api/public-config")
def public_config():
    number=''.join(ch for ch in settings.whatsapp_number if ch.isdigit())
    message=(settings.whatsapp_message or '').strip()
    if not number:
        return {"whatsapp_url": ""}
    url=f"https://wa.me/{number}"
    if message:
        url += f"?text={quote(message, safe='')}"
    return {"whatsapp_url": url}

@app.get("/api/site-content")
def site_content():
    return {row['key']: dict(row) for row in list_site_content()}

@app.get("/api/admin/payment-settings", tags=["Admin"])
def admin_payment_settings(_: dict = Depends(administrator_only)):
    return dict(get_payment_settings())

@app.put("/api/admin/payment-settings", tags=["Admin"])
def admin_save_payment_settings(data: PaymentSettings, _: dict = Depends(administrator_only)):
    if data.provider == 'upi' and not data.upi_id and not data.upi_redirect_url:
        raise HTTPException(400, 'Add a UPI ID or redirect URL before selecting UPI')
    save_payment_settings(data.model_dump())
    return {"status": "updated", "settings": dict(get_payment_settings())}

@app.get("/api/admin/users", tags=["Admin"])
def admin_users(admin: dict = Depends(admin_required)):
    # Managers receive a strictly read-only, customer-only projection. Administrator,
    # manager/staff and test/system identities are never returned to a manager.
    if admin.get("role") == "manager":
        items=[]
        for row in list_users():
            x=dict(row); identity=' '.join(str(x.get(k) or '') for k in ('name','username','email')).lower()
            is_test=(x.get('email') or '').lower().endswith('@example.com') or any(t in identity for t in ('test buyer','testbuyer','duplicate-auth','cashfree.'))
            if x.get('role') == 'customer' and not is_test:
                x['account_category']='customer'; x['builtin']=False; items.append(x)
        return {"items":items,"read_only":True,"scope":"customers"}
    items=[]
    ap=get_admin_profile()
    items.append({"id":"admin","name":ap["name"],"email":ap["email"],"username":ap["username"],"phone":ap["phone"],"role":"admin","must_change_password":False,"created_at":0,"account_category":"administrator","builtin":True})
    for row in list_users():
        x=dict(row); identity=' '.join(str(x.get(k) or '') for k in ('name','username','email')).lower()
        is_test=(x.get('email') or '').lower().endswith('@example.com') or any(t in identity for t in ('test buyer','testbuyer','duplicate-auth','cashfree.'))
        x['account_category']='test_system' if is_test else ('administrator' if x.get('role')=='admin' else ('staff' if x.get('role')=='manager' else ('seo_marketing' if x.get('role') in SEO_MARKETING_ROLES else 'customer')))
        x['builtin']=False; items.append(x)
    return {"items":items}

@app.put("/api/admin/builtin-profile", tags=["Admin"])
def admin_update_builtin_profile(data: BuiltinAdminUpdate, admin: dict = Depends(administrator_only)):
    if admin.get('sub') != 'admin': raise HTTPException(403,'Only the built-in administrator can change the primary administrator record')
    other=find_user_by_login(data.username)
    if other: raise HTTPException(409,'Username is already used by another account')
    other=find_user_by_email(data.email)
    if other: raise HTTPException(409,'Email is already used by another account')
    return {"status":"updated","admin":update_admin_profile(data.name,data.email,data.username,data.phone)}

@app.put("/api/admin/users/{user_id}", tags=["Admin"])
def admin_update_user(user_id: str, data: AdminCustomerProfileUpdate, _: dict = Depends(administrator_only)):
    if user_id == 'admin': raise HTTPException(400,'Use the administrator profile editor for the built-in administrator')
    if not find_user(user_id): raise HTTPException(404,"User not found")
    update_user_details(user_id,data.name,data.email,data.username,data.phone)
    update_customer_profile(user_id,data.model_dump(),admin=True)
    return {"status":"updated","user":dict(find_user(user_id)),"profile":dict(get_customer_profile(user_id))}

@app.delete("/api/admin/users/{user_id}", tags=["Admin"])
def admin_delete_user(user_id: str, _: dict = Depends(administrator_only)):
    if user_id == 'admin': raise HTTPException(409,'The built-in administrator cannot be deleted')
    if not find_user(user_id): raise HTTPException(404,"User not found")
    if not delete_user_admin(user_id): raise HTTPException(409,"Customer has order history and cannot be hard-deleted. Keep the record for audit integrity.")
    return {"status":"deleted","id":user_id}

@app.post("/api/admin/users/bulk-delete", tags=["Admin"])
def admin_bulk_delete_users(data: BulkUserDelete, _: dict = Depends(administrator_only)):
    """Delete only explicitly selected, stale, non-privileged accounts with no orders."""
    now=int(time.time()); cutoff=now-(data.stale_days*86400)
    rows={dict(r)['id']:dict(r) for r in list_users()}
    deleted=[]; skipped=[]
    for user_id in dict.fromkeys(data.user_ids):
        row=rows.get(user_id)
        if not row:
            skipped.append({"id":user_id,"reason":"not_found"}); continue
        if row.get('role') in PRIVILEGED_ACCOUNT_ROLES:
            skipped.append({"id":user_id,"reason":"privileged_account"}); continue
        if int(row.get('order_count') or 0)>0:
            skipped.append({"id":user_id,"reason":"has_order_history"}); continue
        last=row.get('last_activity_at')
        effective=int(last or row.get('created_at') or now)
        if data.deletion_mode == 'stale':
            if last is None and not data.include_never_used:
                skipped.append({"id":user_id,"reason":"never_used_excluded"}); continue
            if effective>cutoff:
                skipped.append({"id":user_id,"reason":"not_stale"}); continue
        if delete_user_admin(user_id): deleted.append(user_id)
        else: skipped.append({"id":user_id,"reason":"protected"})
    return {"status":"completed","deleted":deleted,"skipped":skipped,"deleted_count":len(deleted),"skipped_count":len(skipped)}

@app.post("/api/admin/users", tags=["Admin"])
def admin_create_user(data: UserCreate, _: dict = Depends(administrator_only)):
    if find_user_by_email(data.email):
        raise HTTPException(409, 'An account with this email already exists')
    if find_user_by_login(data.username):
        raise HTTPException(409, 'This username is already in use')
    user_id = f"usr_{uuid.uuid4().hex[:16]}"
    create_user(user_id, data.name, data.email, data.phone, hash_password(data.password), int(time.time()), data.role, username=data.username)
    return {"status": "created", "id": user_id}

@app.post("/api/admin/users/{user_id}/password", tags=["Admin"])
def admin_reset_customer_password(user_id: str, data: AdminPasswordReset, _: dict = Depends(administrator_only)):
    if user_id == 'admin':
        save_admin_password(hash_password(data.new_password)); return {"status":"password_updated","id":"admin"}
    if not find_user(user_id): raise HTTPException(404,"User not found")
    update_user_password(user_id, hash_password(data.new_password))
    return {"status":"password_updated","id":user_id}

@app.put("/api/admin/users/{user_id}/role", tags=["Admin"])
def admin_update_role(user_id: str, data: UserRoleUpdate, _: dict = Depends(administrator_only)):
    if user_id == 'admin': raise HTTPException(409,'The built-in administrator role cannot be changed')
    if not find_user(user_id):
        raise HTTPException(404, 'User not found')
    update_user_role(user_id, data.role)
    return {"status": "updated", "id": user_id, "role": data.role}

@app.get("/api/admin/content", tags=["Admin"])
def admin_content(_: dict = Depends(administrator_only)):
    return {"items": [dict(row) for row in list_site_content(include_inactive=True)]}

@app.put("/api/admin/content/{key}", tags=["Admin"])
def admin_save_content(key: str, data: SiteContent, _: dict = Depends(administrator_only)):
    if key != data.key:
        raise HTTPException(400, 'Content key mismatch')
    save_site_content(data.model_dump())
    return {"status": "updated", "key": key}

# Catalog layout: isolated configuration, no schema migration.
CATALOG_LAYOUT_THEMES = frozenset(('modern', 'premium', 'compact', 'horizontal', 'horizontal-modern'))

class CatalogLayoutThemeRequest(BaseModel):
    theme: str


def _published_catalog_layout_theme():
    from .db import connect
    with connect() as conn:
        row = conn.execute("SELECT value FROM site_content WHERE `key`=?", ('catalog_layout_theme',)).fetchone()
    theme = str(row['value'] if row else 'modern').strip().lower()
    return theme if theme in CATALOG_LAYOUT_THEMES else 'modern'


@app.get('/api/admin/catalog/layout-theme', tags=['Admin'])
def admin_catalog_layout_theme(_: dict = Depends(admin_required)):
    return {'theme': _published_catalog_layout_theme()}


@app.put('/api/admin/catalog/layout-theme', tags=['Admin'])
def admin_publish_catalog_layout_theme(data: CatalogLayoutThemeRequest, _: dict = Depends(administrator_only)):
    theme = data.theme.strip().lower()
    if theme not in CATALOG_LAYOUT_THEMES:
        raise HTTPException(422, 'Invalid catalog theme')
    from .db import connect
    with connect() as conn:
        # UPDATE first avoids relying on SQLite-only ON CONFLICT translation.
        existing = conn.execute("SELECT value FROM site_content WHERE `key`=?", ('catalog_layout_theme',)).fetchone()
        if existing is not None:
            conn.execute("UPDATE site_content SET value=?,active=?,updated_at=? WHERE `key`=?", (theme, 1, int(time.time()), 'catalog_layout_theme'))
        else:
            conn.execute("INSERT INTO site_content(`key`,value,image,link,active,updated_at) VALUES(?,?,?,?,?,?)", ('catalog_layout_theme', theme, '', '', 1, int(time.time())))
    return {'theme': theme, 'status': 'published'}


# Website palette is independent of the catalog layout. Reuse site_content; no DDL.
WEBSITE_COLOR_THEMES = frozenset(('color1', 'color2'))

class WebsiteColorThemeRequest(BaseModel):
    theme: str


def _published_website_color_theme():
    from .db import connect
    with connect() as conn:
        row = conn.execute("SELECT value FROM site_content WHERE `key`=?", ('website_color_theme',)).fetchone()
    value = str(row['value'] if row else 'color1').strip().lower()
    return value if value in WEBSITE_COLOR_THEMES else 'color1'


@app.get('/api/admin/themes/website-color', tags=['Admin'])
def admin_get_website_color_theme(_: dict = Depends(admin_required)):
    return {'theme': _published_website_color_theme()}


@app.put('/api/admin/themes/website-color', tags=['Admin'])
def admin_put_website_color_theme(data: WebsiteColorThemeRequest, _: dict = Depends(administrator_only)):
    theme = data.theme.strip().lower()
    if theme not in WEBSITE_COLOR_THEMES:
        raise HTTPException(422, 'Invalid website color theme')
    from .db import connect
    with connect() as conn:
        row = conn.execute("SELECT value FROM site_content WHERE `key`=?", ('website_color_theme',)).fetchone()
        if row is not None:
            conn.execute("UPDATE site_content SET value=?,active=?,updated_at=? WHERE `key`=?", (theme, 1, int(time.time()), 'website_color_theme'))
        else:
            conn.execute("INSERT INTO site_content(`key`,value,image,link,active,updated_at) VALUES(?,?,?,?,?,?)", ('website_color_theme',theme,'','',1,int(time.time())))
    return {'theme':theme,'status':'published'}


@app.get("/api/admin/catalog/categories", tags=["Admin"])
def admin_catalog_categories(_: dict = Depends(admin_required)):
    media={row["category"]:dict(row) for row in list_category_settings()}
    diag_by_id={x["category_id"]:x for x in category_diagnostics()}
    names={str(row["category"]).strip() for row in list_catalog(include_inactive=True) if str(row["category"]).strip()} | set(media)
    items=[]
    for c in names:
        m=media.get(c,{})
        dx=diag_by_id.get(m.get("category_id",""),{}); items.append({"category_id":m.get("category_id",""),"category":c,"display_name":m.get("display_name") or c,"description":m.get("description") or '',"image":m.get("image") or '',"active":bool(m.get("active",1)),"sort_order":int(m.get("sort_order",100)),"product_count":int(dx.get("product_count",0)),"duplicate":bool(dx.get("duplicate",False))})
    return {"items":sorted(items,key=lambda x:(x['sort_order'],x['display_name'].lower()))}

@app.post("/api/admin/catalog/categories", tags=["Admin"])
def admin_create_category(data: CategorySettings, _: dict = Depends(admin_required)):
    name=(data.new_category or data.display_name).strip()
    if not name: raise HTTPException(400,'Category name is required')
    save_category_settings(name,{**data.model_dump(), 'display_name':data.display_name or name})
    return {"status":"created","category":name}

@app.put("/api/admin/catalog/categories/{category}", tags=["Admin"])
def admin_update_category(category:str,data:CategorySettings,_:dict=Depends(admin_required)):
    new=(data.new_category or category).strip()
    if not new: raise HTTPException(400,'Category name is required')
    try:
        updated_products=rename_category(category,new) if new!=category else 0
    except ValueError as exc:
        raise HTTPException(409,str(exc)) from exc
    save_category_settings(new,{**data.model_dump(),'display_name':data.display_name or new})
    return {"status":"updated","category":new,"products_updated":updated_products}

@app.delete("/api/admin/catalog/categories/{category}", tags=["Admin"])
def admin_delete_category(category:str,_:dict=Depends(administrator_only)):
    if not delete_category_settings(category): raise HTTPException(409,'Category is referenced by catalog products. Reassign or permanently delete those products before deleting the category.')
    return {"status":"deleted"}

@app.post("/api/admin/catalog/categories/{category}/image", tags=["Admin"])
def admin_catalog_category_image(category: str, data: ImageUpload, _: dict = Depends(admin_required)):
    allowed={'image/jpeg':'jpg','image/png':'png','image/webp':'webp','image/gif':'gif','image/avif':'avif'}
    try:
        header, encoded=data.data_url.split(',',1); mime=header.split(';',1)[0].replace('data:','').lower().strip(); ext=allowed.get(mime)
        if not ext: raise ValueError('unsupported')
        raw=base64.b64decode(encoded, validate=True)
        if len(raw)>6*1024*1024: raise ValueError('too large')
    except Exception as exc: raise HTTPException(400,'Invalid category image. Use JPEG, PNG, WebP, GIF or AVIF up to 6 MB.') from exc
    upload_dir=BASE/'static'/'uploads'/'categories'; upload_dir.mkdir(parents=True,exist_ok=True)
    safe=''.join(ch if ch.isalnum() else '-' for ch in category.lower()).strip('-')[:60] or 'category'
    filename=f'{safe}-{uuid.uuid4().hex[:8]}.{ext}'; (upload_dir/filename).write_bytes(raw)
    return save_category_media(category, f'/static/uploads/categories/{filename}')


@app.get("/api/admin/catalog/categories/diagnostics", tags=["Admin"])
def admin_category_diagnostics(_:dict=Depends(administrator_only)):
    return {"items":category_diagnostics()}

@app.put("/api/admin/catalog/categories/by-id/{category_id}", tags=["Admin"])
def admin_update_category_stable(category_id:str,data:CategorySettings,_:dict=Depends(admin_required)):
    try:return {"status":"updated",**update_category_by_id(category_id,data.model_dump())}
    except ValueError as exc:raise HTTPException(409,str(exc))

@app.delete("/api/admin/catalog/categories/by-id/{category_id}", tags=["Admin"])
def admin_delete_category_stable(category_id:str,_:dict=Depends(administrator_only)):
    try:r=delete_category_by_id(category_id)
    except ValueError as exc:raise HTTPException(404,str(exc))
    if not r["deleted"]:raise HTTPException(409,f'Category is referenced by {r["product_count"]} catalog product(s). Merge/Reassign them before deletion.')
    return {"status":"deleted",**r}

class CategoryMerge(BaseModel):
    target_category_id:str

@app.post("/api/admin/catalog/categories/by-id/{category_id}/merge", tags=["Admin"])
def admin_merge_category_stable(category_id:str,data:CategoryMerge,_:dict=Depends(administrator_only)):
    try:return merge_category_by_id(category_id,data.target_category_id)
    except ValueError as exc:raise HTTPException(409,str(exc))

@app.post("/api/admin/catalog/categories/by-id/{category_id}/image", tags=["Admin"])
def admin_category_image_stable(category_id:str,data:ImageUpload,_:dict=Depends(admin_required)):
    allowed={'image/jpeg':'jpg','image/png':'png','image/webp':'webp','image/gif':'gif','image/avif':'avif'}
    try:
        header,encoded=data.data_url.split(',',1);mime=header.split(';',1)[0].replace('data:','').lower().strip();ext=allowed.get(mime)
        if not ext:raise ValueError()
        raw=base64.b64decode(encoded,validate=True)
        if len(raw)>6*1024*1024:raise ValueError()
    except Exception as exc:raise HTTPException(400,'Invalid category image. Use JPEG, PNG, WebP, GIF or AVIF up to 6 MB.') from exc
    upload_dir=BASE/'static'/'uploads'/'categories';upload_dir.mkdir(parents=True,exist_ok=True)
    filename=f'category-{category_id[:12]}-{uuid.uuid4().hex[:8]}.{ext}';(upload_dir/filename).write_bytes(raw)
    try:return save_category_image_by_id(category_id,f'/static/uploads/categories/{filename}')
    except ValueError as exc:
        (upload_dir/filename).unlink(missing_ok=True);raise HTTPException(404,str(exc))

_geo_lock=threading.Lock(); _geo_last=0.0; _geo_cache={}
@app.get("/api/location/reverse")
def reverse_location(lat: float, lon: float):
    global _geo_last
    if not (-90<=lat<=90 and -180<=lon<=180): raise HTTPException(400,'Invalid coordinates')
    key=(round(lat,5),round(lon,5))
    if key in _geo_cache: return _geo_cache[key]
    with _geo_lock:
        wait=1.05-(time.time()-_geo_last)
        if wait>0: time.sleep(wait)
        url=f'https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={lat:.6f}&lon={lon:.6f}&zoom=18&addressdetails=1'
        req=urllib.request.Request(url, headers={'User-Agent':'IndianFamilyMarket/2.0 (+https://theindianfamily.shop)','Accept':'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=6) as resp: payload=json.loads(resp.read().decode('utf-8'))
        except Exception as exc: raise HTTPException(503,'Locality lookup is temporarily unavailable') from exc
        _geo_last=time.time(); a=payload.get('address') or {}
        result={'latitude':lat,'longitude':lon,'locality':a.get('suburb') or a.get('neighbourhood') or a.get('quarter') or a.get('village') or a.get('town') or a.get('city_district') or '', 'city':a.get('city') or a.get('town') or a.get('municipality') or a.get('county') or '', 'state':a.get('state') or '', 'pincode':a.get('postcode') or '', 'display_name':payload.get('display_name') or ''}
        _geo_cache[key]=result
        if len(_geo_cache)>500: _geo_cache.pop(next(iter(_geo_cache)))
        return result

from . import catalog_gallery as _catalog_gallery

class GalleryBatch(BaseModel):
    images: list[dict]

class GalleryUpdate(BaseModel):
    urls: list[str]
    primary: str = ''

@app.get('/api/catalog/{product_id}/gallery')
def public_catalog_gallery(product_id: str):
    return _catalog_gallery.get_gallery(product_id, public=True)

@app.get('/api/admin/catalog/{product_id}/gallery', tags=['Admin'])
def admin_catalog_gallery(product_id: str, _: dict = Depends(admin_required)):
    return _catalog_gallery.get_gallery(product_id)

@app.post('/api/admin/catalog/{product_id}/gallery', tags=['Admin'])
def admin_catalog_gallery_upload(product_id: str, payload: GalleryBatch, _: dict = Depends(admin_required)):
    return _catalog_gallery.upload(product_id, payload.images)

@app.put('/api/admin/catalog/{product_id}/gallery', tags=['Admin'])
def admin_catalog_gallery_update(product_id: str, payload: GalleryUpdate, _: dict = Depends(admin_required)):
    return _catalog_gallery.update(product_id, payload.urls, payload.primary)

@app.post("/api/admin/catalog/{product_id}/image", tags=["Admin"])
def admin_upload_image(product_id: str, data: ImageUpload, _: dict = Depends(admin_required)):
    if not catalog_product(product_id):
        raise HTTPException(404, 'Product not found')
    allowed = {
        'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp',
        'image/gif': 'gif', 'image/avif': 'avif',
    }
    try:
        header, encoded = data.data_url.split(',', 1)
        mime = header.split(';', 1)[0].replace('data:', '').lower().strip()
        extension = allowed.get(mime)
        if not extension:
            raise ValueError('unsupported image type')
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > 6 * 1024 * 1024:
            raise ValueError('image exceeds 6 MB')
    except Exception as exc:
        raise HTTPException(400, 'Invalid image. Use JPEG, PNG, WebP, GIF or AVIF up to 6 MB.') from exc
    upload_dir = BASE / 'static' / 'uploads' / 'catalog'
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f'{product_id}-{uuid.uuid4().hex[:8]}.{extension}'
    target = upload_dir / filename
    target.write_bytes(raw)
    current = dict(catalog_product(product_id))
    old_image = current.get('image') or ''
    current['image'] = f'/static/uploads/catalog/{filename}'
    save_catalog_product(current, product_id)
    # Delete only files managed by this catalog store; never delete external URLs.
    if old_image.startswith('/static/uploads/catalog/'):
        old_path = BASE / old_image.lstrip('/')
        try:
            if old_path.is_file() and old_path != target:
                old_path.unlink()
        except OSError:
            log.warning('catalog_image_cleanup_failed path=%s', old_path)
    return {"status": "uploaded", "image": current['image'], "mime_type": mime, "size": len(raw)}

def _catalog_validation_flags():
    flags={}
    report_path=CATALOG_TEMPLATE_DIR/'last-validation.json'
    if not report_path.exists(): return flags
    try: report=json.loads(report_path.read_text(encoding='utf-8'))
    except Exception: return flags
    for pid in (report.get('diff') or {}).get('missing_from_latest',[]): flags[str(pid)]={'validation_status':'stale','validation_message':'Missing from latest validated template'}
    for err in report.get('errors') or []:
        pid=str(err.get('product_id') or '').strip()
        if pid: flags[pid]={'validation_status':'validation_error','validation_message':str(err.get('error') or 'Validation error')}
    return flags

@app.get("/api/admin/catalog", tags=["Admin"])
def admin_catalog(_: dict = Depends(admin_required)):
    flags=_catalog_validation_flags(); out=[]
    for p in list_catalog(include_inactive=True):
        d=dict(p); d.update(flags.get(str(d['id']), {'validation_status':'valid','validation_message':''})); out.append(d)
    return {"items": out}

@app.post("/api/admin/catalog", tags=["Admin"])
def admin_create_catalog(data: CatalogItem, _: dict = Depends(admin_required)):
    if catalog_product(data.id):
        raise HTTPException(409, "A product with this ID already exists")
    save_catalog_product(data.model_dump())
    return {"status": "created", "id": data.id}

@app.put("/api/admin/catalog/{product_id}", tags=["Admin"])
def admin_update_catalog(product_id: str, data: CatalogItem, _: dict = Depends(admin_required)):
    if not catalog_product(product_id):
        raise HTTPException(404, "Product not found")
    save_catalog_product(data.model_dump(), product_id)
    return {"status": "updated", "id": product_id}

@app.delete("/api/admin/catalog/{product_id}", tags=["Admin"])
def admin_delete_catalog(product_id: str, _: dict = Depends(administrator_only)):
    if not catalog_product(product_id):
        raise HTTPException(404, "Product not found")
    delete_catalog_product(product_id)
    return {"status": "archived", "id": product_id}

@app.post("/api/admin/catalog/bulk/archive", tags=["Admin"])
def admin_bulk_archive_catalog(data: BulkCatalogAction, _: dict = Depends(administrator_only)):
    ids=list(dict.fromkeys(x.strip() for x in data.product_ids if x.strip()))
    missing=[x for x in ids if not catalog_product(x)]
    if missing: raise HTTPException(404, "Product(s) not found: "+", ".join(missing[:10]))
    return {"status":"archived","count":archive_catalog_products(ids),"product_ids":ids}

@app.post("/api/admin/catalog/bulk/delete", tags=["Admin"])
def admin_bulk_delete_catalog(data: BulkCatalogAction, _: dict = Depends(administrator_only)):
    ids=list(dict.fromkeys(x.strip() for x in data.product_ids if x.strip()))
    missing=[x for x in ids if not catalog_product(x)]
    if missing: raise HTTPException(404, "Product(s) not found: "+", ".join(missing[:10]))
    not_archived=[]
    for pid in ids:
        row=catalog_product(pid)
        if row and bool(row['active']) and str(row['status'] or '').lower() != 'archived':
            not_archived.append(pid)
    if not_archived:
        raise HTTPException(409, "Delete blocked: archive all selected products before permanent deletion: "+", ".join(not_archived[:20]))
    referenced=catalog_products_referenced_by_orders(ids)
    if referenced:
        raise HTTPException(409, "Delete blocked: product(s) referenced by order history must be archived instead: "+", ".join(referenced[:20]))
    managed_images=[]
    for pid in ids:
        row=catalog_product(pid); image_path=str(row['image'] or '') if row else ''
        if image_path.startswith('/static/uploads/catalog/'): managed_images.append(BASE/image_path.lstrip('/'))
    count=hard_delete_catalog_products(ids)
    for image_path in managed_images:
        try:
            if image_path.is_file(): image_path.unlink()
        except OSError: log.warning('catalog_bulk_image_cleanup_failed path=%s', image_path)
    return {"status":"deleted","count":count,"product_ids":ids}

def _catalog_template_fields():
    available=[h for h in CatalogItem.model_fields if h != 'active']
    try:
        configured=get_catalog_template_config()
    except Exception:
        log.exception('catalog_template_config_read_failed')
        raise HTTPException(503, 'Unable to read catalog template configuration. Check the server log.')
    ordered=[h for h in configured if h in available]
    return ordered+[h for h in available if h not in ordered]

@app.get("/api/admin/catalog/template-config", tags=["Admin"])
def admin_template_config(_:dict=Depends(administrator_only)):
    fields=[]
    for name in _catalog_template_fields():
        f=CatalogItem.model_fields[name]
        fields.append({'name':name,'required':f.is_required(),'enabled':True})
    return {'fields':fields}

@app.put("/api/admin/catalog/template-config", tags=["Admin"])
def admin_template_config_save(data:TemplateConfig,_:dict=Depends(administrator_only)):
    available=[h for h in CatalogItem.model_fields if h != 'active']; requested=[]
    for h in data.fields:
        if h in available and h not in requested: requested.append(h)
    required=[h for h in ['id','name','category','state','price','mrp','unit','description','status'] if h in available]
    missing=[h for h in required if h not in requested]
    if missing: raise HTTPException(400,'Required template fields cannot be removed: '+', '.join(missing))
    try:
        save_catalog_template_config(requested)
    except Exception:
        log.exception('catalog_template_config_save_failed')
        raise HTTPException(503, 'Unable to save catalog template configuration. Check the server log and site_content table permissions.')
    return {'status':'updated','fields':requested}

@app.get("/api/admin/catalog/template.xlsx", tags=["Admin"])
def admin_catalog_template(_: dict = Depends(administrator_only)):
    try:
        from openpyxl import Workbook
    except ImportError:
        raise HTTPException(503, 'Excel support is unavailable because openpyxl is not installed on the server. Install requirements.txt and restart the application.')
    try:
        from .catalog_template_export import build_catalog_workbook
        workbook = build_catalog_workbook(_catalog_template_fields(), list_catalog(include_inactive=True), Workbook)
        output = io.BytesIO()
        workbook.save(output)
        output.seek(0)
    except Exception:
        log.exception('catalog_template_export_failed')
        raise HTTPException(503, 'Unable to generate the Excel template. Check the server log for details.')
    return StreamingResponse(output,media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",headers={"Content-Disposition":"attachment; filename=indian-family-market-catalog.xlsx","Cache-Control":"no-store"})

CATALOG_TEMPLATE_DIR = BASE / "data" / "catalog_templates"
CATALOG_TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)

class TemplateCleanupRequest(BaseModel):
    mode: str = Field(pattern='^(month|3months|6months|year|custom)$')
    start_date: str = ''
    end_date: str = ''
class TemplateRollbackRequest(BaseModel):
    template_id: str = Field(min_length=1, max_length=220)

def _safe_template_name(value: str) -> str:
    return ''.join(c for c in Path(value).name if c.isalnum() or c in '._-')[:180] or 'catalog.xlsx'
def _template_path(template_id: str) -> Path:
    path=CATALOG_TEMPLATE_DIR/_safe_template_name(template_id)
    if not path.exists() or not path.is_file(): raise HTTPException(404,'Template backup not found')
    return path
def _read_catalog_template(raw: bytes, filename: str):
    name=filename.lower()
    if name.endswith('.xlsx'):
        try: from openpyxl import load_workbook
        except ImportError: raise HTTPException(503,'Excel import is unavailable because openpyxl is not installed on the server. Install requirements.txt and restart the application.')
        ws=load_workbook(io.BytesIO(raw),data_only=True).active; vals=list(ws.values)
        if not vals: return []
        headers=[str(x or '').strip() for x in vals[0]]
        return [dict(zip(headers,v)) for v in vals[1:] if any(x not in (None,'') for x in v)]
    if name.endswith('.csv'): return list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    raise ValueError('Use .xlsx or .csv')
def _split_variant(value): return [x.strip() for x in str(value if value is not None else '').split('/')]
def _validate_catalog_rows(rows):
    required={'id','name','category','state','price','mrp','unit','description','status'}
    if not rows: return [],[],['Template contains no catalog rows']
    missing=required-set(rows[0])
    if missing: return [],[],['Missing columns: '+', '.join(sorted(missing))]
    errors=[]; prepared=[]; seen_ids=set()
    for i,r in enumerate(rows,2):
        try:
            pid=str(r.get('id') or '').strip()
            if not pid: raise ValueError('product id is required')
            if pid in seen_ids: raise ValueError('duplicate product id in upload')
            seen_ids.add(pid); status=str(r.get('status') or 'live').strip().lower().replace(' ','_')
            if status not in {'live','coming_soon','archived'}: raise ValueError('invalid status')
            prices=_split_variant(r.get('price')); mrps=_split_variant(r.get('mrp')); units=_split_variant(r.get('unit'))
            if any(x=='' for x in prices): raise ValueError('selling price is required')
            if len(prices)!=len(mrps) or len(prices)!=len(units): raise ValueError(f'variant count mismatch: price={len(prices)}, mrp={len(mrps)}, unit={len(units)}')
            nums=[]; nmrps=[]
            for n,(pv,mv,uv) in enumerate(zip(prices,mrps,units),1):
                try: price=float(pv); mrp=float(mv)
                except Exception: raise ValueError(f'variant {n}: price and MRP must be numeric values')
                if price<0 or mrp<0: raise ValueError(f'variant {n}: price/MRP cannot be negative')
                if not uv: raise ValueError(f'variant {n}: unit is required')
                if mrp<price: raise ValueError(f'variant {n} ({uv}): MRP {mrp:g} cannot be lower than selling price {price:g}')
                nums.append(price); nmrps.append(mrp)
            state=str(r.get('state') or '').strip()
            if len(state)<2: raise ValueError('state/region is required')
            existing=catalog_product(pid); incoming_image=str(r.get('image') or '').strip(); preserved_image=(str(existing['image'] or '') if existing and not incoming_image else incoming_image)
            item={'id':pid,'name':str(r.get('name') or '').strip(),'category':str(r.get('category') or '').strip(),'state':state,'price':nums[0],'mrp':nmrps[0],'unit':units[0],'description':str(r.get('description') or ''),'image':preserved_image,'parent_url':str(r.get('parent_url') or ''),'status':status,'active':status!='archived'}
            CatalogItem(**item)
            if not item['name'] or not item['category']: raise ValueError('name and category are required')
            prepared.append(item)
        except Exception as e: errors.append({'row':i,'product_id':str(r.get('id') or ''),'error':str(e)})
    return prepared,errors,[]
def _template_diff(rows):
    previous={str(r['id']):dict(r) for r in list_catalog(include_inactive=True)}; latest={str(r.get('id') or '').strip():r for r in rows if str(r.get('id') or '').strip()}
    added=sorted(set(latest)-set(previous)); missing=sorted(set(previous)-set(latest)); changed=[]; fields=['name','category','state','price','mrp','unit','description','image','parent_url','status']
    for pid in sorted(set(latest)&set(previous)):
        diffs=[]
        for f in fields:
            a=str(latest[pid].get(f) if latest[pid].get(f) is not None else '').strip(); b=str(previous[pid].get(f) if previous[pid].get(f) is not None else '').strip()
            if f=='image' and not a: a=b
            if a!=b: diffs.append(f)
        if diffs: changed.append({'id':pid,'fields':diffs})
    return {'added':added,'missing_from_latest':missing,'changed':changed}
def _write_validation_report(filename,rows,errors,general):
    diff=_template_diff(rows); now=int(time.time()); report={'created_at':now,'filename':filename,'errors':errors,'general_errors':general,'diff':diff,'rows':len(rows)}
    (CATALOG_TEMPLATE_DIR/'last-validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    lis=''.join(f"<li>Row {e.get('row','-')} {html.escape(e.get('product_id',''))}: {html.escape(e['error'])}</li>" for e in errors)+''.join(f'<li>{html.escape(x)}</li>' for x in general)
    body='<!doctype html><html><head><meta charset="utf-8"><title>Catalog validation</title><style>body{font:14px Arial;max-width:1000px;margin:30px auto;padding:0 20px}.bad{color:#9b2c1f}</style></head><body>'
    body+=f'<h1>Catalog template validation</h1><p><b>File:</b> {html.escape(filename)}<br><b>Generated:</b> {time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(now))}</p><h2 class="bad">Validation errors ({len(errors)+len(general)})</h2><ol>{lis or "<li>None</li>"}</ol>'
    body+=f'<h2>Comparison with current / n-1 catalog</h2><p>Rows: {len(rows)} | Added: {len(diff["added"])} | Changed: {len(diff["changed"])} | Missing from latest: {len(diff["missing_from_latest"])} (missing rows are not deleted by refresh)</p>'
    body+=f'<h3>Added IDs</h3><p>{html.escape(", ".join(diff["added"]) or "None")}</p><h3>Changed IDs</h3><p>{html.escape(", ".join(x["id"] for x in diff["changed"]) or "None")}</p><h3>Missing IDs</h3><p>{html.escape(", ".join(diff["missing_from_latest"]) or "None")}</p></body></html>'
    (CATALOG_TEMPLATE_DIR/'last-validation.html').write_text(body,encoding='utf-8'); return report
def _make_catalog_snapshot():
    try: from openpyxl import Workbook
    except ImportError: raise HTTPException(503,'Excel support is unavailable because openpyxl is not installed on the server.')
    wb=Workbook(); ws=wb.active; ws.title='Catalog'; headers=_catalog_template_fields(); ws.append(headers)
    for r in list_catalog(include_inactive=True):
        d=dict(r); ws.append([d.get(h,'') for h in headers])
    b=io.BytesIO(); wb.save(b); return b.getvalue()
def _cleanup_template_backups(days=30):
    cutoff=time.time()-days*86400
    for p in list(CATALOG_TEMPLATE_DIR.glob('backup-*'))+list(CATALOG_TEMPLATE_DIR.glob('preop-*'))+list(CATALOG_TEMPLATE_DIR.glob('candidate-*')):
        try:
            if p.stat().st_mtime<cutoff: p.unlink()
        except OSError: pass
# Backward-compatible contract marker: _backup_active_template() defaults to one daily snapshot.
def _backup_active_template(kind='daily'):
    """Daily backups are de-duplicated; destructive operations get separate pre-op snapshots."""
    snapshot=_make_catalog_snapshot(); day=time.strftime('%Y%m%d'); stamp=time.strftime('%Y%m%d-%H%M%S')
    if kind=='daily':
        existing=sorted(CATALOG_TEMPLATE_DIR.glob(f'backup-{day}-*.xlsx'))
        if existing: return existing[0]
        dest=CATALOG_TEMPLATE_DIR/f'backup-{stamp}.xlsx'
    else:
        dest=CATALOG_TEMPLATE_DIR/f'preop-{stamp}.xlsx'
    dest.write_bytes(snapshot); return dest

CATALOG_IMPORT_LOCK=threading.Lock()

@app.post('/api/admin/catalog/import', tags=['Admin'])
def admin_catalog_import(data:BulkCatalogUpload,user:dict=Depends(admin_required)):
    if data.mode=='authoritative' and user.get('role')!='administrator': raise HTTPException(403,'Authoritative rebuild is Administrator only')
    if not CATALOG_IMPORT_LOCK.acquire(blocking=False): raise HTTPException(409,'Another catalog import is already running')
    try:
        _cleanup_template_backups(30); raw=base64.b64decode(data.data_url.split(',',1)[1]); filename=_safe_template_name(data.filename); rows=_read_catalog_template(raw,filename); prepared,errors,general=_validate_catalog_rows(rows); report=_write_validation_report(filename,rows,errors,general)
        stamp=time.strftime('%Y%m%d-%H%M%S'); candidate=CATALOG_TEMPLATE_DIR/f'candidate-{stamp}-{filename}'; candidate.write_bytes(raw)
        if errors or general: return {'status':'rejected','inserted':0,'updated':0,'rows':len(rows),'errors':errors+[{'row':'-','error':x} for x in general],'validation':report}
        preserved=sum(1 for r in rows if str(r.get('id') or '').strip() and catalog_product(str(r.get('id')).strip()) and not str(r.get('image') or '').strip())
        if data.validate_only: return {'status':'validated','rows':len(prepared),'new':sum(1 for x in prepared if not catalog_product(x['id'])),'updates':sum(1 for x in prepared if catalog_product(x['id'])),'images_preserved':preserved,'missing':len((report.get('diff') or {}).get('missing_from_latest',[])),'mode':data.mode,'errors':[],'validation':report,'candidate_id':candidate.name}
        _backup_active_template('daily'); _backup_active_template('preop')
        result=import_catalog_atomic(prepared,authoritative=data.mode=='authoritative')
        # Active template is always regenerated from DB so preserved image mappings round-trip.
        active=CATALOG_TEMPLATE_DIR/'active.xlsx'; active.write_bytes(_make_catalog_snapshot()); _cleanup_template_backups(30)
        return {'status':'imported',**result,'errors':[],'backup_created':True,'mode':data.mode}
    except HTTPException: raise
    except Exception as ex: raise HTTPException(400,str(ex))
    finally: CATALOG_IMPORT_LOCK.release()
@app.get('/api/admin/catalog/templates', tags=['Admin'])
def admin_catalog_templates(kind:str='', page:int=1, page_size:int=25, _:dict=Depends(admin_required)):
    _cleanup_template_backups(30); items=[]
    for p in sorted(CATALOG_TEMPLATE_DIR.glob('*'),key=lambda x:x.stat().st_mtime,reverse=True):
        if not p.is_file() or p.name.startswith('last-validation'): continue
        item_kind='active' if p.name=='active.xlsx' else ('daily' if p.name.startswith('backup-') else ('pre_operation' if p.name.startswith('preop-') else 'candidate')); items.append({'id':p.name,'kind':item_kind,'size':p.stat().st_size,'modified_at':int(p.stat().st_mtime)})
    report={}; rp=CATALOG_TEMPLATE_DIR/'last-validation.json'
    if rp.exists():
        try: report=json.loads(rp.read_text(encoding='utf-8'))
        except Exception: report={}
    db_size=0
    try:
        value=settings.database_url; db=Path(value[10:]).resolve() if value.startswith('sqlite:///') else None
        if db and db.exists(): db_size=db.stat().st_size
    except Exception: pass
    image_dir=BASE/'static'/'uploads'/'catalog'; image_size=sum(x.stat().st_size for x in image_dir.rglob('*') if x.is_file()) if image_dir.exists() else 0; template_size=sum(x.stat().st_size for x in CATALOG_TEMPLATE_DIR.glob('*') if x.is_file())
    filtered=[x for x in items if not kind or x['kind']==kind]; page=max(1,page); page_size=max(5,min(page_size,100)); total=len(filtered); start=(page-1)*page_size
    return {'items':filtered[start:start+page_size],'total':total,'page':page,'page_size':page_size,'validation':report,'storage':{'catalog_database_bytes':db_size,'catalog_images_bytes':image_size,'template_backups_bytes':template_size},'retention_days':30}
@app.get('/api/admin/catalog/templates/{template_id}/download', tags=['Admin'])
def admin_catalog_template_download(template_id:str,_:dict=Depends(administrator_only)):
    p=_template_path(template_id); return FileResponse(p,filename=p.name)
@app.get('/api/admin/catalog/validation/download', tags=['Admin'])
def admin_catalog_validation_download(_:dict=Depends(administrator_only)):
    p=CATALOG_TEMPLATE_DIR/'last-validation.html'
    if not p.exists(): raise HTTPException(404,'No validation report is available yet')
    return FileResponse(p,media_type='text/html',filename='catalog-last-validation.html')
@app.delete('/api/admin/catalog/templates/{template_id}', tags=['Admin'])
def admin_catalog_template_delete(template_id:str,_:dict=Depends(administrator_only)):
    p=_template_path(template_id)
    if p.name=='active.xlsx': raise HTTPException(400,'The active template cannot be deleted. Roll back or refresh it first.')
    p.unlink(); return {'status':'deleted'}
@app.post('/api/admin/catalog/templates/rollback', tags=['Admin'])
def admin_catalog_template_rollback(data:TemplateRollbackRequest,_:dict=Depends(administrator_only)):
    p=_template_path(data.template_id)
    if not (p.name.startswith('backup-') or p.name.startswith('preop-')): raise HTTPException(400,'Only daily or pre-operation snapshots can be restored')
    raw=p.read_bytes(); rows=_read_catalog_template(raw,p.name); prepared,errors,general=_validate_catalog_rows(rows); _write_validation_report(p.name,rows,errors,general)
    if errors or general: return {'status':'rejected','errors':errors+[{'row':'-','error':x} for x in general]}
    _backup_active_template('preop'); result=import_catalog_atomic(prepared,authoritative=True); (CATALOG_TEMPLATE_DIR/'active.xlsx').write_bytes(_make_catalog_snapshot())
    return {'status':'rolled_back',**result,'template_id':p.name}
@app.post('/api/admin/catalog/templates/cleanup', tags=['Admin'])
def admin_catalog_template_cleanup(data:TemplateCleanupRequest,_:dict=Depends(administrator_only)):
    now=time.time(); deleted=[]
    if data.mode=='month': start,end=0,now-30*86400
    elif data.mode=='3months': start,end=0,now-90*86400
    elif data.mode=='6months': start,end=0,now-180*86400
    elif data.mode=='year': start,end=0,now-365*86400
    else:
        try: start=time.mktime(time.strptime(data.start_date,'%Y-%m-%d')) if data.start_date else 0; end=time.mktime(time.strptime(data.end_date,'%Y-%m-%d'))+86399 if data.end_date else now
        except ValueError: raise HTTPException(400,'Custom dates must use YYYY-MM-DD')
    for p in list(CATALOG_TEMPLATE_DIR.glob('backup-*'))+list(CATALOG_TEMPLATE_DIR.glob('preop-*'))+list(CATALOG_TEMPLATE_DIR.glob('candidate-*')):
        mt=p.stat().st_mtime
        if start<=mt<=end: p.unlink(); deleted.append(p.name)
    return {'status':'cleaned','deleted':deleted,'count':len(deleted)}

class ImageRecoveryApply(BaseModel):
    product_id:str
    image_path:str
class ForceCategoryDeleteRequest(BaseModel):
    category_ids:list[str]=Field(min_length=1,max_length=100)
    strategy:str=Field(pattern='^(reassign|archive|delete_products)$')
    target_category_id:str=''

@app.get('/api/admin/catalog/image-recovery/scan', tags=['Admin'])
def admin_catalog_image_recovery_scan(_:dict=Depends(admin_required)):
    upload_dir=BASE/'static'/'uploads'/'catalog'; files=list(upload_dir.glob('*')) if upload_dir.exists() else []
    results=[]
    for row in list_catalog(include_inactive=True):
        d=dict(row); current=str(d.get('image') or ''); current_ok=bool(current and (not current.startswith('/static/uploads/catalog/') or (BASE/current.lstrip('/')).is_file()))
        if current_ok: continue
        pid=str(d['id']); exact=[p for p in files if p.is_file() and p.name.startswith(pid+'-')]
        candidates=[f'/static/uploads/catalog/{p.name}' for p in sorted(exact,key=lambda x:x.stat().st_mtime,reverse=True)[:5]]
        results.append({'product_id':pid,'name':d['name'],'current_image':current,'status':'exact_candidate' if candidates else 'unresolved','candidates':candidates,'confidence':'exact product ID' if candidates else 'none'})
    return {'items':results,'missing_count':len(results),'exact_candidates':sum(1 for x in results if x['candidates'])}

@app.post('/api/admin/catalog/image-recovery/apply', tags=['Admin'])
def admin_catalog_image_recovery_apply(data:ImageRecoveryApply,_:dict=Depends(administrator_only)):
    row=catalog_product(data.product_id)
    if not row: raise HTTPException(404,'Product not found')
    path=data.image_path.strip()
    if not path.startswith('/static/uploads/catalog/') or not (BASE/path.lstrip('/')).is_file(): raise HTTPException(400,'Recovery image must be an existing managed catalog image')
    current=dict(row); current['image']=path; save_catalog_product(current,data.product_id)
    return {'status':'restored','product_id':data.product_id,'image':path}

@app.post('/api/admin/catalog/categories/force-delete', tags=['Admin'])
def admin_catalog_categories_force_delete(data:ForceCategoryDeleteRequest,_:dict=Depends(administrator_only)):
    _backup_active_template('preop')
    try:return {'status':'completed',**force_delete_categories(data.category_ids,data.strategy,data.target_category_id)}
    except ValueError as ex:raise HTTPException(409,str(ex))

@app.get("/api/admin/offers/recommendations", tags=["Admin"])
def admin_offer_recommendations(_:dict=Depends(admin_required)):
    products={r['id']:dict(r) for r in list_catalog(include_inactive=True)}; qty=Counter(); revenue=Counter(); catqty=Counter()
    for order in list_orders(limit=1000):
        if order['status'] not in {'paid','created'}: continue
        try: lines=json.loads(order['items_json'] or '[]')
        except Exception: continue
        for line in lines:
            pid=str(line.get('id') or line.get('product_id') or ''); q=max(0,int(line.get('qty') or line.get('quantity') or 0)); p=products.get(pid,{})
            qty[pid]+=q; revenue[pid]+=q*float(line.get('price') or p.get('price') or 0); catqty[p.get('category','')]+=q
    recs=[]
    if qty:
        pid,n=qty.most_common(1)[0]; p=products.get(pid,{})
        recs.append({'kind':'top_product','title':f"Top seller: {p.get('name',pid)}",'message':f'{n} units found in recent order history. Consider a product-specific bundle or modest percentage promotion; verify margin before activation.','scope':'product','target':pid})
    if catqty:
        cat,n=catqty.most_common(1)[0]; recs.append({'kind':'top_category','title':f'Popular category: {cat}','message':f'{n} units found in recent order history. Consider a category campaign or cross-sell with a complementary category.','scope':'category','target':cat})
    discounted=[p for p in products.values() if p.get('active') and float(p.get('mrp') or 0)>float(p.get('price') or 0)]
    if discounted: recs.append({'kind':'existing_discount','title':'Promote existing markdowns','message':f'{len(discounted)} live catalog items already have MRP above selling price. Consider highlighting these before creating deeper discounts.','scope':'site','target':''})
    if not recs: recs.append({'kind':'insufficient_history','title':'Build order history first','message':'There is not enough order history for a sales-trend recommendation. Use an informational campaign and review results before discounting.','scope':'site','target':''})
    return {'items':recs[:4],'basis':'Recent stored order history and current catalog pricing. Recommendations are heuristics, not forecasts.'}

def _coupon_quote(code, items, *, user_id=None):
    """Compute a non-authoritative preview or server-authoritative checkout discount.

    The caller supplies server-loaded product records; never accept client prices.
    """
    from decimal import Decimal, ROUND_HALF_UP
    normalized = str(code or '').strip().upper()
    if not normalized:
        return {"valid": False, "code": "", "discount": 0.0, "message": "Enter a coupon code."}
    matching = [dict(o) for o in list_offers(active_public=True)
                if str(o['code'] or '').strip().upper() == normalized
                and o['offer_type'] in ('percentage', 'fixed') and float(o['value'] or 0) > 0]
    if not matching:
        return {"valid": False, "code": normalized, "discount": 0.0, "message": "Coupon is not active or has expired."}
    offer = matching[0]
    scope = offer['scope']
    target = str(offer['target'] or '').strip().lower()
    applicable = [p for p, qty in items if scope == 'site' or
                  (scope == 'category' and str(p.category).lower() == target) or
                  (scope == 'product' and str(p.id).lower() == target)]
    eligible = sum((Decimal(str(p.price)) * qty for p, qty in items
                    if p in applicable), Decimal('0'))
    if eligible <= 0:
        return {"valid": False, "code": normalized, "discount": 0.0, "message": "Coupon does not apply to these products."}
    value = Decimal(str(offer['value']))
    if offer['offer_type'] == 'percentage':
        if value > 100:
            return {"valid": False, "code": normalized, "discount": 0.0, "message": "Coupon configuration is invalid."}
        discount = eligible * value / Decimal('100')
    else:
        discount = value
    discount = min(eligible, discount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return {"valid": True, "code": normalized, "discount": float(discount),
            "message": "Coupon eligible. Final amount is confirmed at checkout."}

class CouponPreview(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    items: list[CheckoutItem] = Field(min_length=1)

@app.post("/api/offers/validate")
def validate_coupon(data: CouponPreview):
    products = {p.id: p for p in (row_product(row) for row in list_catalog())}
    items = []
    for item in data.items:
        p = products.get(item.product_id)
        if not p or not p.active or getattr(p, 'status', 'live') != 'live':
            raise HTTPException(400, "Product is not available.")
        items.append((p, item.quantity))
    return _coupon_quote(data.code, items)

@app.get("/api/offers")
def public_offers(): return {"items":[dict(x) for x in list_offers(active_public=True)]}
@app.get("/api/admin/offers", tags=["Admin"])
def admin_offers(_: dict=Depends(admin_required)): return {"items":[dict(x) for x in list_offers()]}
@app.post("/api/admin/offers", tags=["Admin"])
def admin_offer_create(data:OfferItem,_:dict=Depends(admin_required)):
    save_offer(data.model_dump()); return {"status":"created","id":data.id}
@app.put("/api/admin/offers/{offer_id}", tags=["Admin"])
def admin_offer_update(offer_id:str,data:OfferItem,_:dict=Depends(administrator_only)):
    save_offer(data.model_dump(),offer_id); return {"status":"updated","id":offer_id}
@app.delete("/api/admin/offers/{offer_id}", tags=["Admin"])
def admin_offer_delete(offer_id:str,_:dict=Depends(administrator_only)):
    delete_offer(offer_id); return {"status":"deleted"}

# Phase 4: controlled Marketing workspace. Marketing editors may prepare campaign
# drafts only; activation/publishing remains outside this delegated permission.
@app.get("/api/admin/marketing/drafts", tags=["SEO & Marketing Workspace"])
def marketing_drafts(_: dict = Depends(market_permission_required("marketing.draft.edit"))):
    return {"items":[dict(x) for x in list_offers() if x["status"] == "draft"]}

@app.post("/api/admin/marketing/drafts", tags=["SEO & Marketing Workspace"])
def marketing_draft_create(data: OfferItem, user: dict = Depends(market_permission_required("marketing.draft.edit"))):
    payload=data.model_dump(); payload["status"]="draft"
    save_offer(payload)
    log_auth_event(f"log_{uuid.uuid4().hex[:16]}", int(time.time()), "marketing_draft_created", True, user.get("sub",""), user.get("email",""), "", "", f"offer={data.id}")
    return {"status":"draft_created","id":data.id}

@app.put("/api/admin/marketing/drafts/{offer_id}", tags=["SEO & Marketing Workspace"])
def marketing_draft_update(offer_id: str, data: OfferItem, user: dict = Depends(market_permission_required("marketing.draft.edit"))):
    existing=next((dict(x) for x in list_offers() if x["id"]==offer_id),None)
    if not existing: raise HTTPException(404,"Marketing draft not found")
    if existing["status"] != "draft": raise HTTPException(409,"Only draft campaigns can be changed in the delegated Marketing workspace")
    payload=data.model_dump(); payload["status"]="draft"; payload["id"]=offer_id
    save_offer(payload,offer_id)
    log_auth_event(f"log_{uuid.uuid4().hex[:16]}", int(time.time()), "marketing_draft_updated", True, user.get("sub",""), user.get("email",""), "", "", f"offer={offer_id}")
    return {"status":"draft_updated","id":offer_id}

@app.post("/api/auth/signup")
def signup(data: Signup, request: Request):
    if find_user_by_email(data.email):
        raise HTTPException(409, "An account with this email already exists")
    user_id = f"usr_{uuid.uuid4().hex[:16]}"
    if data.username and find_user_by_login(data.username):
        raise HTTPException(409, "This username is already in use")
    create_user(user_id, data.name, data.email, data.phone, hash_password(data.password), int(time.time()), username=data.username)
    token = create_token(user_id, data.email)
    log_auth_event(f"log_{uuid.uuid4().hex[:16]}", int(time.time()), "signup", True, user_id, data.email,
                   request.client.host if request.client else "", request.headers.get("user-agent", "")[:500], "account created")
    return {"token": token, "user": {"id": user_id, "name": data.name, "email": data.email, "username": data.username or None, "phone": data.phone, "role": "customer", "must_change_password": False}}

@app.post("/api/auth/login")
def login(data: Login, request: Request):
    ip = request.client.host if request.client else ""
    ua = request.headers.get("user-agent", "")[:500]
    identity=data.email.strip()
    # Built-in administrator uses the same storefront login prompt as customers.
    ap=get_admin_profile()
    if identity.lower() in {ap["email"].lower(), ap["username"].lower()} and verify_password(data.password, get_admin_password_hash()):
        token=create_token("admin", ap["email"], role="admin")
        log_auth_event(f"log_{uuid.uuid4().hex[:16]}", int(time.time()), "login_success", True, "admin", identity, ip, ua, "administrator login via unified storefront auth")
        return {"token":token,"user":{"id":"admin","name":ap["name"],"email":ap["email"],"username":ap["username"],"phone":ap["phone"],"role":"admin","must_change_password":False}}
    user = find_user_by_login(identity)
    if not user or not verify_password(data.password, user["password_hash"]):
        log_auth_event(f"log_{uuid.uuid4().hex[:16]}", int(time.time()), "login_failed", False, "", identity, ip, ua, "invalid username/email or password")
        raise HTTPException(401, "Invalid username/email or password")
    token = create_token(user["id"], user["email"], role=user["role"])
    log_auth_event(f"log_{uuid.uuid4().hex[:16]}", int(time.time()), "login_success", True, user["id"], identity, ip, ua, f"role={user['role']}")
    return {"token": token, "user": {"id": user["id"], "name": user["name"], "email": user["email"], "username": user["username"], "phone": user["phone"], "role": user["role"], "must_change_password": bool(user["must_change_password"])}}

def _otp_hash(identity: str, code: str) -> str:
    return hmac.new(settings.auth_secret.encode(), f"{identity.lower().strip()}:{code}".encode(), hashlib.sha256).hexdigest()

def _deliver_otp(email: str, code: str):
    """Send OTP by authenticated SMTP; SMS webhook is not required."""
    if not (settings.smtp_host and settings.smtp_from and settings.smtp_username and settings.smtp_password):
        raise HTTPException(503, "Email OTP delivery is not configured")
    from email.message import EmailMessage
    import ssl
    msg = EmailMessage()
    msg['Subject'] = 'Indian Family Market login verification code'
    msg['From'] = settings.smtp_from
    msg['To'] = email
    msg.set_content(f"Your Indian Family Market verification code is {code}. It expires in {settings.otp_expiry_seconds // 60} minutes. If you did not request it, ignore this message.")
    context = ssl.create_default_context()
    if settings.smtp_use_ssl:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15, context=context) as smtp:
            smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls(context=context)
            smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(msg)


def _email_otp_account(email: str):
    """Reject ambiguous email ownership between the built-in admin and users."""
    accounts = []
    user = find_user_by_email(email)
    if user:
        accounts.append(dict(user))
    admin = get_admin_profile()
    if admin['email'].strip().lower() == email:
        accounts.append({'id': 'admin', 'name': admin['name'], 'email': admin['email'],
                         'username': admin['username'], 'phone': admin['phone'],
                         'role': 'admin', 'must_change_password': False})
    return accounts

# In-process throttling supplements (not replaces) an edge/shared rate limiter.
_otp_attempts = {}
_otp_lock = threading.Lock()
def _otp_limit(key, limit, window):
    now = time.monotonic()
    with _otp_lock:
        if len(_otp_attempts) > 10000:
            _otp_attempts.clear()
        history = [t for t in _otp_attempts.get(key, []) if now-t < window]
        if len(history) >= limit:
            raise HTTPException(429, "Too many OTP attempts. Please try again later.")
        history.append(now)
        _otp_attempts[key] = history

@app.post("/api/auth/otp/request")
def request_otp(data: OtpRequest, request: Request):
    email = data.identity.strip().lower()
    if len(email) > 200 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(400, "Enter a valid registered email address")
    ip = request.client.host if request.client else 'unknown'
    _otp_limit('email-request-ip:' + ip, 10, 600)
    _otp_limit('email-request-address:' + hashlib.sha256(email.encode()).hexdigest(), 3, 600)
    accounts = _email_otp_account(email)
    if len(accounts) != 1:
        # Do not reveal whether an address is registered or ambiguous.
        return {'status': 'accepted', 'message': 'If the account is eligible, a verification code will be sent.'}
    account = accounts[0]
    if account['role'] != 'customer':
        # Email OTP is a second factor for privileged accounts, never passwordless admin login.
        if not data.password:
            raise HTTPException(400, "Password is required for privileged accounts")
        correct = (verify_password(data.password, get_admin_password_hash()) if account['id'] == 'admin'
                   else verify_password(data.password, account['password_hash']))
        if not correct:
            raise HTTPException(401, "Invalid credentials")
    code = f"{secrets.randbelow(1000000):06d}"
    try:
        _deliver_otp(email, code)
    except HTTPException:
        raise
    except Exception:
        log.exception('Email OTP delivery failed')
        raise HTTPException(502, "Email delivery failed. Check SMTP configuration")
    now = int(time.time())
    create_login_otp('otp_' + uuid.uuid4().hex[:16], email, account['id'], email,
                     account.get('phone') or '', _otp_hash(email, code), now,
                     now + min(settings.otp_expiry_seconds, 300))
    return {'status': 'sent', 'message': 'If the account is eligible, a verification code will be sent.'}

@app.post("/api/auth/otp/verify")
def verify_otp_login(data: OtpVerify, request: Request):
    email = data.identity.strip().lower()
    ip = request.client.host if request.client else 'unknown'
    _otp_limit('email-verify-ip:' + ip, 30, 600)
    _otp_limit('email-verify-address:' + hashlib.sha256(email.encode()).hexdigest(), 6, 600)
    row = consume_login_otp(email, _otp_hash(email, data.code), int(time.time()))
    if not row:
        raise HTTPException(401, "Invalid or expired OTP")
    accounts = _email_otp_account(email)
    if len(accounts) != 1 or accounts[0]['id'] != row['user_id']:
        raise HTTPException(401, "Account information changed. Request a new OTP")
    account = accounts[0]
    token = create_token(account['id'], account['email'], role=account['role'])
    log_auth_event(f"log_{uuid.uuid4().hex[:16]}", int(time.time()), 'email_otp_login_success', True,
                   account['id'], email, ip, request.headers.get('user-agent', '')[:500],
                   'email OTP verified; privileged login required password at request')
    return {'token': token, 'user': {k: account.get(k) for k in
            ('id', 'name', 'email', 'username', 'phone', 'role', 'must_change_password')}}

@app.post("/api/auth/logout")
def logout(request: Request):
    header = request.headers.get("Authorization", "")
    token_data = decode_token(header[7:]) if header.startswith("Bearer ") else None
    user = current_user(request)
    if token_data:
        revoke_session(token_data)
    if user:
        log_auth_event(f"log_{uuid.uuid4().hex[:16]}", int(time.time()), "logout", True, user["id"], user["email"],
                       request.client.host if request.client else "", request.headers.get("user-agent", "")[:500], "explicit logout")
    return {"status": "logged_out"}

def current_user(request: Request):
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    data = decode_token(header[7:])
    if not data:
        raise HTTPException(401, "Invalid or expired login token")
    if not touch_session(data, request.client.host if request.client else "", request.headers.get("user-agent", "")[:500]):
        raise HTTPException(401, "Session expired after 4 hours of inactivity. Please sign in again.")
    if data.get("sub")=="admin" and data.get("role")=="admin":
        ap=get_admin_profile(); return {"id":"admin","name":ap["name"],"email":ap["email"],"username":ap["username"],"phone":ap["phone"],"role":"admin","must_change_password":0,"created_at":0}
    return find_user(data["sub"])

@app.get("/api/auth/me")
def me(user=Depends(current_user)):
    if not user:
        raise HTTPException(401, "Login required")
    return {"id":user["id"],"name":user["name"],"email":user["email"],"username":user["username"],"phone":user["phone"],"role":user["role"],"must_change_password":bool(user["must_change_password"])}

@app.post("/api/auth/password")
def change_password(data: PasswordChange, request: Request):
    user = current_user(request)
    if user and user['id'] == 'admin':
        if not verify_password(data.current_password, get_admin_password_hash()):
            raise HTTPException(401, 'Current password is incorrect')
        save_admin_password(hash_password(data.new_password))
        return {"status": "password_updated"}
    stored = find_user_by_email(user['email']) if user else None
    if not stored or not verify_password(data.current_password, stored['password_hash']):
        raise HTTPException(401, 'Current password is incorrect')
    update_user_password(user['id'], hash_password(data.new_password))
    return {"status": "password_updated"}

@app.post("/api/admin/password", tags=["Admin"])
def change_admin_password(data: PasswordChange, admin: dict = Depends(administrator_only)):
    if admin.get('sub') == 'admin':
        if not verify_password(data.current_password, get_admin_password_hash()):
            raise HTTPException(401, 'Current password is incorrect')
        save_admin_password(hash_password(data.new_password))
        return {"status": "password_updated"}
    user = find_user(admin['sub'])
    if not user or not verify_password(data.current_password, find_user_by_email(user['email'])['password_hash']):
        raise HTTPException(401, 'Current password is incorrect')
    update_user_password(user['id'], hash_password(data.new_password))
    return {"status": "password_updated"}

def _razorpay_order(total, receipt, payment_settings):
    # Razorpay always sends the customer to the hosted checkout page in a new tab
    # rather than the embedded SDK, so no live order needs to be created via the API.
    return {
        "provider": "razorpay_redirect",
        "id": f"mock_{receipt}",
        "amount": int(total * 100),
        "currency": "INR",
        "receipt": receipt,
        "redirect_url": payment_settings['razorpay_checkout_url'],
    }

@app.get("/api/payments/gateways/health")
def payment_gateways_health():
    cf = cashfree.health_check()
    razorpay_ready = bool(settings.razorpay_key_id and settings.razorpay_key_secret)
    return {"checked_at": int(time.time()), "gateways": {
        "cashfree": {**cf, "name": "Cashfree Payment Gateway", "primary": True},
        "razorpay": {"status": "online" if razorpay_ready else "test_mode", "configured": razorpay_ready,
                     "name": "Razorpay", "primary": False,
                     "message": "Razorpay is configured and ready as backup." if razorpay_ready else "Razorpay credentials are not configured; test/mock mode only."}
    }}

@app.get("/api/payments/cashfree/health")
def cashfree_health():
    return cashfree.health_check()

@app.post("/api/checkout")
def checkout(order: Checkout, request: Request):
    # Basket/delivery details stay visible to guests, but payment requires a signed-in account.
    user = current_user(request)
    if not user:
        raise HTTPException(401, "Please sign in to your account to complete payment.")
    from datetime import datetime
    from zoneinfo import ZoneInfo
    try:
        requested_delivery_date = datetime.strptime(order.delivery_date, '%Y-%m-%d').date()
    except ValueError:
        raise HTTPException(400, 'Invalid delivery date.')
    if requested_delivery_date < datetime.now(ZoneInfo('Asia/Kolkata')).date():
        raise HTTPException(400, 'Delivery date cannot be in the past.')
    products = [row_product(row) for row in list_catalog()]
    by_id = {product.id: product for product in products}
    total = 0
    lines = []
    for item in order.items:
        p = by_id.get(item.product_id)
        if not p or not p.active:
            raise HTTPException(400, f"Invalid product: {item.product_id}")
        if getattr(p, 'status', 'live') != 'live':
            raise HTTPException(400, f"Product is not available for purchase: {item.product_id}")
        total += round(p.price * item.quantity, 2)
        lines.append({"id":p.id,"name":p.name,"qty":item.quantity,"unit_price":p.price})
    coupon = None
    if order.coupon_code.strip():
        coupon = _coupon_quote(order.coupon_code, [(by_id[item.product_id], item.quantity) for item in order.items])
        if not coupon['valid']:
            raise HTTPException(400, coupon['message'])
        # Hosted Razorpay payment pages cannot enforce this server-calculated amount.
        # Never advertise a discount that the gateway cannot collect accurately.
        if order.payment_method == 'razorpay':
            raise HTTPException(409, 'Coupon checkout requires an amount-aware payment gateway. Select Cashfree.')
        if get_payment_settings()['provider'] != 'cashfree':
            raise HTTPException(409, 'Coupon checkout requires Cashfree; the configured gateway cannot enforce coupon totals.')
        total = round(total - coupon['discount'], 2)
    receipt = f"ifm_{int(time.time())}_{uuid.uuid4().hex[:10]}"
    payment_settings = get_payment_settings()
    order_id = f"ord_{uuid.uuid4().hex[:16]}"
    user_id = user["id"]
    # Persist the local order before contacting a gateway. This gives retries/fallbacks a stable internal identity.
    create_order(order_id, user_id, None, total, "INR", "created", json.dumps(lines), int(time.time()),
                 order.customer_name, order.phone, order.pincode, order.address, order.delivery_date, order.delivery_slot)
    amount_paise = int(round(total * 100))
    if payment_settings['provider'] == 'upi':
        from urllib.parse import quote
        upi_uri = f"upi://pay?pa={payment_settings['upi_id']}&pn={payment_settings['upi_name']}&am={total:.2f}&cu=INR"
        payment_order = {"provider":"upi","id":f"upi_{receipt}","amount":amount_paise,"currency":"INR",
                         "upi_id":payment_settings['upi_id'],"upi_name":payment_settings['upi_name'],"upi_uri":upi_uri,
                         "qr_code_url":"https://api.qrserver.com/v1/create-qr-code/?size=260x260&data="+quote(upi_uri),
                         "redirect_url":payment_settings['upi_redirect_url']}
    elif payment_settings['provider'] == 'cashfree':
        if order.payment_method == 'razorpay':
            payment_order = _razorpay_order(total, receipt, payment_settings)
            payment_order['gateway_choice'] = 'customer_selected_razorpay'
        else:
            cf_health = cashfree.health_check(force=True)
            return_url = settings.cashfree_return_url or str(request.base_url).rstrip('/') + '/payment/cashfree/return?order_id={order_id}'
            notify_url = settings.cashfree_notify_url or str(request.base_url).rstrip('/') + '/api/payments/cashfree/webhook'
            payment_order = cashfree.create_order(order_id=order_id, amount_paise=amount_paise, customer_id=user_id,
                customer_phone=order.phone, customer_email=order.email, return_url=return_url, notify_url=notify_url)
            if coupon and (cf_health['status'] != 'online' or payment_order['provider'] == 'cashfree_unavailable'):
                raise HTTPException(503, 'Coupon checkout is unavailable until Cashfree is online. No fallback payment has been initiated; an unpaid order may exist.')
            if cf_health['status'] != 'online' or payment_order['provider'] == 'cashfree_unavailable':
                fallback = _razorpay_order(total, receipt, payment_settings)
                fallback['gateway_failover'] = 'cashfree_unavailable'
                payment_order = fallback
    else:
        payment_order = _razorpay_order(total, receipt, payment_settings)
    set_order_gateway_reference(order_id, payment_order.get('id'))
    if payment_order['provider'] in ('cashfree','razorpay','razorpay_redirect'):
        create_payment_transaction('ptx_'+uuid.uuid4().hex[:20], order_id, 'cashfree' if payment_order['provider']=='cashfree' else 'razorpay',
            payment_order.get('id',''), amount_paise, payment_session_id=payment_order.get('payment_session_id',''),
            environment=payment_order.get('environment', settings.environment), idempotency_key=receipt)
    log.info("checkout_created order=%s total=%.2f item_count=%d payment_provider=%s", order_id, total, len(lines), payment_order["provider"])
    return {"order_id":order_id,"amount":total,"currency":"INR","items":lines,"coupon":coupon,"payment":payment_order}

@app.post("/api/payments/verify")
def verify_payment(data: PaymentVerify):
    order = get_order(data.order_id)
    if not order or order["razorpay_order_id"] != data.razorpay_order_id:
        raise HTTPException(404, "Order not found")
    if not payment.verify_signature(data.razorpay_order_id, data.razorpay_payment_id, data.razorpay_signature):
        set_order_status(data.order_id, "payment_verification_failed")
        raise HTTPException(400, "Payment signature verification failed")
    add_payment(data.razorpay_payment_id, data.order_id, data.razorpay_signature, "verified", int(time.time()))
    set_order_status(data.order_id, "paid")
    dispatch.assign(data.order_id, order["pincode"])
    return {"status":"paid", "order_id":data.order_id, "payment_id":data.razorpay_payment_id}

@app.post("/api/payments/cashfree/webhook")
async def cashfree_webhook(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("x-webhook-signature", "")
    timestamp = request.headers.get("x-webhook-timestamp", "")
    if not cashfree.verify_webhook_signature(raw_body, timestamp, signature):
        raise HTTPException(401, "Invalid webhook signature")
    payload=json.loads(raw_body)
    data=payload.get('data') or {}
    order_data=data.get('order') or {}
    payment_data=data.get('payment') or {}
    provider_order_id=str(order_data.get('order_id') or '')
    tx=get_payment_transaction_by_provider_order('cashfree', provider_order_id)
    if not tx: raise HTTPException(404, "Payment transaction not found")
    status=str(payment_data.get('payment_status') or '').upper()
    payment_id=str(payment_data.get('cf_payment_id') or '')
    if status == 'SUCCESS':
        update_payment_transaction(tx['id'], status='verified', provider_payment_id=payment_id, gateway_status=status, verified=True)
        order=get_order(tx['order_id'])
        if order and order['status'] != 'paid':
            set_order_status(order['id'], 'paid'); dispatch.assign(order['id'], order['pincode'])
    elif status == 'PENDING':
        update_payment_transaction(tx['id'], status='pending', provider_payment_id=payment_id, gateway_status=status)
    else:
        update_payment_transaction(tx['id'], status='failed', provider_payment_id=payment_id, gateway_status=status)
    return {"status":"acknowledged"}

@app.get("/api/payments/cashfree/reconcile/{order_id}")
def reconcile_cashfree_order(order_id: str, request: Request):
    order=get_order(order_id)
    if not order: raise HTTPException(404, "Order not found")
    user=current_user(request)
    if not user or (user.get('role') not in ('admin','manager') and order['user_id'] != user['id']): raise HTTPException(403, "Forbidden")
    result=cashfree.authoritative_status(order_id)
    tx=get_payment_transaction_by_provider_order('cashfree', order_id)
    if result['status']=='paid':
        if tx: update_payment_transaction(tx['id'],status='verified',gateway_status='SUCCESS',verified=True)
        if order['status']!='paid': set_order_status(order_id,'paid'); dispatch.assign(order_id,order['pincode'])
    elif result['status']=='failed' and tx: update_payment_transaction(tx['id'],status='failed',gateway_status='FAILED')
    return {"order_id":order_id,"status":result['status']}

@app.get("/payment/cashfree/return", response_class=HTMLResponse)
def cashfree_return(order_id: str):
    # Browser return is informational only; authoritative confirmation remains server-side.
    return HTMLResponse(f"<html><body><h2>Payment received for verification</h2><p>Order {html.escape(order_id)} is being verified. You may return to the store.</p><a href='/'>Return to store</a></body></html>")

@app.get("/api/admin/payment-testing", tags=["Admin"])
def admin_payment_testing(_: dict = Depends(administrator_only)):
    return {"cashfree":cashfree.health_check(),"transactions":[dict(x) for x in list_payment_transactions(100, is_test=True)]}

@app.post("/api/admin/payment-testing/cashfree/one-rupee", tags=["Admin"])
def admin_cashfree_one_rupee_test(data: PaymentTestRequest, request: Request, admin: dict = Depends(administrator_only)):
    environment=cashfree.environment
    if environment == 'production' and not data.confirm_live:
        raise HTTPException(400, "LIVE ₹1 Cashfree test requires explicit production confirmation")
    if not cashfree.is_configured():
        raise HTTPException(503, f"Cashfree {environment} credentials are not configured")
    test_order_id=('live_test_' if environment=='production' else 'test_')+uuid.uuid4().hex[:18]
    label='LIVE ₹1 payment test' if environment=='production' else 'Sandbox ₹1 payment test'
    create_order(test_order_id, None, None, 1.00, 'INR', 'test_created', '[]', int(time.time()), 'Payment Test','9999999999','000000',label,'','')
    result=cashfree.create_order(order_id=test_order_id,amount_paise=100,customer_id='ifm_payment_test',customer_phone='9999999999',
        return_url=(settings.cashfree_return_url or str(request.base_url).rstrip('/')+'/payment/cashfree/return?order_id={order_id}'),
        notify_url=(settings.cashfree_notify_url or str(request.base_url).rstrip('/')+'/api/payments/cashfree/webhook'))
    if result['provider']!='cashfree': raise HTTPException(503, f"Cashfree {environment} is unavailable")
    set_order_gateway_reference(test_order_id,result['id'])
    create_payment_transaction('ptx_'+uuid.uuid4().hex[:20],test_order_id,'cashfree',result['id'],100,payment_session_id=result.get('payment_session_id',''),environment=environment,idempotency_key=test_order_id,is_test=True)
    log.info('cashfree_one_rupee_test_created environment=%s order=%s admin=%s', environment, test_order_id, admin.get('sub') or admin.get('id') or 'admin')
    return {"order_id":test_order_id,"amount":1.00,"currency":"INR","environment":environment,"live_money":environment=='production',"payment":{k:v for k,v in result.items() if k!='gateway_response'}}

@app.get("/api/orders/{order_id}")
def order_status(order_id: str, request: Request):
    order = get_order(order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    user = current_user(request)
    if order["user_id"] and (not user or user["id"] != order["user_id"]):
        admin_required(request)
    result = dict(order)
    delivery = get_delivery(order_id)
    result["delivery"] = dict(delivery) if delivery else None
    return result

@app.post("/api/admin/alert-test", tags=["Admin"])
def alert_test():
    ok = alerts.send("manual_test", {"service": settings.app_name})
    return {"delivered":ok}

def require_login(request: Request):
    user = current_user(request)
    if not user:
        raise HTTPException(401, "Login required")
    return user

def _order_view(order):
    result = dict(order)
    delivery = get_delivery(order["id"])
    result["delivery"] = dict(delivery) if delivery else None
    payment_row = get_payment_for_order(order["id"])
    result["payment"] = dict(payment_row) if payment_row else None
    return result

@app.put("/api/account/details")
def account_update_details(data: AccountDetailsUpdate, user=Depends(require_login)):
    if user["id"] == "admin": raise HTTPException(400,"Administrator details are managed in administration")
    other=find_user_by_login(data.email)
    if other and other["id"] != user["id"]: raise HTTPException(409,"Email already in use")
    if data.username:
        other=find_user_by_login(data.username)
        if other and other["id"] != user["id"]: raise HTTPException(409,"Username already in use")
    update_user_details(user["id"],data.name,data.email,data.username,data.phone)
    return dict(find_user(user["id"]))

@app.get("/api/account/profile")
def account_profile(user=Depends(require_login)):
    profile={} if user["id"]=="admin" else dict(get_customer_profile(user["id"]))
    return {"user":dict(user),"profile":profile,"bank_details_editable":user["id"]!="admin"}

@app.put("/api/account/address")
def account_address(data: AddressUpdate, user=Depends(require_login)):
    if user["id"]=="admin": raise HTTPException(400,"Administrator does not use a customer address")
    return dict(update_customer_profile(user["id"],data.model_dump(),admin=False))

@app.put("/api/account/bank")
def account_bank(data: BankDetailsUpdate, user=Depends(require_login)):
    if user["id"]=="admin": raise HTTPException(400,"Administrator does not use customer bank details")
    return dict(update_customer_profile(user["id"],data.model_dump(),admin=True))

@app.get("/api/admin/sessions", tags=["Admin"])
def admin_sessions(_:dict=Depends(administrator_only)):
    return {"items":[dict(x) for x in list_auth_sessions()]}

@app.delete("/api/admin/sessions/{session_id}", tags=["Admin"])
def admin_session_revoke(session_id:str,_:dict=Depends(administrator_only)):
    admin_revoke_auth_session(session_id); return {"status":"revoked"}

@app.put("/api/admin/users/{user_id}/profile", tags=["Admin"])
def admin_user_profile_update(user_id:str,data:AdminCustomerProfileUpdate,_:dict=Depends(administrator_only)):
    if not find_user(user_id): raise HTTPException(404,"User not found")
    update_user_details(user_id,data.name,data.email,data.username,data.phone)
    update_customer_profile(user_id,data.model_dump(),admin=True)
    return {"user":dict(find_user(user_id)),"profile":dict(get_customer_profile(user_id))}

@app.get("/api/account/summary")
def account_summary(user=Depends(require_login)):
    orders = list_orders_for_user(user["id"])
    paid = [o for o in orders if o["status"] == "paid"]
    return {"id": user["id"], "name": user["name"], "email": user["email"], "phone": user["phone"],
            "role": user["role"], "member_since": user["created_at"], "order_count": len(orders),
            "paid_order_count": len(paid), "lifetime_value": round(sum(o["amount"] for o in paid), 2)}

@app.get("/api/account/orders")
def account_orders(user=Depends(require_login)):
    return {"items": [_order_view(o) for o in list_orders_for_user(user["id"])]}

@app.get("/api/account/orders/{order_id}")
def account_order_detail(order_id: str, user=Depends(require_login)):
    order = get_order(order_id)
    if not order or order["user_id"] != user["id"]:
        raise HTTPException(404, "Order not found")
    return _order_view(order)

@app.post("/api/account/feedback")
def account_feedback_create(data: FeedbackIn, user=Depends(require_login)):
    if data.order_id:
        order = get_order(data.order_id)
        if not order or order["user_id"] != user["id"]:
            raise HTTPException(404, "Order not found")
    feedback_id = f"fb_{uuid.uuid4().hex[:16]}"
    create_feedback(feedback_id, user["id"], data.order_id, data.subject, data.message, data.rating, int(time.time()))
    return {"id": feedback_id, "status": "received"}

@app.get("/api/account/feedback")
def account_feedback_list(user=Depends(require_login)):
    return {"items": [dict(f) for f in list_feedback_for_user(user["id"])]}

@app.get("/api/account/auth-history")
def account_auth_history(user=Depends(require_login)):
    return {"items": [dict(row) for row in list_auth_logs(user_id=user["id"], limit=100)]}

@app.get("/api/admin/users/{user_id}", tags=["Admin"])
def admin_user_detail(user_id: str, _: dict = Depends(administrator_only)):
    user = find_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    orders = list_orders_for_user(user_id)
    result = dict(user)
    result["order_count"] = len(orders)
    result["orders"] = [_order_view(o) for o in orders]
    result["feedback"] = [dict(f) for f in list_feedback_for_user(user_id)]
    result["profile"] = dict(get_customer_profile(user_id))
    return result

@app.get("/api/admin/orders", tags=["Admin"])
def admin_orders(status: str = "", _: dict = Depends(admin_required)):
    return {"items": [_order_view(o) for o in list_orders(status or None)]}

@app.get("/api/admin/orders/{order_id}", tags=["Admin"])
def admin_order_detail(order_id: str, _: dict = Depends(admin_required)):
    order = get_order(order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    return _order_view(order)

@app.put("/api/admin/orders/{order_id}/status", tags=["Admin"])
def admin_update_order_status(order_id: str, data: OrderStatusUpdate, _: dict = Depends(administrator_only)):
    order = get_order(order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    set_order_status(order_id, data.status)
    if data.status == "paid" and not get_delivery(order_id):
        dispatch.assign(order_id, order["pincode"])
    return _order_view(get_order(order_id))

@app.put("/api/admin/orders/{order_id}/delivery", tags=["Admin"])
def admin_update_delivery_status(order_id: str, data: DeliveryStatusUpdate, _: dict = Depends(administrator_only)):
    if not get_delivery(order_id):
        raise HTTPException(404, "Delivery not assigned for this order yet")
    dispatch.update_status(order_id, data.status, data.tracking_number)
    return dict(get_delivery(order_id))

@app.get("/api/admin/feedback", tags=["Admin"])
def admin_feedback_list(status: str = "", _: dict = Depends(admin_required)):
    return {"items": [dict(f) for f in list_feedback(status or None)]}

@app.put("/api/admin/feedback/{feedback_id}", tags=["Admin"])
def admin_feedback_update(feedback_id: str, data: FeedbackStatusUpdate, _: dict = Depends(admin_required)):
    if not update_feedback_status(feedback_id, data.status, data.response):
        raise HTTPException(404, "Feedback not found")
    return {"status": "updated"}

@app.get("/api/admin/auth-logs", tags=["Admin"])
def admin_auth_logs(user_id: str = "", start_at: int | None = None, end_at: int | None = None, _: dict = Depends(administrator_only)):
    return {"items": [dict(row) for row in list_auth_logs(user_id=user_id or None, start_at=start_at, end_at=end_at)]}

@app.get("/api/admin/auth-logs/archive", tags=["Admin"])
def admin_auth_logs_archive(user_id: str = "", start_at: int | None = None, end_at: int | None = None, _: dict = Depends(administrator_only)):
    # Session/auth/sign-in-out events land here 1 year after they occur and are kept for
    # up to 4 years total before automatic purge — see app/config.py auth_log_*_days.
    return {"items": [dict(row) for row in list_archived_auth_logs(user_id=user_id or None, start_at=start_at, end_at=end_at)]}

@app.post("/api/admin/auth-logs/cleanup", tags=["Admin"])
def admin_auth_logs_cleanup(data: AuthLogCleanupFilter, _: dict = Depends(administrator_only)):
    # Lets admins purge session/auth history ahead of the automatic 1-year/4-year
    # schedule, scoped by a custom date range or a weekly/monthly/yearly preset window.
    now = int(time.time())
    presets = {"weekly": 7, "monthly": 30, "yearly": 365}
    if data.mode == "custom":
        start_at, end_at = data.start_at, data.end_at
    else:
        # Presets are intentionally "older than" filters, matching the admin UI.
        # This avoids accidentally leaving records just outside a 7/30/365-day window.
        start_at = data.start_at
        end_at = data.end_at if data.end_at is not None else now - presets[data.mode] * 86400
    if start_at is None and end_at is None:
        raise HTTPException(400, "Provide start_at/end_at for a custom cleanup range")
    deleted = delete_auth_logs_by_filter(data.target, start_at, end_at)
    return {"status": "cleaned", "deleted": deleted, "start_at": start_at, "end_at": end_at}

@app.get("/", include_in_schema=False)
def index():
    # Phase 3: inject only the currently published page/site SEO into the
    # server response. The storefront remains otherwise unchanged.
    source=(BASE / "static" / "index.html").read_text(encoding="utf-8").replace("{{BRAND_NAME}}", settings.app_name)
    seo=public_seo("page","/") or public_seo("site","global")
    head=seo_head_tags(seo=seo,fallback_title=f"{settings.app_name} | Your everyday basket, delivered",fallback_description="Shop Indian family favourites and everyday essentials.",canonical_path="/")
    # Replace the legacy title and insert the complete crawlable head block.
    source=__import__('re').sub(r'<title>.*?</title>',head,source,count=1,flags=__import__('re').I|__import__('re').S)
    return HTMLResponse(source)

@app.get("/catalog/browse", include_in_schema=False)
def browse_catalog_page():
    """Dedicated mobile-first catalog browsing page using the existing storefront and API."""
    source=(BASE / "static" / "index.html").read_text(encoding="utf-8").replace("{{BRAND_NAME}}", settings.app_name)
    return HTMLResponse(source.replace('<title>', '<title>Explore All Categories | ', 1))

@app.get("/products/{product_id}", include_in_schema=False)
def seo_product_page(product_id: str):
    row=catalog_product(product_id)
    if not row or not row["active"]: raise HTTPException(404,"Product not found")
    p=row_product(row); path=seo_product_path(p.id)
    seo=public_seo("product",p.id)
    title=f"{p.name} | {settings.app_name}"
    desc=p.description or f"Shop {p.name} from {settings.app_name}."
    head=seo_head_tags(seo=seo,fallback_title=title,fallback_description=desc,canonical_path=path,image=p.image)
    import json as _json
    from urllib.parse import urljoin as _urljoin
    esc=lambda value: html.escape(str(value or ''),quote=True)
    status=str(getattr(p,'status','live') or 'live').lower()
    available=status=='live'
    absolute_image=_urljoin(seo_base_url()+'/',p.image) if p.image else ''
    structured={"@context":"https://schema.org","@type":"Product","name":p.name,"description":desc,"sku":p.id,"category":p.category,"url":seo_base_url()+path,"offers":{"@type":"Offer","priceCurrency":"INR","price":round(float(p.price),2),"availability":"https://schema.org/InStock" if available else "https://schema.org/OutOfStock","url":seo_base_url()+path}}
    gallery_images=_catalog_gallery.get_gallery(p.id,public=True)['images']
    gallery_urls=[_urljoin(seo_base_url()+'/',x['url']) for x in gallery_images]
    if gallery_urls: structured['image']=gallery_urls
    elif absolute_image: structured['image']=[absolute_image]
    if not seo or not seo.get('structured_data_json'):
        head+='\n<script type="application/ld+json">'+_json.dumps(structured,ensure_ascii=False).replace('</','<\\/')+'</script>'
    image_html=(f'<img id="galleryHero" class="product-image" src="{esc(gallery_images[0]["url"])}" alt="{esc(p.name)}" loading="eager">' + '<div class="gallery-thumbs">'+''.join(f'<button type="button" onclick="document.getElementById(&quot;galleryHero&quot;).src=this.querySelector(&quot;img&quot;).src"><img src="{esc(x["url"])}" alt="Product image {i+1}"></button>' for i,x in enumerate(gallery_images))+'</div>') if gallery_images else ''
    body=(f'<div class="product-layout">{image_html}<div><p class="category">{esc(p.category)} · {esc(p.state)}</p>'
          f'<p>{esc(desc)}</p><p><strong>Pack / unit:</strong> {esc(p.unit)}</p>'
          f'<p class="price">₹{float(p.price):,.2f}</p><p>{"Available" if available else "Currently unavailable"}</p>'
          f'<p><a class="shop-link" href="/catalog/browse">Browse catalog and add to basket</a></p></div></div>'
          f'<p><a href="{esc(seo_category_path(p.category))}">More in {esc(p.category)}</a></p>')
    css="""<style>.gallery-thumbs{display:flex;gap:8px;overflow-x:auto;margin:12px 0}.gallery-thumbs button{border:1px solid #d5dfd0;background:white;border-radius:7px;padding:4px;cursor:pointer;flex:0 0 75px}.gallery-thumbs img{width:65px;height:65px;object-fit:contain}body{font-family:system-ui,sans-serif;background:#fff9eb;color:#173e25;margin:0}main{max-width:1050px;margin:auto;padding:20px 16px 80px}h1{font-size:clamp(26px,4vw,42px)}.product-layout{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:25px;align-items:start}.product-image{width:100%;max-height:440px;object-fit:contain;background:white;border-radius:14px}.category{font-weight:600}.price{font-size:26px;font-weight:700}.shop-link{display:inline-block;padding:13px 17px;background:#173e25;color:white;border-radius:7px;text-decoration:none}@media(max-width:680px){.product-layout{grid-template-columns:1fr}}</style>"""
    return HTMLResponse(seo_page_html(heading=p.name,body=body,head=head+css))

@app.get("/category/{slug}", include_in_schema=False)
def seo_category_page(slug: str):
    rows=[row_product(r) for r in list_catalog()]
    cats=sorted({p.category for p in rows})
    category=next((c for c in cats if seo_slugify(c)==slug.lower()),None)
    if not category: raise HTTPException(404,"Category not found")
    items=[p for p in rows if p.category==category]
    seo=public_seo("category",category,slug)
    path=seo_category_path(category)
    title=f"{category} | {settings.app_name}"; desc=f"Shop {category} from {settings.app_name}."
    head=seo_head_tags(seo=seo,fallback_title=title,fallback_description=desc,canonical_path=path)
    links=''.join(f'<li><a href="{seo_product_path(p.id)}">{html.escape(p.name)}</a></li>' for p in items)
    return HTMLResponse(seo_page_html(heading=category,body=f'<p>{html.escape(desc)}</p><ul>{links}</ul>',head=head))

@app.get("/robots.txt", include_in_schema=False)
def robots_txt():
    # Keep admin/API surfaces out of crawl discovery. Public product/category
    # pages remain crawlable and the sitemap origin is configuration-owned.
    text=f"User-agent: *\nDisallow: /admin\nDisallow: /api/\nSitemap: {seo_base_url()}/sitemap.xml\n"
    return PlainTextResponse(text)

@app.get("/sitemap.xml", include_in_schema=False)
def sitemap_xml():
    from xml.sax.saxutils import escape as xml_escape
    urls=[seo_base_url()+"/"]
    products=[row_product(r) for r in list_catalog()]
    urls += [seo_base_url()+seo_product_path(p.id) for p in products]
    urls += [seo_base_url()+seo_category_path(c) for c in sorted({p.category for p in products})]
    body=''.join(f'<url><loc>{xml_escape(u)}</loc></url>' for u in urls)
    return Response(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>',media_type='application/xml')

@app.get("/admin", include_in_schema=False)
def admin_page():
    return branded_page("admin.html")

@app.get("/travel", include_in_schema=False)
def travel_page():
    if _MARKET_EXTENDED_MODE == "redirect":
        return _SpinoutRedirect(_COMMUNITY_BASE_URL + "/travel", status_code=307)
    return branded_page("travel.html")

@app.get("/sports", include_in_schema=False)
def sports_page():
    if _MARKET_EXTENDED_MODE == "redirect":
        return _SpinoutRedirect(_COMMUNITY_BASE_URL + "/community", status_code=307)
    return branded_page("sports.html")

@app.get("/scorer", include_in_schema=False)
def scorer_page():
    if _MARKET_EXTENDED_MODE == "redirect":
        return _SpinoutRedirect(_COMMUNITY_BASE_URL + "/scorer", status_code=307)
    return FileResponse(BASE / "static" / "scorer.html")

@app.get("/api/config")
def public_config():
    # Read-only brand/identity config so any service or external site can
    # stay in sync without hardcoding the business name or parent brand.
    return {"app_name": settings.app_name, "environment": settings.environment,
            "parent_catalog_url": settings.parent_catalog_url}

@app.get("/static/{path:path}", include_in_schema=False)
def static_asset(path: str):
    """Serve files referenced with the legacy /static/... URL prefix.

    Catalog uploads and Scorer media store /static/... paths in the database.
    The generic SPA fallback serves from BASE/static/<path>, so without this
    route /static/uploads/... incorrectly resolves to BASE/static/static/... .
    """
    root = (BASE / "static").resolve()
    file = (root / path).resolve()
    try:
        file.relative_to(root)
    except ValueError:
        raise HTTPException(404, "Static file not found")
    if not file.is_file():
        raise HTTPException(404, "Static file not found")
    return FileResponse(file)

@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    file = BASE / "static" / path
    if file.is_file():
        return FileResponse(file)
    return FileResponse(BASE / "static" / "index.html")
