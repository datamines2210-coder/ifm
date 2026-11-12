from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_catalog_multiselect_script_is_real_html_not_escaped_text():
    s=(ROOT/'static'/'admin.html').read_text(encoding='utf-8')
    assert '<script>\n/* 2026-09-24 administrator catalog multi-select' in s
    assert '\\n<script>\\n/* 2026-09-24 administrator catalog multi-select' not in s
    assert "toggleCatalogProduct('${esc(x.id)}',this.checked)" in s

def test_delete_ui_requires_archive_first():
    s=(ROOT/'static'/'admin.html').read_text(encoding='utf-8')
    assert 'allArchived=n>0&&selected.every' in s
    assert 'Archive all selected products before deletion.' in s
    assert "d.disabled=!n||!allArchived" in s

def test_delete_api_requires_archive_first():
    s=(ROOT/'app'/'main.py').read_text(encoding='utf-8')
    assert 'Delete blocked: archive all selected products before permanent deletion:' in s
    assert 'referenced=catalog_products_referenced_by_orders(ids)' in s
