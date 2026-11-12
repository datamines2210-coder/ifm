from pathlib import Path
H=Path("static/scorer.html").read_text()
R=Path("app/scorer/router.py").read_text()

def test_new_label_is_used_everywhere_in_patch():
    assert "Algo_2 (Winning)" not in H
    assert "Algo_2 (Winning)" not in R
    assert "Algo_2 (Win Points)" in H
    assert 'label="Algo_2 (Win Points)"' in R

def test_internal_algorithm_contract_is_unchanged():
    assert 'value="algo_2"' in H
    assert "rankingAlgorithm=['algo_1','algo_2','algo_3','benchmarks']" in H
    assert "'algo_2':`The player of the ${periodLabel} who produces the most winning points is`" in H
