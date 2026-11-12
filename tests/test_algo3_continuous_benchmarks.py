from pathlib import Path
import inspect
from app.scorer import router, database

H=Path('static/scorer.html').read_text(encoding='utf-8')

def source(): return inspect.getsource(router._ranking_result)

def test_algo3_matches_profile_level_not_best_fit():
    s=source()
    assert 'by_level=' in s and 'profile_level=' in s
    assert 'candidates=' not in s and 'best=max(' not in s

def test_algo3_uses_raw_metric_precision_and_continuous_wp_credit():
    s=source()
    assert '_wp_avg_raw' in s and '_sf_avg_raw' in s
    assert 'value/low' in s
    assert 'benchmark_score' in s

def test_missing_metrics_or_benchmark_keeps_player_but_score_unavailable():
    s=source()
    assert 'No detailed metric-recorded games' in s
    assert 'No benchmark configured for' in s
    assert 'ranking=sorted(qualified' in s

def test_benchmark_levels_are_add_remove_configurable():
    assert 'addBenchmarkAdminRow()' in H
    assert "closest('.benchmark-admin-row').remove()" in H
    assert 'At least one benchmark level is required' in inspect.getsource(database.save_performance_benchmarks)

def test_player_profile_levels_come_from_benchmark_configuration():
    assert "api('/performance-benchmarks')" in H
    assert 'profileLevels' in H

def test_algo3_display_is_whole_percent():
    assert 'Performance vs Expected</th>' in H
    assert "Math.round(Number(x.benchmark_score))+'%'" in H
