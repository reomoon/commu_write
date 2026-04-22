"""
커뮤니티 게시글 본문에서 이미지를 추출하고 로컬에 저장하는 모듈.
static/collected_images/YYYYMMDD/source/ 아래에 저장됨.
"""
import os
import re
import time
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
IMAGES_ROOT = os.path.join(STATIC_DIR, "collected_images")

# 커뮤니티별 본문 CSS 셀렉터 (우선순위 순 — 실제 HTML 구조 확인 후 확정)
CONTENT_SELECTORS = {
    "bobaedream":  [".article-body"],
    "todayhumor":  [".viewContent"],
    "ruliweb":     [".view_content"],
    "instiz":      [".memo_content"],
    "ppomppu":     ["table.pic_bg"],
    "inven":       ["#BBSImageHolderTop", ".bbs-con.articleContent"],
}

PC_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9",
}
MOBILE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9",
}


def _headers_for(source):
    if source in ("bobaedream", "inven"):
        return MOBILE_HEADERS
    return PC_HEADERS


def _soup_for(source, url):
    headers = _headers_for(source).copy()
    headers["Referer"] = url
    try:
        resp = requests.get(url, headers=headers, timeout=12, allow_redirects=True)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        print(f"[post_scraper] fetch failed {url}: {e}")
        return None


def _extract_img_urls(soup, source, base_url):
    """본문 영역에서 이미지 URL 목록을 추출."""
    selectors = CONTENT_SELECTORS.get(source, [])
    container = None
    for sel in selectors:
        container = soup.select_one(sel)
        if container:
            break

    # 셀렉터 미적중 시 가장 img가 많은 div로 폴백
    if container is None:
        candidates = soup.find_all(["div", "article", "section"])
        if candidates:
            container = max(candidates, key=lambda el: len(el.find_all("img")))

    if container is None:
        return []

    imgs = container.find_all("img")
    urls = []
    for img in imgs:
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

        # 너무 작은 이미지(아이콘/이모지) 필터링
        try:
            if int(img.get("width", 9999)) < 80:
                continue
            if int(img.get("height", 9999)) < 80:
                continue
        except (ValueError, TypeError):
            pass

        urls.append(src)

    return list(dict.fromkeys(urls))  # 중복 제거 (순서 유지)


def _ext_from_url(url):
    path = urlparse(url).path.lower().split("?")[0]
    for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
        if path.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    return ".jpg"


def _download_one(url, filepath, referer):
    headers = PC_HEADERS.copy()
    headers["Referer"] = referer
    resp = requests.get(url, headers=headers, timeout=15, stream=True)
    resp.raise_for_status()
    ct = resp.headers.get("content-type", "")
    if "image" not in ct and "octet" not in ct:
        # URL에 이미지 확장자가 있으면 그냥 저장 시도
        ext = _ext_from_url(url)
        if ext not in (".jpg", ".png", ".gif", ".webp"):
            return False
    with open(filepath, "wb") as f:
        for chunk in resp.iter_content(8192):
            f.write(chunk)
    return True


def scrape_post_images(source, post_url, rank, date_str, max_images=5):
    """
    게시글 본문의 이미지를 다운로드하고 결과를 반환.

    Returns:
        list[dict]: [{"local": "collected_images/DATE/src/file.jpg", "original": "https://..."}, ...]
    """
    soup = _soup_for(source, post_url)
    if soup is None:
        return []

    img_urls = _extract_img_urls(soup, source, post_url)
    if not img_urls:
        return []

    save_dir = os.path.join(IMAGES_ROOT, date_str, source)
    os.makedirs(save_dir, exist_ok=True)

    results = []
    for i, url in enumerate(img_urls[:max_images], 1):
        ext = _ext_from_url(url)
        filename = f"rank{rank}_img{i}{ext}"
        filepath = os.path.join(save_dir, filename)
        local_rel = f"collected_images/{date_str}/{source}/{filename}"

        if os.path.exists(filepath):
            results.append({"local": local_rel, "original": url})
            continue

        try:
            ok = _download_one(url, filepath, post_url)
            if ok:
                results.append({"local": local_rel, "original": url})
        except Exception as e:
            print(f"[post_scraper] download failed {url}: {e}")
            # 다운로드 실패해도 원본 URL은 보존
            results.append({"local": None, "original": url})

        time.sleep(0.3)

    return results
