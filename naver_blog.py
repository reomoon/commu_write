"""
네이버 블로그 OAuth2 인증 및 글쓰기 API 래퍼.

환경변수 설정 필요:
  NAVER_CLIENT_ID     - 네이버 개발자센터 애플리케이션 Client ID
  NAVER_CLIENT_SECRET - 네이버 개발자센터 애플리케이션 Client Secret
  NAVER_CALLBACK_URL  - 콜백 URL (예: http://localhost:5000/api/blog/naver/callback)
  SERVER_BASE_URL     - 이미지 공개 URL 기준 (예: https://your-app.railway.app)

네이버 개발자센터: https://developers.naver.com
  → 애플리케이션 등록 → API 권한에서 "블로그" 체크
  → 로그인 오픈 API 서비스 환경: PC 웹, 콜백 URL 등록
"""
import json
import os
import secrets
import urllib.parse

import requests

CLIENT_ID     = os.environ.get("NAVER_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "")
CALLBACK_URL  = os.environ.get("NAVER_CALLBACK_URL", "http://localhost:5000/api/blog/naver/callback")
SERVER_BASE   = os.environ.get("SERVER_BASE_URL", "").rstrip("/")

AUTH_URL  = "https://nid.naver.com/oauth2.0/authorize"
TOKEN_URL = "https://nid.naver.com/oauth2.0/token"
POST_API  = "https://openapi.naver.com/v1/blog/post.json"

SOURCE_LABELS = {
    "bobaedream": "보배드림",
    "todayhumor": "오늘의유머",
    "ruliweb": "루리웹",
    "instiz": "인스티즈",
    "ppomppu": "뽐뿌",
    "inven": "인벤",
}


def get_auth_url():
    """OAuth2 인증 시작 URL과 state 값을 반환."""
    if not CLIENT_ID:
        raise RuntimeError("NAVER_CLIENT_ID 환경변수가 설정되지 않았습니다.")
    state = secrets.token_urlsafe(16)
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": CALLBACK_URL,
        "state": state,
    }
    return AUTH_URL + "?" + urllib.parse.urlencode(params), state


def exchange_code(code, state, expected_state):
    """인증 코드를 액세스 토큰으로 교환."""
    if state != expected_state:
        raise ValueError("OAuth state 불일치 — CSRF 가능성")
    if not CLIENT_ID or not CLIENT_SECRET:
        raise RuntimeError("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 미설정")

    resp = requests.get(
        TOKEN_URL,
        params={
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "state": state,
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"토큰 교환 실패: {data.get('error_description', data['error'])}")
    return data  # access_token, refresh_token, token_type, expires_in


def _image_url(image_info):
    """
    로컬 경로가 있고 SERVER_BASE_URL이 설정된 경우 공개 URL 반환.
    그렇지 않으면 원본 URL 반환.
    """
    local = image_info.get("local")
    original = image_info.get("original", "")
    if local and SERVER_BASE:
        return f"{SERVER_BASE}/static/{local}"
    return original


def build_blog_html(post):
    """
    블로그 본문 HTML 생성.
    구조: 커뮤니티명 + 제목 → 이미지 나열 → 출처 링크
    """
    source_label = SOURCE_LABELS.get(post.get("source", ""), post.get("source", ""))
    title = post.get("title", "")
    url = post.get("url", "")
    images = post.get("images", [])

    lines = [
        f"<p><strong>[{source_label}]</strong></p>",
        f"<p><strong>{title}</strong></p>",
        "<br>",
    ]

    for img in images:
        img_url = _image_url(img)
        if img_url:
            lines.append(f'<img src="{img_url}" style="max-width:100%"><br>')

    lines += [
        "<br>",
        f'<p>출처: <a href="{url}" target="_blank">{source_label}</a></p>',
    ]
    return "\n".join(lines)


def post_to_naver_blog(access_token, post):
    """
    단일 게시글을 네이버 블로그에 발행.

    Returns:
        dict: {"ok": True, "postNo": ..., "blogId": ...}
              또는 {"ok": False, "error": "..."}
    """
    title    = post.get("title", "제목 없음")
    contents = build_blog_html(post)
    source   = post.get("source", "")
    tag      = SOURCE_LABELS.get(source, source)

    resp = requests.post(
        POST_API,
        headers={"Authorization": f"Bearer {access_token}"},
        data={
            "title": title,
            "contents": contents,
            "tags": tag,
            "allowComment": "Y",
        },
        timeout=15,
    )

    try:
        data = resp.json()
    except Exception:
        return {"ok": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}

    if resp.status_code != 200 or data.get("resultCode") not in ("00", "200"):
        msg = data.get("message") or data.get("errorMessage") or str(data)
        return {"ok": False, "error": msg}

    result = data.get("result", {})
    return {"ok": True, "postNo": result.get("postNo"), "blogId": result.get("blogId")}
