from app.utils.phone import normalize_phone, validate_phone


def test_normalize_phone_text_and_country_code():
    assert normalize_phone(" +84 901 234 567 ") == "0901234567"
    assert normalize_phone("84901234567") == "0901234567"
    assert normalize_phone("901234567") == "0901234567"


def test_validate_phone():
    assert validate_phone("0901234567")
    assert validate_phone(901234567)
    assert not validate_phone("123")
    assert not validate_phone("")
