from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_catalog_template_management_contract_present():
    main=(ROOT/'app'/'main.py').read_text(encoding='utf-8')
    html=(ROOT/'static'/'admin.html').read_text(encoding='utf-8')
    for route in ['/api/admin/catalog/templates', '/api/admin/catalog/validation/download', '/api/admin/catalog/templates/rollback', '/api/admin/catalog/templates/cleanup']:
        assert route in main
    assert '_backup_active_template()' in main
    assert "_cleanup_template_backups(30)" in main
    assert 'Download last validation (HTML)' in html
    assert 'Older than 1 month' in html and 'Older than 3 months' in html and 'Older than 6 months' in html and 'Older than 1 year' in html
    assert 'Custom date range' in html
    assert 'Catalog DB ${fmtBytes(st.catalog_database_bytes)}' in html
    assert 'Images ${fmtBytes(st.catalog_images_bytes)}' in html
    assert 'Template backups ${fmtBytes(st.template_backups_bytes)}' in html

def test_variant_price_validation_is_positional_not_float_on_whole_cell():
    main=(ROOT/'app'/'main.py').read_text(encoding='utf-8')
    assert "prices=_split_variant(r.get('price'))" in main
    assert "mrps=_split_variant(r.get('mrp'))" in main
    assert "units=_split_variant(r.get('unit'))" in main
    assert 'variant count mismatch' in main
    assert 'MRP {mrp:g} cannot be lower than selling price {price:g}' in main
    assert "float(r['price'])" not in main
