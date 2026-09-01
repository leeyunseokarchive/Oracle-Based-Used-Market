# 🛒 중고마켓 (Used Market)

Oracle 기반 온라인 중고거래 플랫폼. 조건 검색, 물품 등록, 구매 요청, 1:1 채팅, 거래 승인/완료, 관리자 통계를 갖춘 Flask 풀스택 웹 애플리케이션입니다.

- **언어/웹**: Python 3.8+ · Flask 3.x · Jinja2
- **DB**: Oracle Database 23ai Free (python-oracledb thin 모드)
- **인프라**: Docker / Docker Compose

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
