"""Generates docs/Indian_Family_Market_Services_Architecture.pptx.

Run with: python scripts/generate_services_architecture_deck.py
Requires python-pptx (dev-only tool, not a runtime dependency).
"""
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

NAVY = RGBColor(0x0D, 0x2B, 0x4E)
CORAL = RGBColor(0xE6, 0x6F, 0x51)
MUTED = RGBColor(0x5C, 0x6B, 0x80)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

OUT = Path(__file__).resolve().parent.parent / "docs" / "Indian_Family_Market_Services_Architecture.pptx"


def add_title_slide(prs, title, subtitle):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.shapes.add_shape(1, 0, 0, prs.slide_width, prs.slide_height)
    bg.fill.solid(); bg.fill.fore_color.rgb = NAVY; bg.line.fill.background()
    tb = slide.shapes.add_textbox(Inches(0.8), Inches(2.6), Inches(11.7), Inches(1.6))
    tf = tb.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]; p.text = title
    p.font.size = Pt(40); p.font.bold = True; p.font.color.rgb = WHITE
    p2 = tf.add_paragraph(); p2.text = subtitle
    p2.font.size = Pt(18); p2.font.color.rgb = RGBColor(0xC6, 0xEA, 0x6B)
    return slide


def add_content_slide(prs, title, bullets, sub_bullets_ok=True):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bar = slide.shapes.add_shape(1, 0, 0, prs.slide_width, Inches(1.15))
    bar.fill.solid(); bar.fill.fore_color.rgb = NAVY; bar.line.fill.background()
    tb = slide.shapes.add_textbox(Inches(0.6), Inches(0.2), Inches(12), Inches(0.8))
    p = tb.text_frame.paragraphs[0]; p.text = title
    p.font.size = Pt(28); p.font.bold = True; p.font.color.rgb = WHITE

    body = slide.shapes.add_textbox(Inches(0.7), Inches(1.5), Inches(11.9), Inches(5.6))
    tf = body.text_frame; tf.word_wrap = True
    first = True
    for item in bullets:
        level = 0
        text = item
        if isinstance(item, tuple):
            text, level = item
        para = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        para.text = ("• " if level == 0 else "‣ ") + text
        para.level = level
        para.font.size = Pt(20 if level == 0 else 16)
        para.font.color.rgb = NAVY if level == 0 else MUTED
        para.space_after = Pt(10)
    return slide


def build():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    add_title_slide(
        prs,
        "Indian Family Market — Multi-Service Architecture",
        "theindianfamily.shop · configurable brand · independent, plug-and-play services",
    )

    add_content_slide(prs, "Why this architecture", [
        "One production domain, multiple independently-run services",
        "Main storefront brand is fully configurable (merger / acquisition ready)",
        "Extended services (Travel, Sports, Scorer) never depend on each other",
        "Any service can be added, licensed out, or decommissioned without touching the rest",
    ])

    add_content_slide(prs, "Service map", [
        "theindianfamily.shop",
        ("Main storefront — grocery discovery, cart, checkout, payments, accounts", 1),
        ("/travel — static travel services content, zero backend coupling", 1),
        ("/sports — sport communities, gear, events, links to /scorer", 1),
        ("/scorer — full independent app: own DB, own auth, own rankings engine", 1),
    ])

    add_content_slide(prs, "Configurable brand identity", [
        "Business name is a config value, not hardcoded text: APP_NAME",
        "All storefront pages render {{BRAND_NAME}} from settings.app_name at request time",
        "Public GET /api/config exposes app_name, environment, parent_catalog_url",
        "Rebrand or transfer ownership = change env vars + redeploy, no code edits",
    ])

    add_content_slide(prs, "Service independence contract", [
        "No runtime dependency on other services' health",
        "Plug-and-play: self-contained static bundle + optional router per service",
        "Own release & patch process (fixes/, patch/ are scoped per service)",
        "Own dev vs prod data (DATABASE_URL vs SCORER_DB_PATH, isolated test DBs)",
        "Own test suite (test_app.py vs test_scorer.py)",
        "Own user / account / payment management boundary",
        "Packaging ships only the files a service needs (pkg/, release/)",
        "Clean, isolated decommission path",
    ])

    add_content_slide(prs, "Data & environment policy", [
        "Local dev: file-based SQLite per service, created on first run",
        "Automated tests: unique temp database per test run — never touches dev/prod",
        "Production: paths/URLs injected via secrets (DATABASE_URL, SCORER_DB_PATH)",
        "Dev → prod promotion ships code & static assets only, never data files",
        "Prod → dev refresh is a deliberate, one-way, auditable step",
    ])

    add_content_slide(prs, "Adding a new independent service", [
        "1. app/<service>/ — own router, own database module, own auth if needed",
        "2. static/<service>.html — self-contained page, no shared globals",
        "3. Register the route in app/main.py via app.include_router(...)",
        "4. tests/test_<service>.py — independent end-to-end coverage",
        "5. <SERVICE>_DB_PATH env var — its own data store, never the storefront's",
        "6. Package only what this service needs for a release build",
    ])

    add_content_slide(prs, "Decommissioning a service", [
        "Remove its route(s) from app/main.py",
        "Delete its static bundle and any backend module",
        "Archive/delete its data file",
        "Remove its nav link from the storefront",
        "No other service requires any change",
    ])

    add_content_slide(prs, "Business value", [
        "Merger & acquisition ready: rebrand or detach the storefront in minutes",
        "B2B/white-label: license a single service (e.g. Scorer) independently",
        "Resilience: a defect in one service never takes down another",
        "Faster releases: each service ships on its own schedule",
    ])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUT)
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    build()
