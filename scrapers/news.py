import requests
from bs4 import BeautifulSoup, Tag
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

PC_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://www.naver.com/",
}

MOBILE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Referer": "https://m.ruliweb.com/",
}


def fetch(url, headers=None, timeout=10):
    try:
        h = headers or PC_HEADERS
        r = requests.get(url, headers=h, timeout=timeout)
        r.raise_for_status()
        return BeautifulSoup(r.content, "lxml")
    except Exception as e:
        print(f"[fetch error] {url}: {e}")
        return None


def get_nate_ent():
    """네이트 연예 뉴스 일간 랭킹
    참조: NEWS_SCRAPERS["ent"] → app.py /api/news/ent → index.html data-source="ent"
    """
    today = datetime.now(KST).strftime("%Y%m%d")
    soup = fetch(f"https://news.nate.com/rank/interest?sc=ent&p=day&date={today}")
    if not soup:
        return []

    items = []
    seen = set()
    rank = 1

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if "news.nate.com/view/" not in href:
            continue

        title_el = a.select_one(".tit, .title, strong")
        if title_el:
            title = title_el.get_text(strip=True)
        else:
            full_text = a.get_text(separator="\n", strip=True)
            title = full_text.split("\n")[0].strip()

        if not title or len(title) < 5 or title in seen:
            continue

        if href.startswith("//"):
            href = "https:" + href
        elif not href.startswith("http"):
            href = "https://news.nate.com" + href
        href = href.split("?")[0]

        seen.add(title)
        items.append({"rank": rank, "title": title, "url": href})
        rank += 1
        if rank > 50:
            break

    return items[:50]


def _parse_minutes_ago(time_text: str) -> int | None:
    """상대 시간 텍스트를 분 단위로 변환. 오늘 기사가 아니면 None 반환."""
    t = time_text.strip()
    if "분전" in t or "분 전" in t:
        try:
            return int("".join(filter(str.isdigit, t)))
        except ValueError:
            return 0
    if "시간전" in t or "시간 전" in t:
        try:
            return int("".join(filter(str.isdigit, t))) * 60
        except ValueError:
            return 60
    # "04.13." 형식 → 오늘 날짜면 포함
    today_prefix = datetime.now(KST).strftime("%-m.%-d.")
    if t.startswith(today_prefix) or t == datetime.now(KST).strftime("%m.%d."):
        return 24 * 60
    # "방금", "금방" 등
    if t in ("방금", "금방"):
        return 0
    # 그 외(어제, N일 전, 날짜 등)는 제외
    return None


def get_naver_section(section_url):
    """네이버 뉴스 섹션 - 오늘 기사만, 최신순 정렬
    참조: get_naver_economy / get_naver_stocks / get_naver_realestate /
          get_naver_society / get_naver_world / get_naver_it 에서 호출
    """
    soup = fetch(section_url)
    if not soup:
        return []

    candidates = []
    seen = set()

    for item in soup.select(".sa_item._LAZY_LOADING_WRAP"):
        title_el = item.select_one(".sa_text_strong")
        date_el = item.select_one(".sa_text_datetime")
        a = item.select_one("a[href*='article']")

        if not title_el or not a:
            continue

        title = title_el.get_text(strip=True)
        href = a.get("href", "")

        if not title or len(title) < 6 or title in seen:
            continue

        minutes_ago = None
        if date_el:
            minutes_ago = _parse_minutes_ago(date_el.get_text(strip=True))
            if minutes_ago is None:
                continue  # 오늘 기사 아님

        seen.add(title)
        candidates.append({"title": title, "url": href, "_min": minutes_ago or 0})

    # 최신순 정렬 (minutes_ago 오름차순)
    candidates.sort(key=lambda x: x["_min"])

    return [
        {"rank": i + 1, "title": c["title"], "url": c["url"]}
        for i, c in enumerate(candidates[:50])
    ]


