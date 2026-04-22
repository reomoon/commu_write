# 블로그 자동 발행 설정 가이드

## 1. 네이버 개발자센터 앱 등록

1. https://developers.naver.com 접속 → 로그인
2. **Application → 애플리케이션 등록**
3. 사용 API: **블로그** 체크
4. 로그인 오픈 API 서비스 환경: **PC 웹** 선택
5. 서비스 URL: `http://localhost:5000` (개발) 또는 Railway 앱 URL
6. Callback URL: `http://localhost:5000/api/blog/naver/callback` (개발용)
   - Railway 배포 시: `https://your-app.railway.app/api/blog/naver/callback`
7. 등록 후 **Client ID**, **Client Secret** 복사

---

## 2. 환경변수 설정

`.env` 파일을 프로젝트 루트에 생성:

```
NAVER_CLIENT_ID=여기에_Client_ID_입력
NAVER_CLIENT_SECRET=여기에_Client_Secret_입력
NAVER_CALLBACK_URL=http://localhost:5000/api/blog/naver/callback
FLASK_SECRET_KEY=랜덤한_긴_문자열_입력

# Railway 배포 시 이미지 공개 URL (없으면 원본 커뮤니티 이미지 URL 사용)
# SERVER_BASE_URL=https://your-app.railway.app
```

Railway에서는 환경변수 탭에 위 항목들을 직접 입력합니다.

---

## 3. 패키지 설치 및 실행

```bash
pip install -r requirements.txt
python app.py
```

---

## 4. 사용 방법

1. 브라우저에서 `http://localhost:5000/blog-admin` 접속
2. **지금 수집** 버튼으로 즉시 데이터 수집 (1~2분 소요)
   - 이후에는 매일 **00:00 / 06:00 / 12:00 / 18:00 KST** 자동 수집
3. 수집 회차 드롭다운에서 원하는 시간대 선택
4. 보배드림 / 오늘의유머 / 루리웹 / 인스티즈 / 뽐뿌 / 인벤 1~5위 게시글 확인
5. 원하는 글 체크박스 선택
6. **네이버 로그인** 버튼 클릭 → 네이버 인증 완료
7. **네이버 블로그 발행** 버튼 클릭

---

## 5. 블로그 발행 내용 구조

```
제목: [커뮤니티 게시글 제목]

본문:
[보배드림] (또는 해당 커뮤니티명)
[게시글 제목]

[이미지 1]
[이미지 2]
...

출처: 보배드림 (링크)
```

---

## 6. 주의사항

- **Vercel 배포 시**: 자동 스케줄러와 이미지 저장이 동작하지 않습니다.
  Railway 또는 로컬 서버에서 실행해야 합니다.
- 이미지가 없는 게시글(텍스트만 있는 경우)은 이미지 없음으로 표시됩니다.
- 커뮤니티 사이트의 구조 변경 시 이미지 추출이 실패할 수 있습니다.
- 네이버 블로그 API는 하루 발행 횟수 제한이 있을 수 있습니다.
