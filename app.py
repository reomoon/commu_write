from flask import Flask, jsonify, render_template
from scrapers.community import SCRAPERS
from scrapers.news import NEWS_SCRAPERS
import threading
import time

app = Flask(__name__)

# 캐시: 주기적으로 갱신
_cache = {}
_cache_lock = threading.Lock()
CACHE_TTL = 300  # 5분


def get_cached(key, scraper_fn):
    now = time.time()
    with _cache_lock:
        entry = _cache.get(key)
        if entry and (now - entry["ts"]) < CACHE_TTL:
            return entry["data"]
    data = scraper_fn()
    with _cache_lock:
        _cache[key] = {"data": data, "ts": time.time()}
    return data


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/community/<source>")
def api_community(source):
    if source not in SCRAPERS:
        return jsonify({"error": "unknown source"}), 404
    data = get_cached(f"community_{source}", SCRAPERS[source])
    return jsonify({"source": source, "items": data})


@app.route("/api/news/<category>")
def api_news(category):
    if category not in NEWS_SCRAPERS:
        return jsonify({"error": "unknown category"}), 404
    data = get_cached(f"news_{category}", NEWS_SCRAPERS[category])
    return jsonify({"category": category, "items": data})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
