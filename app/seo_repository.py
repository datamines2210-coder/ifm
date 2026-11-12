"""Market SEO revision and controlled publishing repository (Phase 2)."""
from __future__ import annotations
import json
import time
import uuid
from .db import connect

RESOURCE_TYPES = {"site", "page", "product", "category"}
REVISION_STATES = {"draft", "in_review", "approved", "published", "superseded"}

def _now(): return int(time.time())
def _id(prefix): return f"{prefix}_{uuid.uuid4().hex[:20]}"

def _audit(c, *, document_id="", revision_id="", actor_id="", actor_role="", action, details=""):
    c.execute("INSERT INTO seo_audit_events(id,document_id,revision_id,actor_id,actor_role,action,details,occurred_at) VALUES(?,?,?,?,?,?,?,?)",
              (_id("seoa"),document_id,revision_id,actor_id,actor_role,action,details,_now()))

def validate_structured_data(value: str):
    value=(value or "").strip()
    if not value: return ""
    parsed=json.loads(value)
    if not isinstance(parsed, (dict,list)): raise ValueError("Structured data must be a JSON object or array")
    return json.dumps(parsed, separators=(",",":"), ensure_ascii=False)

def list_documents(resource_type="", resource_key=""):
    sql="SELECT d.*, r.status published_status, r.title published_title, r.meta_description published_meta_description, r.published_at FROM seo_documents d LEFT JOIN seo_revisions r ON r.id=d.published_revision_id WHERE 1=1"
    args=[]
    if resource_type: sql+=" AND d.resource_type=?"; args.append(resource_type)
    if resource_key: sql+=" AND d.resource_key=?"; args.append(resource_key)
    sql+=" ORDER BY d.updated_at DESC,d.resource_type,d.resource_key"
    with connect() as c: return [dict(r) for r in c.execute(sql,args).fetchall()]

def get_document(document_id):
    with connect() as c:
        row=c.execute("SELECT * FROM seo_documents WHERE id=?",(document_id,)).fetchone()
        return dict(row) if row else None

def get_revision(revision_id):
    with connect() as c:
        row=c.execute("SELECT * FROM seo_revisions WHERE id=?",(revision_id,)).fetchone()
        return dict(row) if row else None

def list_revisions(document_id):
    with connect() as c: return [dict(r) for r in c.execute("SELECT * FROM seo_revisions WHERE document_id=? ORDER BY revision_no DESC",(document_id,)).fetchall()]

