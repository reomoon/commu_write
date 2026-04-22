"""
수집 기능 단독 테스트 스크립트.
사용법: python test_collect.py [커뮤니티명]
예시:  python test_collect.py bobaedream
       python test_collect.py          (전체 6개 커뮤니티)
"""
import sys
import json
from datetime import datetime
from scrapers.community import SCRAPERS
from scrapers.post_scraper import scrape_post_images

TARGETS = ["bobaedream", "todayhumor", "ruliweb", "instiz", "ppomppu", "inven"]
LABELS  = {
    "bobaedream": "보배드림", "todayhumor": "오늘의유머",
    "ruliweb": "루리웹",    "instiz": "인스티즈",
    "ppomppu": "뽐뿌",     "inven": "인벤",
}

sources = [sys.argv[1]] if len(sys.argv) > 1 else TARGETS
date_str = datetime.now().strftime("%Y%m%d")

for source in sources:
    label = LABELS.get(source, source)
    print(f"\n{'='*50}")
    print(f"  {label} 수집 중...")
    print(f"{'='*50}")

    items = SCRAPERS[source]()[:5]
    for item in items:
        rank  = item["rank"]
        title = item["title"]
        url   = item["url"]
        print(f"\n  [{rank}위] {title}")
        print(f"        {url}")

        images = scrape_post_images(source, url, rank, date_str)
        if images:
            for img in images:
                local = img.get("local") or "(다운로드 실패)"
                print(f"        이미지: {local}")
        else:
            print(f"        이미지 없음")

print("\n\n수집 완료. static/collected_images/ 폴더를 확인하세요.")
