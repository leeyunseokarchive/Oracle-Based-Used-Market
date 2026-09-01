"""애플리케이션 설정 모듈.

이 파일은 앱 전체가 공유하는 설정값(DB 접속 정보·상수)을 한곳에 모아 둔다.
코드 여기저기에 흩어지기 쉬운 "매직값"(접속 주소, 관리자 번호, 만료 시간 등)을
이 파일에서만 관리하므로, 환경이 바뀌어도 여기만 고치면 된다.

DB 접속 정보는 모두 환경변수(TP_DB_*)로 덮어쓸 수 있다. 다만 데모 편의를 위해,
환경변수가 없을 때 쓰는 기본값은 docker-compose.yml 로 띄운 Oracle 23ai Free
컨테이너(사용자 tpuser / 서비스 FREEPDB1)에 맞춰 두었다.
"""
import os

# --- Oracle 접속 정보 (gvenzl/oracle-free 컨테이너 기준) ---
# os.getenv("키", "기본값") → 환경변수가 있으면 그 값을, 없으면 기본값을 쓴다.
DB_USER = os.getenv("TP_DB_USER", "tpuser")            # 앱 전용 스키마 계정
DB_PASSWORD = os.getenv("TP_DB_PASSWORD", "tppw")      # 위 계정의 비밀번호
DB_HOST = os.getenv("TP_DB_HOST", "localhost")         # DB 서버 주소
DB_PORT = int(os.getenv("TP_DB_PORT", "1521"))         # 리스너 포트(문자열 → 정수)
DB_SERVICE = os.getenv("TP_DB_SERVICE", "FREEPDB1")    # 23ai Free 기본 PDB 이름

# oracledb thin 모드가 쓰는 접속 문자열(DSN). 형식: "호스트:포트/서비스명"
# 예) localhost:1521/FREEPDB1
DSN = f"{DB_HOST}:{DB_PORT}/{DB_SERVICE}"

# --- 애플리케이션 상수 ---
ADMIN_CNO = "c0"                  # 관리자(통계·DB 조회 권한)로 취급할 회원번호
RESERVE_TIMEOUT_HOURS = 48        # 예약(거래 대기)이 이 시간을 넘기면 자동 취소
SECRET_KEY = os.getenv("TP_SECRET_KEY", "tp7-demo-secret")  # Flask 세션 서명용 키
