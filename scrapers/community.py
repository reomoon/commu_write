import requests
import re
from bs4 import BeautifulSoup, Tag
from concurrent.futures import ThreadPoolExecutor
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    import cloudscraper
    _scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )
except Exception:
    _scraper = None

# 세션 + 자동 재시도 (HTTP 오류 + 연결/타임아웃 오류 포함)
_session = requests.Session()
_retry = Retry(
    total=3,
    connect=2,
    read=2,
    backoff_factor=0.4,
    status_forcelist=[500, 502, 503, 504],
    allowed_methods=["GET"],
)
_adapter = HTTPAdapter(max_retries=_retry, pool_connections=10, pool_maxsize=20)
_session.mount("http://", _adapter)
_session.mount("https://", _adapter)

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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Referer": "https://bbs.ruliweb.com/",
}

DOGDRIP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Referer": "https://www.dogdrip.net/",
}


def fetch(url, headers=None, timeout=8):
    try:
        h = headers or MOBILE_HEADERS
        r = _session.get(url, headers=h, timeout=timeout)
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


def fetch_pages(urls, headers=None, timeout=8, use_cf=False):
    """URL 목록을 병렬로 가져오기 (순서 보존)"""
    def _get(url):
        if use_cf:
            return fetch_cf(url, timeout=timeout)
        return fetch(url, headers=headers, timeout=timeout)
    with ThreadPoolExecutor(max_workers=min(len(urls), 5)) as executor:
        return list(executor.map(_get, urls))


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
    '검찰개혁', '사법개혁', '석렬', '정치'
}

def _is_politics(title: str) -> bool:
    return any(kw in title for kw in _POLITICS_KEYWORDS)


TARGET = 50  # 모든 커뮤니티 스크래퍼 목표 수량


def get_inven():
    """인벤 오픈이슈 오늘의화제 + 게시판 목록"""
    items = []
    seen_urls = set()

    soups = fetch_pages([
        f"https://m.inven.co.kr/board/webzine/2097/?iskin=&gid=0&sk=&sv=&category=0&p={page}"
        for page in range(1, 4)
    ])

    for page_num, soup in enumerate(soups, 1):
        if not soup:
            continue

        # 1) 오늘의화제 top10 (1페이지에만 존재)
        if page_num == 1:
            issue = soup.find(id="open-issue-topic")
            if issue:
                content = issue.select_one('div.content[data-tab="0"]') or issue
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
                    if href not in seen_urls:
                        seen_urls.add(href)
                        items.append({"rank": rank, "title": title, "category": cate, "url": href})

        # 2) 게시판 목록 (contentLink 구조)
        for a in soup.select("a.contentLink[href]"):
            href = a.get("href", "")
            if not href.startswith("http"):
                href = "https://m.inven.co.kr" + href
            if href in seen_urls:
                continue
            subject_el = a.select_one("span.subject")
            cate_el = a.select_one("span.in-cate")
            if not subject_el:
                continue
            title = subject_el.get_text(strip=True)
            cate = cate_el.get_text(strip=True) if cate_el else ""
            if not title or len(title) < 3:
                continue
            seen_urls.add(href)
            items.append({"rank": len(items) + 1, "title": title, "category": cate, "url": href})

        if len(items) >= TARGET:
            break

    for i, item in enumerate(items):
        item["rank"] = i + 1

    return items[:TARGET]


def get_bobaedream():
    """보배드림 베스트글 (정치 글 제외)"""
    items = []
    seen = set()

    soups = fetch_pages([
        f"https://m.bobaedream.co.kr/board/new_writing/best?page={page}"
        for page in range(1, 4)
    ])

    for soup in soups:
        if not soup:
            continue
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if "/bbs_view/" not in href:
                continue
            txt_el = a.select_one(".txt .cont") or a.select_one(".cont")
            if not txt_el:
                continue
            title = txt_el.get_text(strip=True)
            if not title or title in seen:
                continue
            if _is_politics(title):
                continue
            if not href.startswith("http"):
                href = "https://m.bobaedream.co.kr" + href
            seen.add(title)
            items.append({"rank": len(items) + 1, "title": title, "url": href})
        if len(items) >= TARGET:
            break

    return items[:TARGET]


