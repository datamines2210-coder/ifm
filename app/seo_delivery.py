"""Public crawlable SEO delivery helpers (Phase 3).

Only Phase 2 *published* revisions are consumed here. Draft, in-review and
approved-but-unpublished content is intentionally invisible to public output.
"""
from __future__ import annotations
import html, json, re
from urllib.parse import quote
from .config import settings
from .seo_repository import published_for


def slugify(value: str) -> str:
    value=(value or '').strip().lower()
    value=re.sub(r'[^a-z0-9]+','-',value).strip('-')
    return value or 'item'


def base_url() -> str:
    return (getattr(settings,'seo_public_base_url','') or 'https://theindianfamily.shop').rstrip('/')


def published(resource_type: str, resource_key: str, *fallback_keys: str):
    for key in (resource_key,)+fallback_keys:
        if key:
            row=published_for(resource_type,key)
            if row: return row
    return None


def _safe_json_ld(raw: str) -> str:
    if not raw: return ''
    try:
        obj=json.loads(raw)
    except (TypeError,ValueError):
        return ''
    # Prevent a literal closing script sequence from escaping the JSON-LD tag.
    return json.dumps(obj,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')


def head_tags(*, seo=None, fallback_title: str, fallback_description: str='', canonical_path: str='/', image: str='') -> str:
    seo=seo or {}
    title=(seo.get('title') or fallback_title or settings.app_name).strip()
    desc=(seo.get('meta_description') or fallback_description or '').strip()
    canonical=(seo.get('canonical_url') or f"{base_url()}{canonical_path}").strip()
    robots=(seo.get('robots') or 'index,follow').strip()
    og_title=(seo.get('og_title') or title).strip()
    og_desc=(seo.get('og_description') or desc).strip()
    og_image=(seo.get('og_image') or image or '').strip()
    esc=lambda s: html.escape(str(s),quote=True)
    parts=[f'<title>{esc(title)}</title>']
    if desc: parts.append(f'<meta name="description" content="{esc(desc)}">')
    parts += [f'<link rel="canonical" href="{esc(canonical)}">',f'<meta name="robots" content="{esc(robots)}">',
              f'<meta property="og:title" content="{esc(og_title)}">',f'<meta property="og:type" content="website">',
              f'<meta property="og:url" content="{esc(canonical)}">']
    if og_desc: parts.append(f'<meta property="og:description" content="{esc(og_desc)}">')
    if og_image: parts.append(f'<meta property="og:image" content="{esc(og_image)}">')
    structured=_safe_json_ld(seo.get('structured_data_json',''))
    if structured: parts.append(f'<script type="application/ld+json">{structured}</script>')
    return '\n'.join(parts)


def page_html(*, heading: str, body: str, head: str) -> str:
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">{head}</head><body><main><h1>{html.escape(heading)}</h1>{body}</main></body></html>'''


def product_path(product_id: str) -> str:
    return '/products/'+quote(str(product_id),safe='')


def category_path(category: str) -> str:
    return '/category/'+slugify(category)
