from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEW_URL = "https://pages.razorpay.com/tifa"


def test_market_default_razorpay_page_is_current():
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    db = (ROOT / "app/db.py").read_text(encoding="utf-8")
    assert NEW_URL in main
    assert NEW_URL in db


def test_legacy_razorpay_defaults_are_migrated():
    db = (ROOT / "app/db.py").read_text(encoding="utf-8")
    assert "https://rzp.io/rzp/tifm" in db
    assert "https://pages.razorpay.com/tifm" in db
    assert NEW_URL in db


def test_scorer2_is_not_mounted_by_host_application():
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert ".scorer2" not in main
    assert '"scorer2"' not in main
    assert "'scorer2'" not in main


def test_scorer2_source_and_runtime_payload_removed_from_clean_build():
    for rel in ["app/scorer2", "scorer2_frontend", "scorer2_data", "static/scorer2-legacy.html"]:
        assert not (ROOT / rel).exists(), rel


def test_existing_extended_services_remain_mounted():
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    for service in ('"travel"', '"sports"', '"scorer"'):
        assert service in main
