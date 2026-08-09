from flask import Flask, request, jsonify, send_file
from .cache import TTLCache
from .analytics import AnalyticsTracker
from .suggester import Suggester
from .widget import WIDGET_JS, DEMO_PAGE_HTML


def create_app():
    app = Flask(__name__)
    app.config["PROPAGATE_EXCEPTIONS"] = True

    cache = TTLCache(ttl=120, max_size=500)
    analytics = AnalyticsTracker()
    suggester = Suggester()

    @app.route("/")
    def index():
        return DEMO_PAGE_HTML

    @app.route("/widget/autocomplete.js")
    def widget_js():
        return WIDGET_JS, 200, {"Content-Type": "application/javascript"}

    @app.route("/api/suggest")
    def suggest():
        query = request.args.get("q", "").strip()
        if not query:
            return jsonify({"query": "", "groups": [], "total": 0})

        cache_key = f"suggest:{query.lower()}"
        cached = cache.get(cache_key)
        if cached is not None:
            return jsonify(cached)

        results = suggester.search(query, max_results=8)
        cache.set(cache_key, results)
        return jsonify(results)

    @app.route("/api/trending")
    def trending():
        cache_key = "trending"
        cached = cache.get(cache_key)
        if cached is not None:
            return jsonify(cached)

        results = suggester.get_trending()
        cache.set(cache_key, results, ttl=300)
        return jsonify(results)

    @app.route("/api/analytics", methods=["POST"])
    def analytics_event():
        data = request.get_json(silent=True) or {}
        event_type = data.get("type", "unknown")
        event_data = data.get("data", {})
        event = analytics.track(event_type, event_data)
        return jsonify({"success": True, "event": event}), 201

    @app.after_request
    def add_cors(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return response

    return app
