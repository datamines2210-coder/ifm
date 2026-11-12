import inspect
from app.scorer import database, router
def test_benchmark_functions(): assert callable(database.list_performance_benchmarks) and callable(database.save_performance_benchmarks)
def test_admin_only(): assert "scorer_admin" in inspect.getsource(router.update_performance_benchmarks)
def test_algo3_configurable():
    s=inspect.getsource(router._ranking_result); assert "list_performance_benchmarks" in s and "Insufficient Metrics" in s