def get_ruliweb_game():
    """루리웹 게임 뉴스
    참조: NEWS_SCRAPERS["game"] → app.py /api/news/game → index.html data-source="game"
    """
    urls = [
        "https://m.ruliweb.com/news/523",
        "https://m.ruliweb.com/news/game",
    ]
    soup = None
    for url in urls:
        soup = fetch(url, headers=MOBILE_HEADERS)
        if soup:
            break
    if not soup:
        return []

    items = []
    seen = set()
    rank = 1

    for li in soup.select("li.list_item"):
        a = None
        for tag in li.find_all("a", href=True):
            h = tag.get("href", "")
            if "bbs.ruliweb.com" in h and "/read/" in h:
                a = tag
                break
        if not a:
            continue
        href = a.get("href", "")

        strong = a.select_one("strong")
        title = strong.get_text(strip=True) if strong else a.get_text(strip=True)

        if not title or len(title) < 3 or title in seen:
            continue

        if href.startswith("//"):
            href = "https:" + href

        seen.add(title)
        items.append({"rank": rank, "title": title, "url": href})
        rank += 1
        if rank > 50:
            break

    return items[:50]

# 참조: NEWS_SCRAPERS["economy"] → app.py /api/news/economy → index.html data-source="economy"
def get_naver_economy():
    return get_naver_section("https://news.naver.com/section/101")

def get_naver_stocks():
    return get_naver_section("https://news.naver.com/breakingnews/section/101/258")

def get_naver_realestate():
    return get_naver_section("https://news.naver.com/breakingnews/section/101/260")

def get_naver_society():
    return get_naver_section("https://news.naver.com/section/102")

def get_naver_world():
    return get_naver_section("https://news.naver.com/section/104")

def get_naver_it():
    return get_naver_section("https://news.naver.com/breakingnews/section/105/230")

def get_nate_sports():
    """네이트 스포츠 뉴스 일간 랭킹
    참조: NEWS_SCRAPERS["sports"] → app.py /api/news/sports → index.html data-source="sports"
    """
    today = datetime.now(KST).strftime("%Y%m%d")
    soup = fetch(f"https://news.nate.com/rank/interest?sc=spo&p=day&date={today}")
    if not soup:
        return []

    items = []
    seen = set()
    rank = 1

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if "nate.com/view/" not in href:
            continue

        title_el = a.select_one(".tit, .title, strong")
        if title_el:
            title = title_el.get_text(strip=True)
        else:
            title = a.get_text(separator="\n", strip=True).split("\n")[0].strip()

        if not title or len(title) < 5 or title in seen:
            continue

        if href.startswith("//"):
            href = "https:" + href
        elif not href.startswith("http"):
            href = "https://news.nate.com" + href
        href = href.split("?")[0]

        seen.add(title)
        items.append({"rank": rank, "title": title, "url": href})
        rank += 1
        if rank > 50:
            break

    return items[:50]


def _get_newstravel(sec_no):
    """뉴스트래블 섹션 기사 목록
    참조: get_newstravel_domestic(sec_no=9) / get_newstravel_overseas(sec_no=2) 에서 호출
    """
    soup = fetch(
        f"https://www.newstravel.co.kr/news/section_list_all.html?sec_no={sec_no}",
        headers={**PC_HEADERS, "Referer": "https://www.newstravel.co.kr/"},
    )
    if not soup:
        return []

    items = []
    seen = set()
    rank = 1

    for a in soup.find_all("a", href=lambda h: h and "article.html?no=" in h):
        h3 = a.find("h3")
        title = h3.get_text(strip=True) if h3 else a.get_text(strip=True).split("\n")[0].strip()

        if not title or len(title) < 5 or title in seen:
            continue

        href = a.get("href", "")
        if not href.startswith("http"):
            href = "https://www.newstravel.co.kr" + href

        seen.add(title)
        items.append({"rank": rank, "title": title, "url": href})
        rank += 1
        if rank > 50:
            break

    return items[:50]


def get_newstravel_domestic():
    # 참조: NEWS_SCRAPERS["domestic"] → app.py /api/news/domestic → index.html data-source="domestic"
    return _get_newstravel(9)


def get_newstravel_overseas():
    # 참조: NEWS_SCRAPERS["overseas"] → app.py /api/news/overseas → index.html data-source="overseas"
    return _get_newstravel(2)


# 참조: app.py api_news() → /api/news/<category>
NEWS_SCRAPERS = {
    "ent": get_nate_ent,
    "society": get_naver_society,
    "economy": get_naver_economy,
    "stocks": get_naver_stocks,
    "realestate": get_naver_realestate,
    "world": get_naver_world,
    "it": get_naver_it,
    "sports": get_nate_sports,
    "domestic": get_newstravel_domestic,
    "overseas": get_newstravel_overseas,
    "game": get_ruliweb_game,
}
