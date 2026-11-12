from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'static/index.html').read_text()
ADMIN=(ROOT/'static/admin.html').read_text()
DB=(ROOT/'app/db.py').read_text()
MAIN=(ROOT/'app/main.py').read_text()

def test_mobile_cards_use_flow_layout_not_absolute_actions():
    assert '/* 2026-09-26 mobile-first product card repair */' in HTML
    assert '.card .add-row{position:static!important' in HTML
    assert '.card .meta,.card .parent-link{display:none!important}' in HTML
    assert '@media(max-width:340px){.grid{grid-template-columns:1fr}' in HTML

def test_mobile_cards_reserve_bottom_navigation_space():
    assert 'padding-bottom:calc(88px + env(safe-area-inset-bottom))' in HTML

def test_category_ui_exposes_rename_and_protected_delete():
    assert 'Category name (rename/edit)' in ADMIN
    assert 'no catalog products (Live, Coming Soon or Archived) reference it' in ADMIN
    assert 'new_category:name' in ADMIN

def test_category_delete_protects_all_product_references():
    assert 'SELECT COUNT(*) FROM catalog WHERE category=?"' in DB
    assert 'AND active=1' not in DB[DB.index('def delete_category_settings'):DB.index('def import_catalog_atomic')]
    assert 'Reassign or permanently delete those products' in MAIN

def test_category_rename_prevents_case_insensitive_collision():
    block=DB[DB.index('def rename_category'):DB.index('def delete_category_settings')]
    assert 'lower(category)=lower(?)' in block
    assert 'A different category with that name already exists' in block