def create_draft(resource_type, resource_key, payload, actor_id, actor_role):
    if resource_type not in RESOURCE_TYPES: raise ValueError("Unsupported SEO resource type")
    resource_key=(resource_key or "").strip()
    if not resource_key: raise ValueError("SEO resource key is required")
    structured=validate_structured_data(payload.get("structured_data_json", ""))
    now=_now()
    with connect() as c:
        c.execute("BEGIN IMMEDIATE")
        doc=c.execute("SELECT * FROM seo_documents WHERE resource_type=? AND resource_key=?",(resource_type,resource_key)).fetchone()
        if not doc:
            document_id=_id("seod")
            c.execute("INSERT INTO seo_documents(id,resource_type,resource_key,created_at,updated_at) VALUES(?,?,?,?,?)",(document_id,resource_type,resource_key,now,now))
        else: document_id=doc["id"]
        revno=c.execute("SELECT COALESCE(MAX(revision_no),0)+1 FROM seo_revisions WHERE document_id=?",(document_id,)).fetchone()[0]
        revision_id=_id("seor")
        c.execute("""INSERT INTO seo_revisions(id,document_id,revision_no,status,title,meta_description,canonical_url,robots,og_title,og_description,og_image,structured_data_json,notes,created_by,created_at)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (revision_id,document_id,revno,"draft",payload.get("title","").strip(),payload.get("meta_description","").strip(),payload.get("canonical_url","").strip(),payload.get("robots","index,follow"),payload.get("og_title","").strip(),payload.get("og_description","").strip(),payload.get("og_image","").strip(),structured,payload.get("notes","").strip(),actor_id,now))
        c.execute("UPDATE seo_documents SET updated_at=? WHERE id=?",(now,document_id))
        _audit(c,document_id=document_id,revision_id=revision_id,actor_id=actor_id,actor_role=actor_role,action="draft_created",details=f"revision={revno}")
        return dict(c.execute("SELECT * FROM seo_revisions WHERE id=?",(revision_id,)).fetchone())

def submit_review(revision_id, actor_id, actor_role):
    with connect() as c:
        c.execute("BEGIN IMMEDIATE")
        r=c.execute("SELECT * FROM seo_revisions WHERE id=?",(revision_id,)).fetchone()
        if not r: raise KeyError("SEO revision not found")
        if r["status"]!="draft": raise ValueError("Only a draft can be submitted for review")
        c.execute("UPDATE seo_revisions SET status='in_review' WHERE id=?",(revision_id,))
        _audit(c,document_id=r["document_id"],revision_id=revision_id,actor_id=actor_id,actor_role=actor_role,action="submitted_for_review")
        return dict(c.execute("SELECT * FROM seo_revisions WHERE id=?",(revision_id,)).fetchone())

def approve_revision(revision_id, actor_id, actor_role):
    now=_now()
    with connect() as c:
        c.execute("BEGIN IMMEDIATE")
        r=c.execute("SELECT * FROM seo_revisions WHERE id=?",(revision_id,)).fetchone()
        if not r: raise KeyError("SEO revision not found")
        if r["status"]!="in_review": raise ValueError("Only an in-review revision can be approved")
        if r["created_by"]==actor_id and actor_role!="admin": raise ValueError("Author cannot approve their own SEO revision")
        c.execute("UPDATE seo_revisions SET status='approved',reviewed_by=?,reviewed_at=? WHERE id=?",(actor_id,now,revision_id))
        _audit(c,document_id=r["document_id"],revision_id=revision_id,actor_id=actor_id,actor_role=actor_role,action="approved")
        return dict(c.execute("SELECT * FROM seo_revisions WHERE id=?",(revision_id,)).fetchone())

def publish_revision(revision_id, actor_id, actor_role):
    now=_now()
    with connect() as c:
        c.execute("BEGIN IMMEDIATE")
        r=c.execute("SELECT * FROM seo_revisions WHERE id=?",(revision_id,)).fetchone()
        if not r: raise KeyError("SEO revision not found")
        if r["status"]!="approved": raise ValueError("Only an approved SEO revision can be published")
        doc=c.execute("SELECT * FROM seo_documents WHERE id=?",(r["document_id"],)).fetchone()
        previous=doc["published_revision_id"] if doc else None
        if previous:
            c.execute("UPDATE seo_revisions SET status='superseded' WHERE id=? AND status='published'",(previous,))
        c.execute("UPDATE seo_revisions SET status='published',published_by=?,published_at=? WHERE id=?",(actor_id,now,revision_id))
        c.execute("UPDATE seo_documents SET published_revision_id=?,updated_at=? WHERE id=?",(revision_id,now,r["document_id"]))
        _audit(c,document_id=r["document_id"],revision_id=revision_id,actor_id=actor_id,actor_role=actor_role,action="published",details=f"previous={previous or ''}")
        return dict(c.execute("SELECT * FROM seo_revisions WHERE id=?",(revision_id,)).fetchone())

def rollback_to_revision(document_id, target_revision_id, actor_id, actor_role):
    """Create a new draft from historical content; rollback never mutates history in place."""
    with connect() as c:
        r=c.execute("SELECT * FROM seo_revisions WHERE id=? AND document_id=?",(target_revision_id,document_id)).fetchone()
        if not r: raise KeyError("SEO revision not found for document")
        payload={k:r[k] for k in ("title","meta_description","canonical_url","robots","og_title","og_description","og_image","structured_data_json")}
        payload["notes"]=f"Rollback candidate from revision {r['revision_no']}"
    document=get_document(document_id)
    if not document: raise KeyError("SEO document not found")
    return create_draft(document["resource_type"], document["resource_key"], payload, actor_id, actor_role)

def published_for(resource_type, resource_key):
    with connect() as c:
        row=c.execute("""SELECT r.* FROM seo_documents d JOIN seo_revisions r ON r.id=d.published_revision_id
                         WHERE d.resource_type=? AND d.resource_key=? AND r.status='published'""",(resource_type,resource_key)).fetchone()
        return dict(row) if row else None

def list_audit(document_id="", limit=200):
    limit=max(1,min(int(limit),500))
    with connect() as c:
        if document_id:
            rows=c.execute("SELECT * FROM seo_audit_events WHERE document_id=? ORDER BY occurred_at DESC LIMIT ?",(document_id,limit)).fetchall()
        else: rows=c.execute("SELECT * FROM seo_audit_events ORDER BY occurred_at DESC LIMIT ?",(limit,)).fetchall()
        return [dict(r) for r in rows]
