import pytest
from autocomplete.widget import WIDGET_JS, DEMO_PAGE_HTML


class TestWidgetJS:
    def test_widget_contains_essentials(self):
        assert "AutocompleteSearch" in WIDGET_JS
        assert "role=\"combobox\"" in WIDGET_JS
        assert "role=\"listbox\"" in WIDGET_JS
        assert "role=\"option\"" in WIDGET_JS
        assert "aria-expanded" in WIDGET_JS
        assert "aria-activedescendant" in WIDGET_JS
        assert "aria-autocomplete" in WIDGET_JS

    def test_widget_contains_keyboard_handling(self):
        assert "ArrowDown" in WIDGET_JS
        assert "ArrowUp" in WIDGET_JS
        assert "Enter" in WIDGET_JS
        assert "Escape" in WIDGET_JS

    def test_widget_contains_debounce(self):
        assert "debounce" in WIDGET_JS
        assert "setTimeout" in WIDGET_JS

    def test_widget_contains_cache(self):
        assert "ResultsCache" in WIDGET_JS

    def test_widget_contains_highlight(self):
        assert "highlightText" in WIDGET_JS
        assert "<mark>" in WIDGET_JS

    def test_widget_contains_recent_searches(self):
        assert "Recent Searches" in WIDGET_JS
        assert "localStorage" in WIDGET_JS

    def test_widget_contains_analytics(self):
        assert "track" in WIDGET_JS
        assert "/analytics" in WIDGET_JS

    def test_widget_contains_grouping(self):
        assert "ac-group" in WIDGET_JS
        assert "ac-group-label" in WIDGET_JS
        assert "role=\"group\"" in WIDGET_JS

    def test_widget_contains_loading_state(self):
        assert "ac-loading" in WIDGET_JS
        assert "ac-spinner" in WIDGET_JS

    def test_widget_contains_error_state(self):
        assert "ac-error" in WIDGET_JS
        assert "Retry" in WIDGET_JS

    def test_widget_contains_empty_state(self):
        assert "ac-empty" in WIDGET_JS
        assert "No results found" in WIDGET_JS

    def test_widget_contains_abort_controller(self):
        assert "AbortController" in WIDGET_JS

    def test_widget_auto_init(self):
        assert "data-autocomplete" in WIDGET_JS
        assert "querySelectorAll" in WIDGET_JS

    def test_widget_exports_global(self):
        assert "window.AutocompleteSearch" in WIDGET_JS


class TestDemoPage:
    def test_demo_page_is_valid_html(self):
        assert "<!DOCTYPE html>" in DEMO_PAGE_HTML
        assert "<html" in DEMO_PAGE_HTML
        assert "</html>" in DEMO_PAGE_HTML

    def test_demo_page_has_input(self):
        assert 'data-autocomplete' in DEMO_PAGE_HTML
        assert 'placeholder' in DEMO_PAGE_HTML

    def test_demo_page_includes_widget_script(self):
        assert '/widget/autocomplete.js' in DEMO_PAGE_HTML

    def test_demo_page_has_responsive_css(self):
        assert '@media' in DEMO_PAGE_HTML
        assert 'max-width' in DEMO_PAGE_HTML

    def test_demo_page_has_search_icon(self):
        assert 'svg' in DEMO_PAGE_HTML.lower()

    def test_css_has_combobox_styles(self):
        assert 'ac-wrap' in DEMO_PAGE_HTML
        assert 'ac-dropdown' in DEMO_PAGE_HTML
        assert 'ac-option' in DEMO_PAGE_HTML
