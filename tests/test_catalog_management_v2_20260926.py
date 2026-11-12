from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MAIN=(ROOT/'app/main.py').read_text()
DB=(ROOT/'app/db.py').read_text()
ADMIN=(ROOT/'static/admin.html').read_text()

def test_blank_excel_image_preserves_mapping():
    assert "if existing and not image" in DB
    assert "image=existing['image']" in DB
    assert "preserved_image" in MAIN

def test_authoritative_rebuild_archives_missing_not_recycles_ids():
    assert "authoritative=False" in DB
    assert "status='archived'" in DB
    assert "mode: str = Field(default='update'" in MAIN

def test_daily_and_preop_snapshots_separate():
    assert "if kind=='daily'" in MAIN
    assert "preop-" in MAIN
    assert "openBackupRestore" in ADMIN
    assert "page_size=25" in ADMIN

def test_restore_regenerates_round_trip_snapshot():
    assert "active.xlsx').write_bytes(_make_catalog_snapshot())" in MAIN
    assert "import_catalog_atomic(prepared,authoritative=True)" in MAIN

def test_image_recovery_is_deterministic_and_admin_applied():
    assert "/image-recovery/scan" in MAIN
    assert "p.name.startswith(pid+'-')" in MAIN
    assert "/image-recovery/apply" in MAIN
    assert "Uncertain matches are never applied automatically" in ADMIN

def test_category_admin_merge_force_cleanup_and_stable_ids():
    assert "/categories/force-delete" in MAIN
    assert "force_delete_categories" in DB
    assert "category_id" in DB
    assert "mergeDuplicateCategory" in ADMIN

def test_templates_view_is_summary_not_unbounded_history():
    assert "Use Backup / Restore for snapshot history" in ADMIN
    assert 'id="backupRestoreModal"' in ADMIN

def test_import_lock_prevents_concurrent_apply():
    assert "CATALOG_IMPORT_LOCK" in MAIN
    assert "Another catalog import is already running" in MAIN
