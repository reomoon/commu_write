"""
하루 4회(00:00 / 06:00 / 12:00 / 18:00 KST) 커뮤니티 상위 10개 글을 수집하고,
본문 이미지를 저장한다. Railway / 로컬 환경 전용 (Vercel 서버리스 미지원).
"""
import json
import os
import sqlite3
import threading
from datetime import datetime

from scrapers.community import SCRAPERS
from scrapers.post_scraper import scrape_post_images

DB_PATH = os.path.join(os.path.dirname(__file__), "blog_collected.db")
DB_LOCK = threading.Lock()

TARGET_SOURCES = ["bobaedream", "todayhumor", "ruliweb", "instiz", "inven"]
TOP_N = 10

SOURCE_LABELS = {
    "bobaedream": "보배드림",
    "todayhumor": "오늘의유머",
    "ruliweb": "루리웹",
    "instiz": "인스티즈",
    "inven": "인벤",
}


# ─── DB ───────────────────────────────────────────────────────────────────────

def init_db():
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS collected_posts (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                source           TEXT    NOT NULL,
                rank             INTEGER NOT NULL,
                title            TEXT    NOT NULL,
                url              TEXT    NOT NULL,
                images           TEXT    DEFAULT '[]',
                collected_at     TEXT    NOT NULL,
                batch_id         TEXT    NOT NULL,
                status           TEXT    DEFAULT 'pending'
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_batch ON collected_posts(batch_id)"
        )
        conn.commit()
        conn.close()


def _insert_post(source, rank, title, url, images, collected_at, batch_id):
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO collected_posts (source,rank,title,url,images,collected_at,batch_id) "
            "VALUES (?,?,?,?,?,?,?)",
            (source, rank, title, url, json.dumps(images, ensure_ascii=False),
             collected_at, batch_id),
        )
        conn.commit()
        conn.close()


def get_batches(limit=20):
    """최근 배치 목록을 반환 (batch_id, collected_at, 글 수)."""
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT batch_id, MIN(collected_at) AS collected_at, COUNT(*) AS post_count "
            "FROM collected_posts "
            "GROUP BY batch_id "
            "ORDER BY collected_at DESC "
            "LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
    return [dict(r) for r in rows]


def get_batch_posts(batch_id):
    """배치 안의 게시글을 source → rank 순으로 반환."""
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM collected_posts "
            "WHERE batch_id=? "
            "ORDER BY source, rank",
            (batch_id,),
        ).fetchall()
        conn.close()

    posts = []
    for row in rows:
        d = dict(row)
        try:
            d["images"] = json.loads(d.get("images") or "[]")
        except Exception:
            d["images"] = []
        d["source_label"] = SOURCE_LABELS.get(d["source"], d["source"])
        posts.append(d)
    return posts


def mark_published(post_id):
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "UPDATE collected_posts SET status='published' WHERE id=?", (post_id,)
        )
        conn.commit()
        conn.close()


def unqueue_post(post_id):
    """대기열에서 제거 (pending으로 되돌림)."""
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "UPDATE collected_posts SET status='pending' WHERE id=? AND status='queued'",
            (post_id,),
        )
        conn.commit()
        conn.close()


def enqueue_posts(post_ids):
    """모바일 어드민에서 선택한 글을 발행 대기열로 등록."""
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH)
        conn.executemany(
            "UPDATE collected_posts SET status='queued' WHERE id=? AND status='pending'",
            [(pid,) for pid in post_ids],
        )
        conn.commit()
        conn.close()


def get_queued_posts():
    """로컬 naver_poster.py가 가져갈 대기 중인 글 목록."""
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM collected_posts WHERE status='queued' ORDER BY collected_at, source, rank"
        ).fetchall()
        conn.close()

    posts = []
    for row in rows:
        d = dict(row)
        try:
            d["images"] = json.loads(d.get("images") or "[]")
        except Exception:
            d["images"] = []
        d["source_label"] = SOURCE_LABELS.get(d["source"], d["source"])
        posts.append(d)
    return posts


# ─── 수집 작업 ────────────────────────────────────────────────────────────────

def collect_once():
    """
    6개 커뮤니티 상위 5개 글 수집 + 이미지 다운로드.
    APScheduler 또는 수동 호출 가능.
    """
    now = datetime.now()
    batch_id = now.strftime("%Y%m%d_%H%M")
    date_str = now.strftime("%Y%m%d")
    collected_at = now.isoformat(timespec="seconds")

    print(f"[collector] batch {batch_id} 시작")

    for source in TARGET_SOURCES:
        scraper = SCRAPERS.get(source)
        if scraper is None:
            print(f"[collector] 스크래퍼 없음: {source}")
            continue
        try:
            items = scraper()[:TOP_N]
        except Exception as e:
            print(f"[collector] {source} 목록 수집 실패: {e}")
            continue

        for item in items:
            rank = item.get("rank", 0)
            title = item.get("title", "")
            url = item.get("url", "")
            if not url:
                continue

            try:
                images = scrape_post_images(source, url, rank, date_str)
            except Exception as e:
                print(f"[collector] {source} rank{rank} 이미지 수집 실패: {e}")
                images = []

            _insert_post(source, rank, title, url, images, collected_at, batch_id)
            label = SOURCE_LABELS.get(source, source)
            print(f"[collector] {label} {rank}위 저장 | 이미지 {len(images)}개 | {title[:40]}")

    print(f"[collector] batch {batch_id} 완료")


# ─── 스케줄러 ─────────────────────────────────────────────────────────────────

def start_scheduler():
    """
    APScheduler BackgroundScheduler 시작.
    하루 4회: 00:00 / 06:00 / 12:00 / 18:00 KST
    Railway / 로컬 전용 — Vercel 서버리스 환경에서는 동작하지 않음.
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        print("[collector] apscheduler 미설치 — 스케줄러 비활성. pip install apscheduler")
        return None

    init_db()
    scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    scheduler.add_job(
        collect_once,
        CronTrigger(hour="0,6,12,18", minute=0, timezone="Asia/Seoul"),
        id="blog_collect",
        replace_existing=True,
    )
    scheduler.start()
    print("[collector] 스케줄러 시작 (00:00 / 06:00 / 12:00 / 18:00 KST)")
    return scheduler
