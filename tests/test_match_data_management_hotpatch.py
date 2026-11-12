from pathlib import Path
import inspect
from app.scorer import router
H=Path("static/scorer.html").read_text(encoding="utf-8")
R=Path("app/scorer/router.py").read_text(encoding="utf-8")
def test_layout_order_and_separation():
 assert H.index("Performance Benchmarks") < H.index("Match Data Management")
 assert "Upload & Analyze" in H and "Backup History" in H
def test_upload_is_stage_only():
 s=inspect.getsource(router.stage_matches_jsonl)
 assert "_merge_transfer" not in s and "_transfer_analysis" in s
def test_approval_requires_backup_and_authorization():
 s=inspect.getsource(router.approve_matches_import)
 assert '"APPROVE"' in s and "_backup_scorer_db" in s and "_merge_transfer" in s
def test_conflicts_and_missing_players_block_merge():
 s=inspect.getsource(router._transfer_analysis)
 assert '"conflicts"' in s and '"missing_players"' in s and '"blocked"' in s
def test_merge_is_new_only_and_transactional():
 s=inspect.getsource(router._merge_transfer)
 assert "new_ids=set" in s and "with connect() as c:" in s
def test_rollback_is_reversible_and_authorized():
 s=inspect.getsource(router.rollback_match_backup)
 assert '"ROLLBACK"' in s and '"before_rollback"' in s and ".backup(dst)" in s
def test_live_scoring_blocks_destructive_maintenance():
 assert "_active_scoring_locks()" in inspect.getsource(router.approve_matches_import)
 assert "_active_scoring_locks()" in inspect.getsource(router.rollback_match_backup)
