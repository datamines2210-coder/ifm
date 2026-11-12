from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_scorer2_route_mounted_on_host_8020_model():
    main = (ROOT / 'app/main.py').read_text(encoding='utf-8')
    assert '"scorer2"' in main
    assert 'from .scorer2.router import router' in main
    assert 'from .scorer2.web import router as web_router' in main
    assert '8030' not in main

def test_scorer2_has_own_config_and_no_parent_config_import():
    assert (ROOT / 'app/scorer2/config.py').is_file()
    for p in (ROOT / 'app/scorer2').glob('*.py'):
        text = p.read_text(encoding='utf-8')
        assert 'from ..config' not in text, p
        assert 'app.scorer.' not in text, p
        assert 'from .scorer.' not in text, p

def test_scorer2_namespace_and_db_are_independent():
    router = (ROOT / 'app/scorer2/router.py').read_text(encoding='utf-8')
    db = (ROOT / 'app/scorer2/database.py').read_text(encoding='utf-8')
    assert 'prefix="/scorer2/api"' in router
    assert 'scorer2_data' in db and 'scorer2.db' in db
    assert 'indian_family_market.db' not in db
    assert 'scorer.db' not in db.replace('scorer2.db','')

def test_scorer2_frontend_targets_same_host_port():
    vite = (ROOT / 'scorer2_frontend/vite.config.ts').read_text(encoding='utf-8')
    constants = (ROOT / 'scorer2_frontend/app/core/constants.ts').read_text(encoding='utf-8')
    assert 'http://localhost:8020' in vite
    assert '"/scorer2/api"' in constants
    assert '8030' not in vite

def test_scorer2_media_namespace_does_not_overlap_original_scorer():
    router = (ROOT / 'app/scorer2/router.py').read_text(encoding='utf-8')
    assert '/static/scorer2_player_photos/' in router
    assert '/static/scorer2_album/' in router
    assert '/static/scorer_player_photos/' not in router
    assert '/static/scorer_album/' not in router
