from pathlib import Path
H=Path("static/scorer.html").read_text(encoding="utf-8")
def test_benchmark_table_scrolls_inside_section():
 assert "#benchmarkAdminBox{max-width:100%;overflow-x:auto" in H
 assert "#benchmarkAdminBox table{width:max-content;min-width:" in H
def test_benchmark_inputs_have_editable_widths():
 assert 'input[data-k="level"]' in H and 'input[data-k="rank_no"]' in H
def test_first_columns_are_sticky():
 assert "#benchmarkAdminBox th:first-child" in H
 assert "#benchmarkAdminBox th:nth-child(2)" in H
def test_scroll_hint_present():
 assert "Scroll horizontally to view and update all benchmark values." in H
