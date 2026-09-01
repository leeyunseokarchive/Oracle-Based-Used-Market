# 🛒 중고마켓 (Used Market)

Oracle 기반 온라인 중고거래 플랫폼. 조건 검색, 물품 등록, 구매 요청, 1:1 채팅, 거래 승인/완료, 관리자 통계를 갖춘 Flask 풀스택 웹 애플리케이션입니다.

- **언어/웹**: Python 3.8+ · Flask 3.x · Jinja2
- **DB**: Oracle Database 23ai Free (python-oracledb thin 모드)
- **인프라**: Docker / Docker Compose

---

## ✨ 주요 기능

| 기능 | 설명 |
|------|------|
| 로그인 & 권한 구분 | 일반 회원 / 관리자 권한 분리, 세션 기반 인증 |
| 물품 등록 | 사진 최대 3장 업로드, 카테고리 분류, 입력값 검증 |
| 조건 검색 | 키워드 AND / OR / NOT 조합 검색 + 가격·날짜 정렬 (동적 SQL 생성) |
| 구매 요청 | 한 물품에 여러 구매자가 동시 요청 가능 |
| 1:1 채팅 | 판매자-구매자 채팅방, 안 읽은 메시지 배지 표시 |
| 거래 승인/완료 | 요청 승인 → '예약 중' → 거래 완료 상태 전이 (트랜잭션 보장) |
| 예약 자동 취소 | 48시간 초과 예약을 lazy 방식으로 자동 복구 (스케줄러 불필요) |
| 관리자 통계 | 카테고리별 판매 현황·거래 통계 (GROUP BY 집계) |

## 📸 스크린샷

| 검색 홈 | 물품 상세 (사진 3장) |
|---|---|
| ![검색 홈](docs/f1_search_home.png) | ![물품 상세](docs/f2_detail_3pics.png) |

| AND/OR/NOT 조합 검색 | 1:1 채팅 (읽음 표시) |
|---|---|
| ![조합 검색](docs/f3_search_combo_sql.png) | ![채팅](docs/f5_chat_room.png) |

| 거래 승인 → 예약 중 | 관리자 통계 |
|---|---|
| ![승인](docs/f6_after_approve_reserved.png) | ![통계](docs/f9_stats.png) |

> 설계·구현 상세(스키마, 모듈별 알고리즘, 요청 처리 흐름)은 [REPORT.md](./REPORT.md) 참고.

---

## 🚀 실행 방법

> 사전 준비: Docker(또는 colima), Python 3.8+

### 1. Oracle 서버 열기

`docker-compose.yml`로 Oracle 23ai Free 컨테이너를 띄웁니다.

```bash
docker compose up -d
```

- 접속 정보: `localhost:1521` / 서비스명 `FREEPDB1`
- 앱 계정: `tpuser` / `tppw`
- 처음 기동은 DB 초기화로 1~2분 걸릴 수 있습니다. 아래 명령으로 준비 완료(`healthy`)를 확인하세요.

```bash
docker compose ps          # STATUS가 healthy 가 될 때까지 대기
```

컨테이너를 끌 때는 `docker compose down`, 데이터까지 지우려면 `docker compose down -v`.

### 2. 가상환경 + 의존성 설치

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

### 3. 스키마 + 시드 데이터 적재

```bash
.venv/bin/python init_db.py
```

### 4. 앱 실행

```bash
.venv/bin/python app.py
```

브라우저에서 **http://127.0.0.1:5001** 접속.

> macOS 는 5000 번 포트를 AirPlay 수신기가 점유하므로 기본 포트를 5001 로 둔다.
> 다른 포트로 띄우려면 `TP_PORT=8000 .venv/bin/python app.py` 처럼 지정한다.

---

## 🧪 테스트 계정

| 역할 | 회원번호 | 비밀번호 |
|---|---|---|
| 일반 회원 | `C1` ~ `C5` | `pw1` ~ `pw5` |
| 관리자 | `c0` | `admin` |
