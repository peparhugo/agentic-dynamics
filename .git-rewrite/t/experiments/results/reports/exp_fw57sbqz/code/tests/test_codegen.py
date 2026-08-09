from codegen import generate_code


class TestCodeGen:
    def test_generates_default_length(self):
        code = generate_code("https://example.com")
        assert len(code) == 6

    def test_generates_custom_length(self):
        code = generate_code("https://example.com", length=8)
        assert len(code) == 8

    def test_codes_are_alphanumeric(self):
        for i in range(20):
            code = generate_code(f"https://example.com/{i}")
            assert code.isalnum(), f"Non-alphanumeric code: {code}"

    def test_different_urls_produce_different_codes(self):
        codes = {generate_code(f"https://test.com/{i}") for i in range(20)}
        assert len(codes) == 20

    def test_same_url_produces_different_codes(self):
        c1 = generate_code("https://same.com")
        c2 = generate_code("https://same.com")
        assert c1 != c2

    def test_short_urls_work(self):
        code = generate_code("a")
        assert len(code) == 6

    def test_code_can_be_variable_length(self):
        for length in [4, 8, 12]:
            code = generate_code("https://example.com", length=length)
            assert len(code) == length
