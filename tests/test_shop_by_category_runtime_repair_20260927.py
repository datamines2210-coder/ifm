from pathlib import Path
import re, subprocess, tempfile
H=(Path(__file__).resolve().parents[1]/"static"/"index.html").read_text()
def test_all_inline_javascript_parses():
    scripts=re.findall(r"<script(?:[^>]*)>(.*?)</script>",H,flags=re.S|re.I)
    assert scripts
    for code in scripts:
        with tempfile.NamedTemporaryFile("w",suffix=".js",delete=False,encoding="utf-8") as f:
            f.write(code); name=f.name
        r=subprocess.run(["node","--check",name],capture_output=True,text=True)
        assert r.returncode==0, r.stderr
def test_category_selection_closes_and_filters():
    assert "function chooseShopCategory(c){syncShopCategorySelection(c);closeShopByCategory();if(c)setCategory(c);else showAll();}" in H
def test_account_and_category_entrypoints_remain_present():
    assert "toggleShopByCategory(event)" in H
    assert "shopAllToggle" in H
    assert "account" in H.lower()
def test_escape_and_outside_click_close():
    assert "if(e.key==='Escape')closeShopByCategory()" in H
    assert "!panel.contains(e.target)" in H
