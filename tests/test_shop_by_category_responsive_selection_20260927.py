from pathlib import Path
H=(Path(__file__).resolve().parents[1]/"static"/"index.html").read_text()
def test_category_click_closes_and_applies():
    assert "function chooseShopCategory(c){syncShopCategorySelection(c);closeShopByCategory();if(c)setCategory(c);else showAll();}" in H
def test_selection_is_highlighted_and_labelled():
    assert ".shop-mega-item.active" in H and "aria-current" in H and "shop-selection" in H
def test_all_categories_clears_selection():
    assert "onclick=\"chooseShopCategory('')\">All categories" in H
def test_mobile_menu_is_responsive():
    assert "@media(max-width:760px)" in H and ".shop-mega{position:fixed" in H and ".shop-mega-in{display:block" in H
def test_outside_and_escape_close_preserved():
    assert "if(e.key==='Escape')closeShopByCategory()" in H
    assert "!panel.contains(e.target)" in H
def test_product_click_closes_menu():
    assert 'class="shop-mega-product" onclick="closeShopByCategory();' in H
