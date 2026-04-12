import requests
from bs4 import BeautifulSoup, Tag
from datetime import date

PC_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://www.naver.com/",
}

MOBILE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Accept-Language": "ko-KR,ko;q=0.9",
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
    """네이트 연예 뉴스 일간 랭킹"""
    today = date.today().strftime("%Y%m%d")
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


def get_naver_section(section_url):
    """네이버 뉴스 섹션"""
    soup = fetch(section_url)
    if not soup:
        return []

    items = []
    seen = set()
    rank = 1

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if "naver.com" not in href or "article" not in href:
            continue

        title_el = a.select_one(".sa_text_strong, .cluster_text_headline, .tit")
        if title_el:
            title = title_el.get_text(strip=True)
        else:
            title = a.get_text(strip=True)

        if not title or len(title) < 6 or title in seen:
            continue

        seen.add(title)
        items.append({"rank": rank, "title": title, "url": href})
        rank += 1
        if rank > 50:
            break

    return items[:50]


def get_ruliweb_game():
    """루리웹 게임 뉴스"""
    soup = fetch("https://m.ruliweb.com/news/board/11", headers=MOBILE_HEADERS)
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

        # 제목: num_reply 클래스 제외하고 텍스트 수집
        title = ""
        for node in a.children:
            if isinstance(node, Tag):
                if "num_reply" not in node.get("class", []):
                    title += node.get_text(strip=True)
            else:
                title += str(node).strip()
        title = title.strip()

        if not title or len(title) < 3 or title in seen:
            continue

        if href and not href.startswith("http"):
            href = "https://m.ruliweb.com" + href
        href = href.split("?")[0]

        seen.add(title)
        items.append({"rank": rank, "title": title, "url": href})
        rank += 1
        if rank > 50:
            break

    return items[:50]


def get_naver_economy():
    return get_naver_section("https://news.naver.com/section/101")


def get_naver_society():
    return get_naver_section("https://news.naver.com/section/102")


def get_naver_world():
    return get_naver_section("https://news.naver.com/section/104")


def get_naver_it():
    return get_naver_section("https://news.naver.com/breakingnews/section/105/230")


NEWS_SCRAPERS = {
    "ent": get_nate_ent,
    "society": get_naver_society,
    "economy": get_naver_economy,
    "world": get_naver_world,
    "it": get_naver_it,
    "game": get_ruliweb_game,
}
