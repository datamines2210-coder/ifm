from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_account_icon_is_dark_green_svg_and_mobile_smaller_only():
    html=(ROOT/'static'/'index.html').read_text(encoding='utf-8')
    assert 'class="account-icon" aria-hidden="true"><svg' in html
    assert '.nav-action .account-icon{color:var(--forest);width:20px;height:20px;font-size:0}' in html
    assert '@media(max-width:768px){.nav-action .account-icon{width:16px;height:16px;font-size:0}}' in html
    assert '.nav-action .account-icon svg{display:block;width:100%;height:100%;fill:currentColor}' in html

def test_catalog_has_separate_import_validation_and_upload_refresh_actions():
    html=(ROOT/'static'/'admin.html').read_text(encoding='utf-8')
    assert '<button onclick="importCatalog()">Import</button>' in html
    assert '<button class="primary" onclick="uploadCatalog()">Upload / Refresh</button>' in html
    assert 'validate_only:true' in html
    assert 'validate_only:false' in html
    assert 'Nothing uploaded yet.' in html

def test_openpyxl_is_pinned_and_missing_dependency_has_controlled_message():
    req=(ROOT/'requirements.txt').read_text(encoding='utf-8')
    main=(ROOT/'app'/'main.py').read_text(encoding='utf-8')
    assert 'openpyxl==3.1.5' in req
    assert 'Excel import is unavailable because openpyxl is not installed on the server.' in main
    assert 'Excel support is unavailable because openpyxl is not installed on the server.' in main
