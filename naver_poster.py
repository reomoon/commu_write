"""
로컬 PC 전용 — 네이버 블로그 자동 발행 스크립트.

사용법:
  1. pip install playwright
     playwright install chromium

  2. .env 또는 환경변수 설정:
     RAILWAY_URL=https://your-app.railway.app   (배포 후) 또는 http://localhost:5000 (로컬)
     NAVER_ID=네이버아이디
     NAVER_PW=네이버비밀번호

  3. 모바일 blog-admin에서 원하는 글을 대기열에 추가한 뒤:
     python naver_poster.py
"""

import os
import sys
import time
import requests

# .env 파일 지원 (python-dotenv 있으면 로드)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

RAILWAY_URL = os.environ.get("RAILWAY_URL", "http://localhost:5000").rstrip("/")
NAVER_ID    = os.environ.get("NAVER_ID", "")
NAVER_PW    = os.environ.get("NAVER_PW", "")

SOURCE_LABELS = {
    "bobaedream": "보배드림", "todayhumor": "오늘의유머",
    "ruliweb": "루리웹",     "instiz": "인스티즈",
    "ppomppu": "뽐뿌",      "inven": "인벤",
}


# ── API 헬퍼 ─────────────────────────────────────────────────────────────────

def get_queue():
    r = requests.get(f"{RAILWAY_URL}/api/blog/queue", timeout=10)
    r.raise_for_status()
    return r.json()


def mark_done(post_id):
    requests.post(
        f"{RAILWAY_URL}/api/blog/queue/done",
        json={"post_id": post_id},
        timeout=10,
    )


# ── 이미지 URL 결정 ───────────────────────────────────────────────────────────

def image_url(img):
    """로컬 이미지는 Railway 공개 URL로, 없으면 원본 URL."""
    if img.get("local"):
        return f"{RAILWAY_URL}/static/{img['local']}"
    return img.get("original", "")


# ── 블로그 본문 HTML ──────────────────────────────────────────────────────────

def build_html(post):
    label  = SOURCE_LABELS.get(post["source"], post["source"])
    title  = post["title"]
    url    = post["url"]
    images = post.get("images", [])

    lines = [
        f"<p><strong>[{label}]</strong></p>",
        f"<p><strong>{title}</strong></p>",
        "<p><br></p>",
    ]
    for img in images:
        u = image_url(img)
        if u:
            lines.append(f'<img src="{u}" style="max-width:100%;"><p><br></p>')
    lines.append(f'<p>출처: <a href="{url}">{label}</a></p>')
    return "\n".join(lines)


# ── Playwright 발행 ───────────────────────────────────────────────────────────

def post_one(page, post):
    title   = post["title"]
    content = build_html(post)
    label   = SOURCE_LABELS.get(post["source"], post["source"])

    print(f"  발행 중: [{label}] {title[:50]}")

    # 블로그 글쓰기 페이지
    page.goto("https://blog.naver.com/PostWriteForm.naver", wait_until="domcontentloaded")
    page.wait_for_timeout(3000)

    # ── 제목 입력 ──
    # Smart Editor ONE 제목 영역
    title_sel = ".se-title-input .se-placeholder, .se-title-input"
    try:
        page.wait_for_selector(".se-title-input", timeout=10000)
        page.click(".se-title-input")
        page.keyboard.type(title, delay=30)
    except Exception:
        # 구버전 에디터 폴백
        try:
            page.fill('input[name="subject"]', title)
        except Exception as e:
            print(f"    제목 입력 실패: {e}")

    page.wait_for_timeout(500)

    # ── 본문 입력 ──
    try:
        # Smart Editor ONE 본문 영역
        page.wait_for_selector(".se-content", timeout=8000)
        page.click(".se-content")
        page.wait_for_timeout(300)
        # JavaScript로 직접 HTML 삽입
        page.evaluate("""(html) => {
            const editor = document.querySelector('.se-content');
            if (editor) {
                editor.focus();
                document.execCommand('insertHTML', false, html);
            }
        }""", content)
    except Exception:
        # iframe 기반 에디터 폴백
        try:
            frame = page.frame_locator("iframe#se_iframe, iframe.se-frame").first
            frame.locator("body").evaluate("(el, html) => { el.innerHTML = html; }", content)
        except Exception as e:
            print(f"    본문 입력 실패: {e}")

    page.wait_for_timeout(1000)

    # ── 발행 버튼 ──
    try:
        # 발행 버튼 클릭
        page.click("button.publish_btn, button[data-type='publish'], .se-publish-btn", timeout=5000)
        page.wait_for_timeout(1500)
        # 확인 팝업이 뜨면 확인
        confirm = page.query_selector(".btn_confirm, button:has-text('확인'), button:has-text('발행')")
        if confirm:
            confirm.click()
            page.wait_for_timeout(2000)
        print(f"    발행 완료!")
    except Exception as e:
        print(f"    발행 버튼 실패: {e}")
        print(f"    → 수동으로 발행 버튼을 눌러주세요. 10초 대기...")
        page.wait_for_timeout(10000)


def run():
    if not NAVER_ID or not NAVER_PW:
        print("오류: NAVER_ID, NAVER_PW 환경변수를 설정해주세요.")
        print("  Windows: set NAVER_ID=아이디 && set NAVER_PW=비밀번호")
        sys.exit(1)

    # 대기열 확인
    posts = get_queue()
    if not posts:
        print("대기열이 비어있습니다. blog-admin에서 글을 대기열에 추가해주세요.")
        sys.exit(0)

    print(f"대기 중인 글: {len(posts)}개")
    for p in posts:
        print(f"  - [{SOURCE_LABELS.get(p['source'], p['source'])}] {p['title'][:50]}")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("\nPlaywright가 설치되지 않았습니다.")
        print("  pip install playwright")
        print("  playwright install chromium")
        sys.exit(1)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)  # 눈으로 확인 가능하게 창 표시
        context = browser.new_context(
            locale="ko-KR",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # ── 네이버 로그인 ──
        print("\n네이버 로그인 중...")
        page.goto("https://nid.naver.com/nidlogin.login", wait_until="domcontentloaded")
        page.wait_for_timeout(1000)

        # JavaScript로 ID/PW 입력 (보안 필드 우회)
        page.evaluate(f"document.querySelector('#id').value = '{NAVER_ID}'")
        page.evaluate(f"document.querySelector('#pw').value = '{NAVER_PW}'")
        page.click(".btn_login")
        page.wait_for_timeout(3000)

        # 로그인 성공 확인
        if "nidlogin" in page.url:
            print("로그인 실패. ID/PW를 확인하거나 캡챠가 필요할 수 있습니다.")
            print("브라우저 창에서 직접 로그인 후 Enter를 누르세요...")
            input()

        print("로그인 완료!\n")

        # ── 각 글 발행 ──
        for post in posts:
            try:
                post_one(page, post)
                mark_done(post["id"])
                time.sleep(2)  # 연속 발행 간격
            except Exception as e:
                print(f"  오류: {e}")

        print("\n모든 발행 완료!")
        browser.close()


if __name__ == "__main__":
    run()
