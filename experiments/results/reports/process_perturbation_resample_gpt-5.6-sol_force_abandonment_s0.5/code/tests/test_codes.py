from shortener.codes import ALPHABET, SPACE, WIDTH, code_for_id


def test_code_mapping_is_fixed_width_and_collision_free_for_sample():
    codes = {code_for_id(identifier) for identifier in range(1, 10_001)}
    assert len(codes) == 10_000
    assert all(len(code) == WIDTH for code in codes)
    assert all(set(code) <= set(ALPHABET) for code in codes)


def test_code_mapping_rejects_values_outside_space():
    for identifier in (0, -1, SPACE):
        try:
            code_for_id(identifier)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for {identifier}")
