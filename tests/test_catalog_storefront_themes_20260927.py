from pathlib import Path
import re, subprocess, tempfile
ROOT=Path('/mnt/data/theme_hotpatch_work')
M=(ROOT/'app/main.py').read_text(); I=(ROOT/'static/index.html').read_text(); A=(ROOT/'static/admin.html').read_text()
def block(marker):
    i=M.index(marker); j=M.find('\n@app.',i+1); return M[i:j if j!=-1 else len(M)]
def test_three_validated_themes():
    assert '^(modern|premium|compact)$' in M
    for t in ('modern','premium','compact'):
        assert f'catalog-theme-{t}' in I and f'data-theme="{t}"' in A
def test_admin_can_publish_manager_cannot():
    assert 'Depends(administrator_only)' in block('@app.put("/api/admin/catalog/layout-theme"')
    assert 'Depends(admin_required)' in block('@app.get("/api/admin/catalog/layout-theme"')
    assert "marketAdminRole()==='manager'" in A
def test_public_theme_uses_market_site_content():
    assert '"key":"catalog_layout_theme"' in M and "content.catalog_layout_theme?.value||'modern'" in I
def test_preview_is_non_persistent():
    assert 'catalog_theme_preview' in I and "window.open('/?catalog_theme_preview='" in A
def test_responsive_contract():
    for t in ('modern','premium','compact'):
        assert f'body.catalog-theme-{t} .categories' in I and f'body.catalog-theme-{t} .grid' in I
def test_existing_repairs_preserved():
    assert 'id="catalogKpiStats"' in A and "stats.hidden=name!=='catalog'" in A and 'Category updated successfully.' in A
def test_inline_js_parses():
    for html in (I,A):
        for code in re.findall(r'<script(?:[^>]*)>(.*?)</script>',html,flags=re.S|re.I):
            if not code.strip(): continue
            r=subprocess.run(['node','--check','-'],input=code,capture_output=True,text=True)
            assert r.returncode==0,r.stderr
