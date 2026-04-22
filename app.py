from flask import Flask, jsonify, render_template, make_response, request, redirect, session, send_file
from scrapers.community import SCRAPERS
from scrapers.news import NEWS_SCRAPERS
from scrapers.hotdeal import HOTDEAL_SCRAPERS
import threading
import time
import os
import sqlite3
import secrets
import zipfile
import io
import json as _json

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(24))

# ===== 댓글 DB =====
_DATABASE_URL = os.environ.get('DATABASE_URL', '')
if _DATABASE_URL.startswith('postgres://'):
    _DATABASE_URL = _DATABASE_URL.replace('postgres://', 'postgresql://', 1)
_USE_PG = bool(_DATABASE_URL)

def _get_conn():
    if _USE_PG:
        import psycopg2
        return psycopg2.connect(_DATABASE_URL)
    conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), 'comments.db'))
    conn.row_factory = sqlite3.Row
    return conn

def _init_db():
    conn = _get_conn()
    cur = conn.cursor()
    if _USE_PG:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS comments (
                id SERIAL PRIMARY KEY,
                url TEXT NOT NULL,
                nickname VARCHAR(50) NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_comments_url ON comments(url)")
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                nickname TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_comments_url ON comments(url)")
    conn.commit()
    cur.close()
    conn.close()

_init_db()

# ===== 블로그 수집 스케줄러 (Railway / 로컬 전용) =====
_IS_VERCEL = bool(os.environ.get("VERCEL"))
_blog_scheduler = None

if not _IS_VERCEL:
    try:
        from blog_collector import start_scheduler, init_db as blog_init_db
        blog_init_db()
        _blog_scheduler = start_scheduler()
    except Exception as e:
        print(f"[app] 블로그 스케줄러 초기화 실패: {e}")

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

@app.route("/api/comments/counts", methods=["POST"])
def api_comment_counts():
    urls = (request.get_json(silent=True) or {}).get('urls', [])
    if not urls or len(urls) > 100:
        return jsonify({}), 400
    ph = '%s' if _USE_PG else '?'
    placeholders = ','.join([ph] * len(urls))
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT url, COUNT(*) FROM comments WHERE url IN ({placeholders}) GROUP BY url", urls)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify({r[0]: r[1] for r in rows})


@app.route("/api/comments")
def api_get_comments():
    url = request.args.get('url', '').strip()
    if not url:
        return jsonify({"error": "url required"}), 400
    ph = '%s' if _USE_PG else '?'
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT nickname, content, created_at FROM comments WHERE url={ph} ORDER BY created_at ASC", (url,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    comments = [{"nickname": r[0], "content": r[1], "created_at": str(r[2])[:16]} for r in rows]
    return jsonify({"comments": comments, "count": len(comments)})


@app.route("/api/comments", methods=["POST"])
def api_post_comment():
    data = request.get_json(silent=True) or {}
    url = data.get('url', '').strip()
    nickname = data.get('nickname', '').strip()[:20]
    content = data.get('content', '').strip()[:300]
    if not url or not nickname or not content:
        return jsonify({"error": "url, nickname, content required"}), 400
    ph = '%s' if _USE_PG else '?'
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(f"INSERT INTO comments (url, nickname, content) VALUES ({ph},{ph},{ph})", (url, nickname, content))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"ok": True})


# ===== 블로그 어드민 라우트 =====

@app.route("/blog-admin")
def blog_admin():
    return render_template("blog_admin.html")


@app.route("/api/blog/batches")
def api_blog_batches():
    try:
        from blog_collector import get_batches
        return jsonify(get_batches())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/blog/batch/<batch_id>")
def api_blog_batch(batch_id):
    try:
        from blog_collector import get_batch_posts
        return jsonify(get_batch_posts(batch_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/blog/collect", methods=["POST"])
def api_blog_collect():
    """수동으로 즉시 수집 실행."""
    if _IS_VERCEL:
        return jsonify({"ok": False, "error": "Vercel 환경에서는 수동 수집을 지원하지 않습니다."}), 400
    try:
        from blog_collector import collect_once, init_db as blog_init_db
        blog_init_db()

        t = threading.Thread(target=_do_collect, daemon=True)
        t.start()

        from datetime import datetime
        batch_id = datetime.now().strftime("%Y%m%d_%H%M")
        return jsonify({"ok": True, "batch_id": batch_id, "message": "백그라운드에서 수집 중입니다."})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def _do_collect():
    try:
        from blog_collector import collect_once
        collect_once()
    except Exception as e:
        print(f"[app] collect_once 오류: {e}")


@app.route("/api/blog/queue", methods=["GET"])
def api_blog_queue_get():
    """로컬 naver_poster.py가 대기 중인 글 목록을 가져가는 엔드포인트."""
    try:
        from blog_collector import get_queued_posts
        return jsonify(get_queued_posts())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/blog/queue", methods=["POST"])
def api_blog_queue_add():
    """모바일 어드민에서 발행 대기열에 추가."""
    body = request.get_json(silent=True) or {}
    post_ids = body.get("post_ids", [])
    if not post_ids:
        return jsonify({"ok": False, "error": "post_ids 필요"}), 400
    try:
        from blog_collector import enqueue_posts
        enqueue_posts(post_ids)
        return jsonify({"ok": True, "queued": len(post_ids)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/blog/queue/done", methods=["POST"])
def api_blog_queue_done():
    """발행 완료 처리 또는 대기열에서 제거(undo=true)."""
    body    = request.get_json(silent=True) or {}
    post_id = body.get("post_id")
    undo    = body.get("undo", False)
    if not post_id:
        return jsonify({"ok": False, "error": "post_id 필요"}), 400
    try:
        from blog_collector import mark_published, unqueue_post
        if undo:
            unqueue_post(post_id)
        else:
            mark_published(post_id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/blog/images/<int:post_id>/zip")
def api_blog_images_zip(post_id):
    """선택한 게시글 이미지들을 ZIP으로 묶어서 다운로드."""
    try:
        from blog_collector import get_batch_posts, get_batches
        post = None
        for batch in get_batches(100):
            for p in get_batch_posts(batch["batch_id"]):
                if p["id"] == post_id:
                    post = p
                    break
            if post:
                break

        if not post:
            return jsonify({"error": "게시글을 찾을 수 없습니다."}), 404

        images = post.get("images", [])
        static_root = os.path.join(os.path.dirname(__file__), "static")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            count = 0
            for img in images:
                local = img.get("local")
                if not local:
                    continue
                filepath = os.path.join(static_root, local.replace("/", os.sep))
                if os.path.exists(filepath):
                    zf.write(filepath, os.path.basename(filepath))
                    count += 1

        if count == 0:
            return jsonify({"error": "저장된 이미지가 없습니다."}), 404

        buf.seek(0)
        safe_title = "".join(c for c in post["title"][:20] if c.isalnum() or c in " _-")
        filename = f"{post['source']}_{post['rank']}위_{safe_title}.zip"
        return send_file(
            buf,
            mimetype="application/zip",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 로컬 호스트 테스트 포트(ex. http://localhost:5000/)
if __name__ == "__main__":
    app.run(debug=True, port=5000)
