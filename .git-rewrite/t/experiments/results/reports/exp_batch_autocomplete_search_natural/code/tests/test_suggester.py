import pytest
from autocomplete.suggester import Suggester, Suggestion, DEFAULT_DATASET


class TestSuggester:
    @pytest.fixture
    def suggester(self):
        return Suggester()

    def test_search_exact_match(self, suggester):
        results = suggester.search("iPhone 15 Pro Max")
        assert results["total"] >= 1
        assert results["groups"][0]["results"][0]["title"] == "iPhone 15 Pro Max"

    def test_search_prefix_match(self, suggester):
        results = suggester.search("iphone")
        assert results["total"] >= 1
        titles = [
            r["title"]
            for g in results["groups"]
            for r in g["results"]
        ]
        assert any("iphone" in t.lower() for t in titles)

    def test_search_case_insensitive(self, suggester):
        lower = suggester.search("python")
        upper = suggester.search("PYTHON")
        assert lower["total"] == upper["total"]

    def test_search_no_results(self, suggester):
        results = suggester.search("xyznonexistent123")
        assert results["total"] == 0
        assert results["groups"] == []

    def test_search_empty_query(self, suggester):
        results = suggester.search("")
        assert results["total"] == 0
        assert results["groups"] == []

    def test_search_whitespace_query(self, suggester):
        results = suggester.search("   ")
        assert results["total"] == 0

    def test_search_results_grouped_by_category(self, suggester):
        results = suggester.search("apple")
        categories = {g["category"] for g in results["groups"]}
        assert "Products" in categories

    def test_search_partial_word_match(self, suggester):
        results = suggester.search("sec")
        titles = [
            r["title"].lower()
            for g in results["groups"]
            for r in g["results"]
        ]
        assert any("security" in t or "secure" in t for t in titles)

    def test_search_ranking_exact_above_partial(self, suggester):
        results = suggester.search("macbook")
        if results["total"] >= 1:
            first = results["groups"][0]["results"][0]
            assert first["score"] >= 50

    def test_trending_returns_items(self, suggester):
        trending = suggester.get_trending()
        assert len(trending) > 0
        assert "title" in trending[0]
        assert "category" in trending[0]

    def test_trending_limit(self, suggester):
        trending = suggester.get_trending(limit=3)
        assert len(trending) <= 3

    def test_custom_dataset(self):
        custom = [
            Suggestion("x1", "Custom Alpha", "First custom item", "Custom"),
            Suggestion("x2", "Custom Beta", "Second custom item", "Custom"),
        ]
        suggester = Suggester(dataset=custom)
        results = suggester.search("custom")
        assert results["total"] == 2

    def test_result_structure(self, suggester):
        results = suggester.search("ipad")
        assert "query" in results
        assert "groups" in results
        assert "total" in results
        for group in results["groups"]:
            assert "category" in group
            assert "results" in group
            for item in group["results"]:
                assert "id" in item
                assert "title" in item
                assert "description" in item
                assert "category" in item
                assert "url" in item
                assert "score" in item

    def test_search_description_match(self, suggester):
        results = suggester.search("containerization")
        if results["total"] >= 1:
            titles = [
                r["title"]
                for g in results["groups"]
                for r in g["results"]
            ]
            assert any("Docker" in t for t in titles)
