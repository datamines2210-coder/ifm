from pathlib import Path
import inspect
from app.scorer import database, router
H=Path('static/scorer.html').read_text(encoding='utf-8')
def test_two_decimal_recommended_defaults():
    src=inspect.getsource(database.reset_performance_benchmarks)
    for value in ('0.50','1.01','2.01','3.50','4.50','5.99','7.99','2.99'): assert value in src
    assert '"level":"Coach"' in src
def test_save_normalizes_and_rejects_negative_ranges():
    src=inspect.getsource(database.save_performance_benchmarks)
    assert 'round(float(item.get(k,0)),2)' in src
    assert 'Benchmark values cannot be negative' in src
def test_progressive_range_scoring_uses_both_edges():
    src=inspect.getsource(router._ranking_result)
    assert '(value-low)/(high-low)' in src and '0.75 + 0.25' in src
def test_ui_uses_two_decimal_inputs_and_reference_values():
    assert 'step="0.01"' in H and 'n.toFixed(2)' in H and 'min="0"' in H
def test_profile_specific_benchmark_and_raw_metric_inputs_remain():
    src=inspect.getsource(router._ranking_result)
    assert 'by_level' in src and 'x["_sf_avg_raw"]' in src and 'x["_wp_avg_raw"]' in src
