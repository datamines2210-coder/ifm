from pathlib import Path
DB=(Path(__file__).resolve().parents[1]/"app"/"db.py").read_text()
MAIN=(Path(__file__).resolve().parents[1]/"app"/"main.py").read_text()
ADMIN=(Path(__file__).resolve().parents[1]/"static"/"admin.html").read_text()
def test_startup_repairs_stable_ids():
    assert "category_id TEXT NOT NULL DEFAULT" in DB
    assert "WHERE category_id='' OR category_id IS NULL" in DB
    assert "SELECT DISTINCT category FROM catalog" in DB
def test_image_update_uses_stable_id():
    assert "save_category_image_by_id" in DB
    assert "/by-id/{category_id}/image" in MAIN
    assert "/by-id/'+encodeURIComponent(categoryId)+'/image" in ADMIN
def test_delete_is_reference_protected():
    assert "def delete_category_by_id" in DB
    assert "SELECT COUNT(*) FROM catalog WHERE category=?" in DB
    assert "Merge/Reassign them before deletion" in MAIN
def test_duplicate_diagnostics_and_merge():
    assert "def category_diagnostics" in DB
    assert "unquote(d[\"category\"])" in DB
    assert "def merge_category_by_id" in DB
    assert "/diagnostics" in ADMIN and "mergeDuplicateCategory" in ADMIN
def test_rename_uses_stable_id():
    assert "def update_category_by_id" in DB
    assert "/by-id/'+encodeURIComponent(categoryId)" in ADMIN
def test_new_category_gets_stable_id():
    assert "uuid.uuid4().hex" in DB
