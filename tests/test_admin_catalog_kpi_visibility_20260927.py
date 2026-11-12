from pathlib import Path
import re, subprocess, tempfile
H=(Path(__file__).resolve().parents[1]/"static"/"admin.html").read_text()
def test_catalog_kpis_have_one_container():
    assert 'id="catalogKpiStats"' in H
    assert H.count('id="catalogKpiStats"')==1
def test_navigation_controls_kpi_visibility():
    assert "stats.hidden=name!=='catalog'" in H
    assert "stats.style.display=name==='catalog'?'':'none'" in H
def test_initial_view_applies_visibility():
    assert "const initial=tabs.querySelector('.admin-tab.active')?.dataset.view||'catalog';" in H
    assert "setAdminView(initial);" in H
def test_role_independent_behavior():
    # Visibility is driven by active view, not administrator/manager role.
    block=H[H.index("const setAdminView=(name)=>"):H.index("tabs.addEventListener('click'",H.index("const setAdminView=(name)=>"))]
    assert "role" not in block.lower() and "manager" not in block.lower()
def test_inline_javascript_parses():
    for code in re.findall(r"<script(?:[^>]*)>(.*?)</script>",H,flags=re.S|re.I):
        with tempfile.NamedTemporaryFile("w",suffix=".js",delete=False,encoding="utf-8") as f:
            f.write(code); name=f.name
        r=subprocess.run(["node","--check",name],capture_output=True,text=True)
        assert r.returncode==0,r.stderr