def get_todayhumor():
    """오늘의유머 베스트오브베스트"""
    items = []
    seen = set()

    soups = fetch_pages([
        f"https://www.todayhumor.co.kr/board/list.php?table=bestofbest&page={page}"
        for page in range(1, 4)
    ])

    for soup in soups:
        if not soup:
            continue
        for a in soup.find_all("a", href=re.compile(r'view\.php\?table=bestofbest&no=\d+')):
            href = a.get("href", "")
            title = a.get_text(strip=True)
            title = re.sub(r'\[\d+\]\s*$', '', title).strip()
            title = re.sub(r'\s+', ' ', title)
            if not title or title.isdigit() or len(title) < 3 or title in seen:
                continue
            no_match = re.search(r'no=(\d+)', href)
            if not no_match:
                continue
            href = f"https://www.todayhumor.co.kr/board/view.php?table=bestofbest&no={no_match.group(1)}"
            seen.add(title)
            items.append({"rank": len(items) + 1, "title": title, "url": href})
        if len(items) >= TARGET:
            break

    return items[:TARGET]


def get_dogdrip():
    """개드립 인기글 (Cloudflare 우회)"""
    items = []
    seen = set()

    # CF 우회는 느리므로 2페이지만 병렬 요청
    soups = fetch_pages([
        f"https://www.dogdrip.net/dogdrip?page={page}"
        for page in range(1, 3)
    ], use_cf=True)

    for soup in soups:
        if not soup:
            continue
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if not re.match(r'^/dogdrip/\d+', href):
                continue
            title_el = a.select_one(".title, .subject, strong")
            title = title_el.get_text(strip=True) if title_el else a.get_text(strip=True)
            title = strip_comment_count(title)
            if not title or len(title) < 3 or title in seen:
                continue
            href = "https://www.dogdrip.net" + href.split("?")[0]
            seen.add(title)
            items.append({"rank": len(items) + 1, "title": title, "url": href})
        if len(items) >= TARGET:
            break

    return items[:TARGET]


def get_ruliweb():
    """루리웹 유머 베스트"""
    items = []
    seen = set()

    # Vercel 클라우드 IP 차단 우회: cloudscraper로 TLS 핑거프린팅 모방
    soups = fetch_pages([
        f"https://bbs.ruliweb.com/best/humor_only?page={page}"
        for page in range(1, 3)
    ], use_cf=True, timeout=15)

    for soup in soups:
        if not soup:
            continue
        for tr in soup.select("tr.table_body"):
            a = tr.select_one("a.subject_link")
            if not a:
                continue
            href = a.get("href", "")
            if "ruliweb.com" not in href and not href.startswith("/best/") and not href.startswith("/"):
                continue
            title = ""
            for node in a.children:
                if isinstance(node, Tag):
                    cls = node.get('class', [])
                    if 'num_reply' not in cls:
                        title += node.get_text(strip=True)
                else:
                    title += str(node).strip()
            title = title.strip()
            title = re.sub(r'^\d+', '', title).strip()  # 앞에 붙는 순위 숫자 제거
            title = strip_comment_count(title)
            if not title or len(title) < 3 or title in seen:
                continue
            if not href.startswith("http"):
                href = "https://bbs.ruliweb.com" + href
            seen.add(title)
            items.append({"rank": len(items) + 1, "title": title, "url": href})
        if len(items) >= TARGET:
            break

    return items[:TARGET]


def get_dcinside():
    """디시인사이드 베스트 게시물"""
    NOTICE_NOS = {"30638"}

    items = []
    seen = set()

    soups = fetch_pages([
        f"https://m.dcinside.com/board/dcbest?page={page}"
        for page in range(1, 4)
    ], headers=PC_HEADERS)

    for soup in soups:
        if not soup:
            continue
        for tr in soup.select("tr"):
            ub = tr.select_one(".ub-word")
            if not ub:
                continue
            title = ub.get_text(strip=True)
            title = re.sub(r'\[\d+(?:/\d+)?\]\s*$', '', title).strip()
            if not title or len(title) < 3 or title in seen:
                continue
            a = tr.find("a", href=re.compile(r'/board/view/'))
            if not a:
                continue
            href = a.get("href", "")
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
            items.append({"rank": len(items) + 1, "title": title, "url": href})
        if len(items) >= TARGET:
            break

    return items[:TARGET]


def get_theqoo():
    """더쿠 HOT 게시글"""
    NOTICE_IDS = {"3516074637", "3176100535", "2984500576", "1383792790"}

    items = []
    seen = set()

    soups = fetch_pages([
        f"https://theqoo.net/hot?filter_mode=normal&page={page}"
        for page in range(1, 4)
    ], headers=PC_HEADERS)

    for soup in soups:
        if not soup:
            continue
        for a in soup.select("td.title a[href]"):
            href = a.get("href", "")
            if "#" in href or not re.match(r'^/hot/\d+', href):
                continue
            post_id = re.search(r'/hot/(\d+)', href)
            if post_id and post_id.group(1) in NOTICE_IDS:
                continue
            title = a.get_text(strip=True)
            if not title or len(title) < 3 or title.isdigit() or title in seen:
                continue
            href = "https://theqoo.net" + href.split("?")[0]
            seen.add(title)
            items.append({"rank": len(items) + 1, "title": title, "url": href})
        if len(items) >= TARGET:
            break

    return items[:TARGET]


