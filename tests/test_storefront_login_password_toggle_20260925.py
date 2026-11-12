from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")

def test_login_password_has_show_hide_control():
    assert 'class="password-field"' in HTML
    assert 'id="loginPasswordToggle"' in HTML
    assert 'onclick="toggleLoginPassword()"' in HTML
    assert 'aria-label="Show password"' in HTML
    assert 'autocomplete="current-password"' in HTML

def test_toggle_changes_only_password_visibility():
    assert "input.type=show?'text':'password'" in HTML
    assert "show?'Hide password':'Show password'" in HTML

def test_signup_password_is_not_changed_to_toggle_component():
    assert '<input id="apass" type="password" placeholder="At least 8 characters">' in HTML
