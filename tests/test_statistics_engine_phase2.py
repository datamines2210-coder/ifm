"""Structural and behavioral compatibility checks for Phase 2."""
from datetime import datetime, timezone
from fastapi import HTTPException
import pytest
from app.scorer.engines.statistics import service
from app.scorer import router as legacy

def test_compatibility_symbols():
    for name in ('_period_bounds','_ranking_result','_performance_group_bounds'):
        assert getattr(legacy,name) is getattr(service,name)

def test_period_bounds():
    start,end=service._period_bounds('custom','2026-09-01','2026-09-03')
    assert start.date().isoformat()=='2026-09-01'
    assert (end-start).days==3
    with pytest.raises(HTTPException):
        service._period_bounds('bad')

def test_trend_buckets():
    a=datetime(2026,9,7,tzinfo=timezone.utc)
    b=datetime(2026,9,14,tzinfo=timezone.utc)
    buckets=service._performance_group_bounds(a,b,'weekly')
    assert len(buckets)==7
    assert buckets[0]['start']==a and buckets[-1]['end']==b

def test_ranking_algorithms(monkeypatch):
    monkeypatch.setattr(service,'period_stats',lambda *a,**kw:{'player_stats':[]})
    monkeypatch.setattr(service,'list_performance_benchmarks',lambda:[])
    for algo in ('algo_1','algo_2','algo_3'):
        result=service._ranking_result(algorithm=algo)
        assert result['items']==[] and result['algorithm']==algo
