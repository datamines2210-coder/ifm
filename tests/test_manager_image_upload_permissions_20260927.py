from pathlib import Path
import re
M=(Path(__file__).resolve().parents[1]/"app"/"main.py").read_text()
def route_block(path_fragment):
    i=M.index(path_fragment)
    j=M.find("\n@app.",i+1)
    return M[i:j if j!=-1 else len(M)]
def test_manager_product_image_upload_allowed():
    b=route_block('@app.post("/api/admin/catalog/{product_id}/image"')
    assert "Depends(admin_required)" in b
    assert "Depends(administrator_only)" not in b
def test_manager_legacy_category_image_upload_allowed():
    b=route_block('@app.post("/api/admin/catalog/categories/{category}/image"')
    assert "Depends(admin_required)" in b
def test_manager_stable_category_image_upload_allowed():
    b=route_block('@app.post("/api/admin/catalog/categories/by-id/{category_id}/image"')
    assert "Depends(admin_required)" in b
    assert "Depends(administrator_only)" not in b
def test_destructive_category_actions_remain_admin_only():
    for route in [
        '@app.delete("/api/admin/catalog/categories/by-id/{category_id}"',
        '@app.post("/api/admin/catalog/categories/by-id/{category_id}/merge"'
    ]:
        assert "Depends(administrator_only)" in route_block(route)
def test_declared_manager_privileges_match_routes():
    assert "Catalog: view, add, edit and upload product images; no delete/archive" in M
    assert "Categories: view, add, edit and upload images; no delete" in M
