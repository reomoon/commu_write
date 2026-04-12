import requests
import re
from bs4 import BeautifulSoup, Tag
try:
    import cloudscraper
    _scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )
except Exception:
    _scraper = None

MOBILE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}

PC_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Upgrade-Insecure-Requests": "1",
}

RULIWEB_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Referer": "https://m.ruliweb.com/",
}

DOGDRIP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Referer": "https://www.dogdrip.net/",
}


def fetch(url, headers=None, timeout=10):
    try:
        h = headers or MOBILE_HEADERS
        r = requests.get(url, headers=h, timeout=timeout)
        r.raise_for_status()
        return BeautifulSoup(r.content, "lxml")
    except Exception as e:
        print(f"[fetch error] {url}: {e}")
        return None


def fetch_cf(url, timeout=15):
    """Cloudflare 보호 사이트용 scraper"""
    try:
        if _scraper:
            r = _scraper.get(url, timeout=timeout)
            r.raise_for_status()
            return BeautifulSoup(r.content, "lxml")
        return fetch(url, timeout=timeout)
    except Exception as e:
        print(f"[fetch_cf error] {url}: {e}")
        return None


def strip_comment_count(text):
    """제목 끝의 댓글 수 [N] 또는 N 제거"""
    text = re.sub(r'\[\d+\]\s*$', '', text).strip()
    text = re.sub(r'\d+\s*$', '', text).strip()
    return text


_POLITICS_KEYWORDS = {
    '국민의힘', '민주당', '더불어민주당', '정의당', '개혁신당',
    '국회의원', '국회', '탄핵', '탄핵소추',
    '윤석열', '이재명', '한덕수', '이준석', '홍준표',
    '여당', '야당', '여야', '총선', '대선', '지방선거',
    '국정감사', '인사청문회', '개헌', '헌법재판소',
    '검찰개혁', '사법개혁',
}

def _is_politics(title: str) -> bool:
    return any(kw in title for kw in _POLITICS_KEYWORDS)


def get_inven():
    """인벤 오픈이슈 오늘의 화제 top10"""
    soup = fetch("https://m.inven.co.kr/board/webzine/2097/")
    if not soup:
        return []

    issue = soup.find(id="open-issue-topic")
    if not issue:
        return []

    # 오늘의화제 (data-tab="0")
    content = issue.select_one('div.content[data-tab="0"]')
    if not content:
        content = issue

    items = []
    for li in content.select("li"):
        a = li.find("a", href=True)
        if not a:
            continue
        num_el = li.select_one(".num")
        cate_el = li.select_one(".cate")
        txt_el = li.select_one(".txt")

        rank = int(num_el.get_text(strip=True)) if num_el else len(items) + 1
        cate = cate_el.get_text(strip=True) if cate_el else ""
        title = txt_el.get_text(strip=True) if txt_el else a.get_text(strip=True)
        href = a.get("href", "")
        if href and not href.startswith("http"):
            href = "https://m.inven.co.kr" + href

        items.append({"rank": rank, "title": title, "category": cate, "url": href})

    return items[:10]


def get_bobaedream():
    """보배드림 베스트글 (정치 글 제외)"""
    soup = fetch("https://m.bobaedream.co.kr/board/new_writing/best")
    if not soup:
        return []

    items = []
    seen = set()
    rank = 1

    # bbs_view 링크가 있는 a 태그 기준
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if "/bbs_view/" not in href:
            continue

        # 제목: .cont 스팬
        txt_el = a.select_one(".txt .cont")
        if not txt_el:
            txt_el = a.select_one(".cont")
        if not txt_el:
            continue
        title = txt_el.get_text(strip=True)

        if not title or title in seen:
            continue

        # 정치X 필터
        if _is_politics(title):
            continue

        if not href.startswith("http"):
            href = "https://m.bobaedream.co.kr" + href

        seen.add(title)
        items.append({"rank": rank, "title": title, "url": href})
        rank += 1
        if rank > 50:
            break

    return items[:50]


def get_fmkorea():
    """에펨코리아 베스트2"""
    soup = fetch("https://m.fmkorea.com/best2", headers=PC_HEADERS)
    if not soup:
        return []

    items = []
    seen = set()
    rank = 1

    # div.li 안의 h3.title에서 제목 추출
    for div in soup.select("div.li"):
        h3 = div.select_one("h3.title")
        if not h3:
            continue
        title = h3.get_text(strip=True)
        title = re.sub(r'\[\d+\]', '', title).strip()

        if not title or len(title) < 3 or title in seen:
            continue

        a = div.find("a", href=re.compile(r'^/best2/\d+$'))
        if not a:
            continue
        href = "https://m.fmkorea.com" + a.get("href", "")

        seen.add(title)
        items.append({"rank": rank, "title": title, "url": href})
        rank += 1
        if rank > 50:
            break

    return items[:50]


def get_dogdrip():
    """개드립 인기글 (Cloudflare 우회)"""
    soup = fetch_cf("https://www.dogdrip.net/dogdrip")
    if not soup:
        return []

    items = []
    seen = set()
    rank = 1

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        # /dogdrip/숫자 형태의 게시글 링크
        if not re.match(r'^/dogdrip/\d+', href):
            continue

        # 제목 전용 요소 우선, 없으면 a 텍스트
        title_el = a.select_one(".title, .subject, strong")
        title = title_el.get_text(strip=True) if title_el else a.get_text(strip=True)
        title = strip_comment_count(title)

        if not title or len(title) < 3 or title in seen:
            continue

        href = "https://www.dogdrip.net" + href.split("?")[0]
        seen.add(title)
        items.append({"rank": rank, "title": title, "url": href})
        rank += 1
        if rank > 50:
            break

    return items[:50]


