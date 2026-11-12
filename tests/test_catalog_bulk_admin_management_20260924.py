from pathlib import Path
import json
from app.db import init_db, save_catalog_product, archive_catalog_products, hard_delete_catalog_products, catalog_products_referenced_by_orders, create_order, catalog_product

ROOT=Path(__file__).resolve().parents[1]

def _product(pid):
    return dict(id=pid,name='Bulk '+pid,category='Tea',state='Karnataka',price=10,mrp=12,unit='1 pc',description='',image='',parent_url='',active=True,status='live')

def test_catalog_search_is_below_bulk_refresh_and_admin_multiselect_present():
    html=(ROOT/'static'/'admin.html').read_text(encoding='utf-8')
    assert html.index('<b>Bulk catalog refresh</b>') < html.index('id="filter"')
    assert 'id="catalogSelectVisible"' in html
    assert 'id="catalogValidationFilter"' in html
    assert 'Archive selected' in html and 'Delete selected' in html
    assert "if(isMarketManager())" in html

def test_bulk_catalog_endpoints_are_administrator_only_and_delete_checks_orders():
    main=(ROOT/'app'/'main.py').read_text(encoding='utf-8')
    assert '/api/admin/catalog/bulk/archive' in main
    assert '/api/admin/catalog/bulk/delete' in main
    assert 'Depends(administrator_only)' in main
    assert 'catalog_products_referenced_by_orders(ids)' in main
    assert 'must be archived instead' in main

def test_validation_flags_expose_stale_and_errors():
    main=(ROOT/'app'/'main.py').read_text(encoding='utf-8')
    assert "'validation_status':'stale'" in main
    assert "'validation_status':'validation_error'" in main
    assert "'validation_status':'valid'" in main

def test_db_bulk_archive_and_safe_hard_delete_helpers():
    init_db()
    save_catalog_product(_product('bulk-safe-a'))
    save_catalog_product(_product('bulk-safe-b'))
    assert archive_catalog_products(['bulk-safe-a']) == 1
    assert int(catalog_product('bulk-safe-a')['active']) == 0
    create_order('bulk-order', 'u-test', 'gw-bulk', 10, 'INR', 'created', json.dumps([{'id':'bulk-safe-b','qty':1}]), 1, customer_name='T', phone='9999999999', pincode='560001', address='A')
    assert catalog_products_referenced_by_orders(['bulk-safe-a','bulk-safe-b']) == ['bulk-safe-b']
    assert hard_delete_catalog_products(['bulk-safe-a']) == 1
    assert catalog_product('bulk-safe-a') is None
