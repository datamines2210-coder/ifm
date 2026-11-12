from pathlib import Path


def test_manager_role_ui_can_reuse_pagination_helpers_and_data_arrays():
    html = (Path(__file__).parents[1] / "static" / "admin.html").read_text(encoding="utf-8")
    assert "window.pageRows=function" in html
    assert "window.putPager=function" in html
    assert "window.orderItems=[]" in html
    assert "window.feedbackItems=[]" in html
    assert "window.categoryItems=[]" in html
    assert "window.render=function(){" in html
    assert "pageRows('products',filtered)" in html