def get_ruliweb():
    """루리웹 유머 베스트"""
    soup = fetch("https://m.ruliweb.com/best/humor_only", headers=RULIWEB_HEADERS)
    if not soup:
        return []

    items = []
    seen = set()
    rank = 1

    for tr in soup.select("tr.table_body"):
        a = tr.select_one("a.subject_link")
        if not a:
            continue
        href = a.get("href", "")
        # ruliweb.com/best/ 링크만
        if "ruliweb.com/best/" not in href and not href.startswith("/best/"):
            continue

        # 댓글 수는 별도 span에 있음 - a 태그 직접 텍스트만
        title = ""
        for node in a.children:
            if isinstance(node, Tag):
                cls = node.get('class', [])
                if 'num_reply' not in cls:
                    title += node.get_text(strip=True)
            else:
                title += str(node).strip()
        title = title.strip()
        title = strip_comment_count(title)

        if not title or len(title) < 3 or title in seen:
            continue
        if not href.startswith("http"):
            href = "https://m.ruliweb.com" + href

        seen.add(title)
        items.append({"rank": rank, "title": title, "url": href})
        rank += 1
        if rank > 50:
            break

    return items[:50]


def get_dcinside():
    """디시인사이드 베스트 게시물"""
    soup = fetch("https://m.dcinside.com/board/dcbest", headers=PC_HEADERS)
    if not soup:
        return []

    NOTICE_NOS = {"30638"}  # 실시간베스트 갤러리 이용 안내 공지

    items = []
    seen = set()
    rank = 1

    for tr in soup.select("tr"):
        ub = tr.select_one(".ub-word")
        if not ub:
            continue

        title = ub.get_text(strip=True)
        # 댓글 수 [N] 또는 [N/N] 제거
        title = re.sub(r'\[\d+(?:/\d+)?\]\s*$', '', title).strip()

        if not title or len(title) < 3 or title in seen:
            continue

        # /board/view/ 링크만
        a = tr.find("a", href=re.compile(r'/board/view/'))
        if not a:
            continue
        href = a.get("href", "")

        # id와 no만 추출해서 PC URL로 재구성 (_dcbest 등 불필요한 파라미터 제거)
        id_match = re.search(r'[?&]id=([^&]+)', href)
        no_match = re.search(r'[?&]no=(\d+)', href)
        if not id_match or not no_match:
            continue

        gall_id = id_match.group(1)
        gall_no = no_match.group(1)

        if gall_no in NOTICE_NOS:
            continue

        href = f"https://gall.dcinside.com/board/view/?id={gall_id}&no={gall_no}"

        seen.add(title)
        items.append({"rank": rank, "title": title, "url": href})
        rank += 1
        if rank > 50:
            break

    return items[:50]


def get_theqoo():
    """더쿠 HOT 게시글"""
    soup = fetch("https://theqoo.net/hot?filter_mode=normal", headers=PC_HEADERS)
    if not soup:
        return []

    NOTICE_IDS = {"3516074637", "3176100535", "2984500576", "1383792790"}

    items = []
    seen = set()
    rank = 1

    # td.title 안의 a 태그만 — 댓글 수 앵커(#) 제외
    for a in soup.select("td.title a[href]"):
        href = a.get("href", "")
        # 댓글 앵커 링크 및 이벤트/카테고리 제외
        if "#" in href or not re.match(r'^/hot/\d+', href):
            continue
        # 공지 ID 제외
        post_id = re.search(r'/hot/(\d+)', href)
        if post_id and post_id.group(1) in NOTICE_IDS:
            continue

        title = a.get_text(strip=True)
        # 숫자만인 텍스트(조회수 등) 제외
        if not title or len(title) < 3 or title.isdigit() or title in seen:
            continue

        href = "https://theqoo.net" + href.split("?")[0]
        seen.add(title)
        items.append({"rank": rank, "title": title, "url": href})
        rank += 1
        if rank > 50:
            break

    return items[:50]


def get_mlbpark():
    """MLB파크 불펜 게시글"""
    soup = fetch("https://mlbpark.donga.com/mp/b.php?b=bullpen", headers=PC_HEADERS)
    if not soup:
        return []

    items = []
    seen = set()
    rank = 1

    for a in soup.select("div.title a[href*='b=bullpen'][href*='id=']"):
        href = a.get("href", "")
        title = re.sub(r'\[\d+\]\s*$', '', a.get_text(strip=True)).strip()

        if not title or len(title) < 3 or title in seen:
            continue

        if not href.startswith("http"):
            href = "https://mlbpark.donga.com" + href

        seen.add(title)
        items.append({"rank": rank, "title": title, "url": href})
        rank += 1
        if rank > 50:
            break

    return items[:50]


SCRAPERS = {
    "inven": get_inven,
    "bobaedream": get_bobaedream,
    "fmkorea": get_fmkorea,
    "ruliweb": get_ruliweb,
    "theqoo": get_theqoo,
    "dcinside": get_dcinside,
    "mlbpark": get_mlbpark,
}
