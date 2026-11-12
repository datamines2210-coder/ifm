from pathlib import Path


def test_shop_by_category_mega_menu_is_mounted_below_subnav():
    html = (Path(__file__).resolve().parents[1] / 'static' / 'index.html').read_text(encoding='utf-8')
    nav = html.index('<nav class="subnav">')
    nav_end = html.index('</nav>', nav)
    menu = html.index('id="shopBrowser"')
    hero = html.index('<section class="hero"')
    assert nav < nav_end < menu < hero
    assert '.shop-mega.open{display:block}' in html
    assert 'onclick="toggleShopByCategory(event)"' in html