def get_ppomppu_hot():
    """뽐뿌 커뮤니티 핫게시물 (hot.php + 자유게시판 보충)"""
    PPOMPPU_HEADERS = {**PC_HEADERS, "Referer": "https://www.ppomppu.co.kr/hot.php/"}

    # 광고성 게시판 ID 제외
    AD_BOARDS = {"pmarket", "pmarket2", "pmarket3", "pmarket7", "pmarket8",
                 "card_market", "experience", "event2", "coupon", "wcoupon", "guin"}

    items = []
    seen = set()

    def _parse_hot_links(soup):
        for a in soup.find_all("a", href=re.compile(r'/zboard/view\.php\?id=\w+&no=\d+')):
            href = a.get("href", "")
            board_match = re.search(r'[?&]id=(\w+)', href)
            if board_match and board_match.group(1) in AD_BOARDS:
                continue
            title = "".join(
                node for node in a.strings
                if node.strip() and node.strip().lower() not in ("hot", "pop", "new")
            ).strip()
            title = re.sub(r'^\s*\[?(hot|pop|new|ad)\]?\s*', '', title, flags=re.IGNORECASE).strip()
            title = re.sub(r'\s*\d+$', '', title).strip()
            if not title or len(title) < 3:
                continue
            if re.match(r'^AD\s', title, re.IGNORECASE):
                continue
            if not href.startswith("http"):
                href = "https://ppomppu.co.kr" + href
            if title not in seen:
                seen.add(title)
                items.append({"rank": len(items) + 1, "title": title, "url": href})

    # hot.php 페이지 병렬 수집
    hot_urls = ["https://ppomppu.co.kr/hot.php"] + [
        f"https://ppomppu.co.kr/hot.php?page={page}" for page in range(2, 5)
    ]
    for soup in fetch_pages(hot_urls, headers=PPOMPPU_HEADERS):
        if soup:
            _parse_hot_links(soup)
        if len(items) >= TARGET:
            break

    # TARGET 미만이면 자유게시판에서 댓글 많은 글로 보충
    if len(items) < TARGET:
        FREE_HEADERS = {**PC_HEADERS, "Referer": "https://www.ppomppu.co.kr/"}
        for soup in fetch_pages([
            f"https://ppomppu.co.kr/zboard/zboard.php?id=freeboard&page={page}"
            for page in range(1, 4)
        ], headers=FREE_HEADERS):
            if not soup:
                continue
            for tr in soup.select("tr.baseList"):
                a = tr.find("a", href=re.compile(r'view\.php\?id=freeboard&no=\d+'))
                if not a:
                    continue
                title = a.get_text(strip=True)
                title = re.sub(r'\s*\[\d+\]\s*$', '', title).strip()
                if not title or len(title) < 3:
                    continue
                reply_el = tr.select_one("td.baseList-reply, span.list_reply, font.list_reply")
                reply_count = 0
                if reply_el:
                    m = re.search(r'\d+', reply_el.get_text())
                    if m:
                        reply_count = int(m.group())
                if reply_count < 10:
                    continue
                href = a.get("href", "")
                if not href.startswith("http"):
                    href = "https://ppomppu.co.kr/zboard/" + href
                if title not in seen:
                    seen.add(title)
                    items.append({"rank": len(items) + 1, "title": title, "url": href})
            if len(items) >= TARGET:
                break

    return items[:TARGET]


def get_mlbpark():
    """MLB파크 불펜 게시글"""
    items = []
    seen = set()

    soups = fetch_pages([
        f"https://mlbpark.donga.com/mp/b.php?b=bullpen&page={page}"
        for page in range(1, 4)
    ], headers=PC_HEADERS)

    for soup in soups:
        if not soup:
            continue
        for a in soup.select("div.title a[href*='b=bullpen'][href*='id=']"):
            href = a.get("href", "")
            title = re.sub(r'\[\d+\]\s*$', '', a.get_text(strip=True)).strip()
            if not title or len(title) < 3 or title in seen:
                continue
            if not href.startswith("http"):
                href = "https://mlbpark.donga.com" + href
            seen.add(title)
            items.append({"rank": len(items) + 1, "title": title, "url": href})
        if len(items) >= TARGET:
            break

    return items[:TARGET]


SCRAPERS = {
    "inven": get_inven,
    "bobaedream": get_bobaedream,
    "todayhumor": get_todayhumor,
    "ruliweb": get_ruliweb,
    "ppomppu": get_ppomppu_hot,
    "theqoo": get_theqoo,
    "dcinside": get_dcinside,
    "mlbpark": get_mlbpark,
}
