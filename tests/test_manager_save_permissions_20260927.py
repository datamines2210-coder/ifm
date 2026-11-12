from pathlib import Path
M=(Path(__file__).resolve().parents[1]/"app"/"main.py").read_text()
H=(Path(__file__).resolve().parents[1]/"static"/"admin.html").read_text()
def block(marker):
    i=M.index(marker); j=M.find("\n@app.",i+1); return M[i:j if j!=-1 else len(M)]
def test_manager_can_save_product():
    b=block('@app.put("/api/admin/catalog/{product_id}"')
    assert "Depends(admin_required)" in b and "Depends(administrator_only)" not in b
def test_manager_can_upload_product_image():
    assert "Depends(admin_required)" in block('@app.post("/api/admin/catalog/{product_id}/image"')
def test_manager_can_save_category_metadata():
    b=block('@app.put("/api/admin/catalog/categories/by-id/{category_id}"')
    assert "Depends(admin_required)" in b and "Depends(administrator_only)" not in b
def test_manager_can_upload_category_image():
    b=block('@app.post("/api/admin/catalog/categories/by-id/{category_id}/image"')
    assert "Depends(admin_required)" in b and "Depends(administrator_only)" not in b
def test_destructive_category_actions_stay_admin_only():
    assert "Depends(administrator_only)" in block('@app.delete("/api/admin/catalog/categories/by-id/{category_id}"')
    assert "Depends(administrator_only)" in block('@app.post("/api/admin/catalog/categories/by-id/{category_id}/merge"')
def test_category_save_confirms_success():
    assert "Category updated successfully." in H
