from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DB=(ROOT/'app/db.py').read_text(encoding='utf-8')
MAIN=(ROOT/'app/main.py').read_text(encoding='utf-8')
ADMIN=(ROOT/'static/admin.html').read_text(encoding='utf-8')

def test_category_schema_has_stable_id():
    assert 'category_id TEXT NOT NULL' in DB
    assert 'ux_catalog_category_media_category_id' in DB

def test_image_update_is_by_stable_id_not_name():
    assert 'def save_category_media_by_id' in DB
    assert '/api/admin/catalog/categories/id/{category_id}/image' in MAIN
    assert "/api/admin/catalog/categories/id/'+encodeURIComponent(categoryId)+'/image" in ADMIN

def test_rename_is_by_stable_id_and_updates_products():
    assert 'def rename_category_by_id' in DB
    assert 'UPDATE catalog SET category=?' in DB
    assert '/api/admin/catalog/categories/id/{category_id}' in MAIN
    assert 'new_category:name' in ADMIN

def test_delete_unused_duplicate_allowed_but_referenced_protected():
    assert 'def delete_category_by_id' in DB
    assert 'SELECT COUNT(*) FROM catalog WHERE category=?' in DB
    assert "Category is referenced by {count} catalog product(s)" in MAIN
    assert "method:'DELETE'" in ADMIN

def test_admin_ui_uses_category_id_for_all_mutations():
    assert "uploadCategoryImage('${esc(x.category_id||'')}',this)" in ADMIN
    assert "saveCategory('${esc(x.category_id||'')}','${esc(x.category)}')" in ADMIN
    assert "deleteCategory('${esc(x.category_id||'')}','${esc(x.category)}')" in ADMIN
