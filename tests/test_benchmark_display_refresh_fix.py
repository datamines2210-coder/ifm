from pathlib import Path
H=Path("static/scorer.html").read_text(encoding="utf-8")
def test_header():
 assert "Performance Score vs Expected</th>" in H
 assert "Performance Score vs Expected (%)</th>" not in H
def test_percentage_display():
 assert "toFixed(2).replace(/\\.00$/,'')+'%'" in H
def test_benchmark_not_periodically_redrawn():
 assert "let benchmarkReferenceLoaded=false;" in H
 assert "return benchmarkReferenceLoaded?true:loadBenchmarkReference()" in H
def test_explicit_refresh_paths_remain():
 assert "benchmarkReferenceLoaded=false;return loadBenchmarkReference()" in H
 assert "if(rankingAlgorithm==='benchmarks')await loadBenchmarkReference();" in H
