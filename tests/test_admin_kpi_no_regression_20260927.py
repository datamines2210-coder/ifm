from pathlib import Path
import re, subprocess, tempfile
H=(Path(__file__).resolve().parents[1]/"static"/"admin.html").read_text()
M=(Path(__file__).resolve().parents[1]/"app"/"main.py").read_text()
def test_kpi_only_catalog():
    assert 'id="catalogKpiStats"' in H
    assert "stats.hidden=name!=='catalog'" in H
    assert "stats.style.display=name==='catalog'?'':'none'" in H
def test_navigation_uses_single_view_setter():
    assert "setAdminView(initial)" in H
    assert "setAdminView(b.dataset.view)" in H
def test_manager_save_success_behavior_retained():
    assert "Category updated successfully." in H
    i=M.index('@app.put("/api/admin/catalog/categories/by-id/{category_id}"')
    j=M.find("\n@app.",i+1)
    assert "Depends(admin_required)" in M[i:j]
def test_inline_js_parses():
    for code in re.findall(r"<script(?:[^>]*)>(.*?)</script>",H,flags=re.S|re.I):
        with tempfile.NamedTemporaryFile("w",suffix=".js",delete=False,encoding="utf-8") as f:
            f.write(code); name=f.name
        r=subprocess.run(["node","--check",name],capture_output=True,text=True)
        assert r.returncode==0,r.stderr
