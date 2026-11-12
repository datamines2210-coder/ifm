"""Generate docs/DATABASE_DESIGN_PRESENTATION.pptx from plain slide content.

Builds a minimal, valid Office Open XML (.pptx) package using only the Python
standard library (zipfile + string templates) - no python-pptx or other
third-party package is installed or required.

Usage:
    python scripts/generate_db_design_pptx.py
"""
from __future__ import annotations

import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

OUT_PATH = Path(__file__).resolve().parents[1] / "docs" / "DATABASE_DESIGN_PRESENTATION.pptx"

# Each slide: (title, [bullet lines])
SLIDES: list[tuple[str, list[str]]] = [
    ("Multi-Service MySQL Database Design",
     ["Indian Family Market (Main Project) + Travel, Sports, Scorer",
      "Target hosting: GoDaddy (cPanel MySQL / VPS)",
      "Proposal for future implementation - no changes made yet"]),
    ("Why This Design",
     ["Each service has independent business logic and customer base",
      "Separate folder structure, release, and patching per service today",
      "Goal: same independence at the database layer",
      "Support easy decommission, resale, or merger of any single service"]),
    ("Guiding Principles",
     ["One MySQL database per service - never a shared schema",
      "One least-privilege MySQL user per service, per environment",
      "Structural prod/dev isolation, not just a config flag",
      "Plug-and-play: one dump + one user + one env var to relocate a service",
      "Prod -> Dev refresh is one-way, deliberate, and sanitized",
      "Everything scripted and reproducible (SQL/shell, version-controlled)"]),
    ("GoDaddy Hosting Context",
     ["cPanel MySQL: db/user names auto-prefixed by hosting account",
      "Database = natural isolation unit (own grant table per DB)",
      "Shared plans may cap number of databases/users - plan accordingly",
      "Remote MySQL allow-list acts as network-level control, not a security substitute",
      "VPS/dedicated plan gives root mysqld access for backup/replication tooling"]),
    ("Database-Per-Service Layout",
     ["Main storefront: ifm_market_prod / ifm_market_dev",
      "Travel: ifm_travel_prod / ifm_travel_dev",
      "Sports: ifm_sports_prod / ifm_sports_dev",
      "Scorer: ifm_scorer_prod / ifm_scorer_dev",
      "No cross-service foreign keys, tables, or shared IDs"]),
    ("Users & Least-Privilege Grants",
     ["1 app user per service x environment (8 total for 4 services)",
      "App user: SELECT / INSERT / UPDATE / DELETE only",
      "Separate migration user: adds CREATE / ALTER / DROP / INDEX",
      "Separate read-only reporting user per service (prod) for exports/BI",
      "GRANT scoped to exactly one database - enforced by MySQL, not app code"]),
    ("Connection Configuration",
     ["Each service already reads its DB from one env var (existing pattern)",
      "Storefront: DATABASE_URL, Scorer: SCORER_DATABASE_URL, etc.",
      "Dev vs prod = same code, different env var value only",
      "Secrets in .env / hosting secret store - never committed to git"]),
    ("Environment Safeguards: Prod vs Dev",
     ["Physical separation: distinct databases (ideally distinct MySQL accounts)",
      "Credential separation: dev credentials cannot see any *_prod database",
      "Network separation: remote MySQL allow-list per environment",
      "No auto-sync from dev to prod - migrations are explicit and reviewed",
      "Full backup taken before any risky prod schema change"]),
    ("Prod -> Dev Data Refresh Design",
     ["Direction is strictly one-way: production -> development",
      "1) Export via read-only user (mysqldump --single-transaction)",
      "2) Sanitize: mask PII, replace password hashes, strip payment secrets",
      "3) Import into *_dev using the dev migration user",
      "Manually triggered and logged - never a silent scheduled job",
      "Each service refreshed independently of the others"]),
    ("Backup, Monitoring & Guardrails",
     ["Automated daily backups of every *_prod database, stored off-host",
      "Pre-migration on-demand snapshot before schema changes",
      "Periodic restore drills to prove backups are usable",
      "Per-service connection/slow-query/disk monitoring",
      "Periodic SHOW GRANTS audit to catch privilege drift",
      "Scheduled secret rotation, isolated to one service at a time"]),
    ("Schema Migration Strategy",
     ["Per-service migrations folder, mirrors existing init_db() pattern",
      "Forward-only, additive-first (avoid destructive DROP without review)",
      "Per-database schema_version table tracks applied migrations",
      "Promote one service at a time - never a cross-service migration run"]),
    ("Plug-and-Play, Decommission & Merger",
     ["Decommission: stop routing, backup, then DROP DATABASE + DROP USER",
      "Resell/license one service: hand over one dump + one router folder",
      "Merge with a partner platform: import as a new, distinctly named database",
      "Add a new service: copy this same one-DB / one-user / one-env-var pattern"]),
    ("Provisioning Checklist",
     ["8 databases: {market, travel, sports, scorer} x {prod, dev}",
      "8 least-privilege app users (one per database)",
      "Migration users + read-only reporting users per service",
      "Remote MySQL allow-list per environment",
      "Daily automated backup job for all *_prod databases",
      "sanitize_prod_dump script for the refresh workflow",
      "Secrets stored outside git, per environment"]),
    ("Next Steps",
     ["Review and approve this design before any implementation work",
      "Provision databases/users on GoDaddy, starting with the Main Project",
      "Write per-service migration scripts (SQLite -> MySQL schema parity)",
      "Build the sanitize/export/import refresh scripts",
      "Roll out one service at a time, verifying independence at each step"]),
]

NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
{slide_overrides}
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""

PRESENTATION_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rIdMaster1"/></p:sldMasterIdLst>
<p:sldIdLst>
{slide_ids}
</p:sldIdLst>
<p:sldSz cx="12192000" cy="6858000"/>
<p:notesSz cx="6858000" cy="9144000"/>
</p:presentation>"""

PRESENTATION_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rIdMaster1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>
<Relationship Id="rIdTheme1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>
{slide_rels}
</Relationships>"""

SLIDE_MASTER_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
<p:cSld>
<p:bg><p:bgPr><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>
<p:spTree>
<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
</p:spTree>
</p:cSld>
<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
</p:sldMaster>"""

SLIDE_MASTER_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
</Relationships>"""

SLIDE_LAYOUT_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="title" preserve="1">
<p:cSld name="Title and Content">
<p:spTree>
<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
</p:spTree>
</p:cSld>
<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>"""

SLIDE_LAYOUT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
</Relationships>"""

THEME_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="DBDesignTheme">
<a:themeElements>
<a:clrScheme name="DBDesign">
<a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1>
<a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>
<a:dk2><a:srgbClr val="1F3864"/></a:dk2>
<a:lt2><a:srgbClr val="E8EEF7"/></a:lt2>
<a:accent1><a:srgbClr val="2E5395"/></a:accent1>
<a:accent2><a:srgbClr val="C0504D"/></a:accent2>
<a:accent3><a:srgbClr val="9BBB59"/></a:accent3>
<a:accent4><a:srgbClr val="8064A2"/></a:accent4>
<a:accent5><a:srgbClr val="4BACC6"/></a:accent5>
<a:accent6><a:srgbClr val="F79646"/></a:accent6>
<a:hlink><a:srgbClr val="0563C1"/></a:hlink>
<a:folHlink><a:srgbClr val="954F72"/></a:folHlink>
</a:clrScheme>
<a:fontScheme name="DBDesign">
<a:majorFont><a:latin typeface="Calibri"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont>
<a:minorFont><a:latin typeface="Calibri"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont>
</a:fontScheme>
<a:fmtScheme name="DBDesign">
<a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst>
<a:lnStyleLst><a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln><a:ln w="12700"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln><a:ln w="19050"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst>
<a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>
<a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst>
</a:fmtScheme>
</a:themeElements>
</a:theme>"""

CORE_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<dc:title>Multi-Service MySQL Database Design - GoDaddy Hosting</dc:title>
<dc:creator>Indian Family Market Engineering</dc:creator>
<cp:lastModifiedBy>Indian Family Market Engineering</cp:lastModifiedBy>
</cp:coreProperties>"""

