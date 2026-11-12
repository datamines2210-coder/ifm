from pathlib import Path
H=(Path(__file__).resolve().parents[1]/'static'/'index.html').read_text()
def test_quickview(): assert 'id="productQuickView"' in H and 'zoomed' in H
def test_actions(): assert 'addQuickViewToBasket' in H and 'Coming Soon' in H
def test_contact(): assert 'shareQuickViewProduct' in H and 'whatsAppQuickViewProduct' in H and 'feedbackQuickViewProduct' in H
def test_direct_add(): assert 'class="add-row" onclick="event.stopPropagation()"' in H
def test_accessibility(): assert 'role="dialog" aria-modal="true"' in H and "e.key==='Escape'" in H
