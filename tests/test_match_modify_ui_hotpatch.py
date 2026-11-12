from pathlib import Path
H=Path("static/scorer.html").read_text(encoding="utf-8")
def test_modify_button_has_handler_definition():
 assert "onclick=\"modifyMatch('" in H
 assert "async function modifyMatch(id)" in H
def test_modify_loads_match_players_teams():
 block=H[H.index("async function modifyMatch(id)"):H.index("async function saveModifiedMatch")]
 assert "api('/matches/'+encodeURIComponent(id))" in block
 assert "api('/players')" in block and "api('/teams')" in block
def test_modify_uses_existing_save_path():
 block=H[H.index("async function modifyMatch(id)"):H.index("async function saveModifiedMatch")]
 assert "onsubmit=\"saveModifiedMatch(event," in block
 assert "Game results" in block and "Player statistics" in block
def test_admin_guard_is_retained():
 block=H[H.index("async function modifyMatch(id)"):H.index("async function saveModifiedMatch")]
 assert "if(!isAdmin())" in block