APP_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
<Application>Indian Family Market DB Design Generator</Application>
<Slides>{count}</Slides>
</Properties>"""


def bullet_paragraphs(lines: list[str]) -> str:
    parts = []
    for line in lines:
        parts.append(
            '<a:p><a:pPr marL="285750" indent="-285750"><a:buFont typeface="Arial"/>'
            '<a:buChar char="&#8226;"/></a:pPr><a:r><a:rPr lang="en-US" sz="2400" dirty="0"/>'
            f'<a:t>{escape(line)}</a:t></a:r></a:p>'
        )
    return "".join(parts)


def slide_xml(title: str, lines: list[str]) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
<p:cSld>
<p:spTree>
<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
<p:sp>
<p:nvSpPr><p:cNvPr id="2" name="Title"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr>
<p:spPr>
<a:xfrm><a:off x="609600" y="274638"/><a:ext cx="10972800" cy="914400"/></a:xfrm>
<a:solidFill><a:srgbClr val="1F3864"/></a:solidFill>
</p:spPr>
<p:txBody><a:bodyPr anchor="ctr"/><a:lstStyle/>
<a:p><a:r><a:rPr lang="en-US" sz="3200" b="1" dirty="0"><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill></a:rPr><a:t>{escape(title)}</a:t></a:r></a:p>
</p:txBody>
</p:sp>
<p:sp>
<p:nvSpPr><p:cNvPr id="3" name="Content"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph type="body" idx="1"/></p:nvPr></p:nvSpPr>
<p:spPr>
<a:xfrm><a:off x="609600" y="1371600"/><a:ext cx="10972800" cy="5181600"/></a:xfrm>
</p:spPr>
<p:txBody><a:bodyPr/><a:lstStyle/>
{bullet_paragraphs(lines)}
</p:txBody>
</p:sp>
</p:spTree>
</p:cSld>
<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>"""


SLIDE_RELS_TEMPLATE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
</Relationships>"""


def build_pptx(path: Path) -> None:
    n = len(SLIDES)
    slide_overrides = "\n".join(
        f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(1, n + 1)
    )
    slide_ids = "\n".join(
        f'<p:sldId id="{256 + i}" r:id="rIdSlide{i}"/>' for i in range(1, n + 1)
    )
    slide_rels = "\n".join(
        f'<Relationship Id="rIdSlide{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>'
        for i in range(1, n + 1)
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES.format(slide_overrides=slide_overrides))
        z.writestr("_rels/.rels", ROOT_RELS)
        z.writestr("docProps/core.xml", CORE_XML)
        z.writestr("docProps/app.xml", APP_XML.format(count=n))
        z.writestr("ppt/presentation.xml", PRESENTATION_XML.format(slide_ids=slide_ids))
        z.writestr("ppt/_rels/presentation.xml.rels", PRESENTATION_RELS.format(slide_rels=slide_rels))
        z.writestr("ppt/slideMasters/slideMaster1.xml", SLIDE_MASTER_XML)
        z.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", SLIDE_MASTER_RELS)
        z.writestr("ppt/slideLayouts/slideLayout1.xml", SLIDE_LAYOUT_XML)
        z.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", SLIDE_LAYOUT_RELS)
        z.writestr("ppt/theme/theme1.xml", THEME_XML)
        for i, (title, lines) in enumerate(SLIDES, start=1):
            z.writestr(f"ppt/slides/slide{i}.xml", slide_xml(title, lines))
            z.writestr(f"ppt/slides/_rels/slide{i}.xml.rels", SLIDE_RELS_TEMPLATE)


if __name__ == "__main__":
    build_pptx(OUT_PATH)
    print(f"Wrote {OUT_PATH} ({len(SLIDES)} slides)")
