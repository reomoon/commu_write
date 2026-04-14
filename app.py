from flask import Flask, jsonify, render_template, make_response
from scrapers.community import SCRAPERS
from scrapers.news import NEWS_SCRAPERS
from scrapers.hotdeal import HOTDEAL_SCRAPERS
import threading
import time

app = Flask(__name__)

# 캐시: 주기적으로 갱신
_cache = {}
_cache_lock = threading.Lock()
CACHE_TTL = 3600  # 10분 (서버 인스턴스 메모리 캐시)
CDN_TTL = 3600    # 10분 (Vercel CDN 엣지 캐시 - Cold Start 우회)


def get_cached(key, scraper_fn):
    now = time.time()
    with _cache_lock:
        entry = _cache.get(key)
        if entry and (now - entry["ts"]) < CACHE_TTL:
            return entry["data"]
    try:
        data = scraper_fn()
    except Exception as e:
        print(f"[scraper error] {key}: {e}")
        data = None
    with _cache_lock:
        if data:
            _cache[key] = {"data": data, "ts": time.time()}
        elif entry:
            return entry["data"]  # 실패 시 이전 캐시 유지
        else:
            return []
    return data


def cached_response(data):
    """CDN 엣지 캐싱 헤더 포함 응답 - Cold Start 문제 해결"""
    resp = make_response(jsonify(data))
    resp.headers["Cache-Control"] = (
        f"public, s-maxage={CDN_TTL}, stale-while-revalidate=60"
    )
    return resp


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/community/<source>")
def api_community(source):
    if source not in SCRAPERS:
        return jsonify({"error": "unknown source"}), 404
    data = get_cached(f"community_{source}", SCRAPERS[source])
    return cached_response({"source": source, "items": data})


@app.route("/api/news/<category>")
def api_news(category):
    if category not in NEWS_SCRAPERS:
        return jsonify({"error": "unknown category"}), 404
    data = get_cached(f"news_{category}", NEWS_SCRAPERS[category])
    return cached_response({"category": category, "items": data})


@app.route("/api/hotdeal/<source>")
def api_hotdeal(source):
    if source not in HOTDEAL_SCRAPERS:
        return jsonify({"error": "unknown source"}), 404
    data = get_cached(f"hotdeal_{source}", HOTDEAL_SCRAPERS[source])
    return cached_response({"source": source, "items": data})

# 로컬 호스트 테스트 포트(ex. http://localhost:5000/)
if __name__ == "__main__":
    app.run(debug=True, port=5000)
