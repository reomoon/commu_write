"""
커뮤니티 게시글 본문에서 이미지 URL을 추출한다 (서버 저장 없음).
모바일에서 원본 URL로 직접 다운로드하는 방식으로 사용.
"""
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup

CONTENT_SELECTORS = {
    "bobaedream": [".article-body"],
    "todayhumor": [".viewContent"],
    "ruliweb":    [".view_content"],
    "instiz":     [".memo_content"],
    "inven":      ["#BBSImageHolderTop", ".bbs-con.articleContent"],
    "fmkorea":    [".xe_content", ".rd_body"],
}

PC_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
}
MOBILE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Accept-Language": "ko-KR,ko;q=0.9",
}


def _fetch_soup(source, url):
    headers = (MOBILE_HEADERS if source in ("bobaedream", "inven") else PC_HEADERS).copy()
    headers["Referer"] = url
    try:
        resp = requests.get(url, headers=headers, timeout=12, allow_redirects=True)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        print(f"[post_scraper] fetch failed {url}: {e}")
        return None


def _extract_img_urls(soup, source, base_url, max_images):
    selectors = CONTENT_SELECTORS.get(source, [])
    container = None
    for sel in selectors:
        container = soup.select_one(sel)
        if container:
            break

    if container is None:
        candidates = soup.find_all(["div", "article", "section"])
        if candidates:
            container = max(candidates, key=lambda el: len(el.find_all("img")))

    if container is None:
        return []

    urls = []
    for img in container.find_all("img"):
        src = (
            img.get("src")
            or img.get("data-src")
            or img.get("data-original")
            or img.get("data-lazy")
        )
        if not src:
            continue
        src = src.strip()
        if src.startswith("data:"):
            continue
        if src.startswith("//"):
            src = "https:" + src
        elif not src.startswith("http"):
            src = urljoin(base_url, src)

        try:
            if int(img.get("width", 9999)) < 80 or int(img.get("height", 9999)) < 80:
                continue
        except (ValueError, TypeError):
            pass

        urls.append(src)
        if len(urls) >= max_images:
            break

    return list(dict.fromkeys(urls))


def scrape_post_images(source, post_url, max_images=5):
    """게시글 본문 이미지 URL 목록 반환 (서버 저장 없음)."""
    soup = _fetch_soup(source, post_url)
    if soup is None:
        return []

    urls = _extract_img_urls(soup, source, post_url, max_images)
    return [{"local": None, "original": url} for url in urls]
