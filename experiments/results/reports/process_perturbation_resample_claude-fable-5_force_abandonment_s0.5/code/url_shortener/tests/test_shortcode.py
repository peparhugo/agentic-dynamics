from app.shortcode import candidate_codes


def test_deterministic_first_candidate_is_stable():
    a = next(candidate_codes("https://example.com/a"))
    b = next(candidate_codes("https://example.com/a"))
    assert a == b


def test_different_urls_usually_produce_different_first_codes():
    a, _ = next(candidate_codes("https://example.com/a"))
    b, _ = next(candidate_codes("https://example.com/b"))
    assert a != b


def test_candidate_length_respected():
    for code, _salt in candidate_codes("https://example.com/x", length=10):
        assert len(code) == 10
        break


def test_salts_increase_and_change_code():
    gen = candidate_codes("https://example.com/collide")
    first_code, first_salt = next(gen)
    second_code, second_salt = next(gen)
    assert first_salt == 0
    assert second_salt == 1
    assert first_code != second_code
