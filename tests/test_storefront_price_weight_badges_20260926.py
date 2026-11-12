from pathlib import Path
HTML=(Path(__file__).resolve().parents[1]/'static'/'index.html').read_text(encoding='utf-8')
def test_badges():
 assert ".unit:before{content:'WEIGHT'" in HTML
 assert ".price:before{content:'PRICE'" in HTML
 assert 'class=\"price\">₹${Number(p.price||0).toFixed(2)}' in HTML
def test_actions_preserved():
 assert 'class=\"add-row\"' in HTML and 'Add to basket' in HTML and 'Coming Soon' in HTML
