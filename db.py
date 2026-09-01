"""Oracle 연결 관리 모듈 (데이터 접근 계층).

이 파일은 "DB와 어떻게 연결하고, 트랜잭션을 어떻게 끊을지"를 한곳에서 책임진다.
서비스 계층(services/*)은 SQL 만 작성하고, 커밋·롤백·커넥션 반납 같은 뒤처리는
모두 여기의 get_conn() 에 맡긴다.

- python-oracledb 의 *thin 모드*를 쓰므로 Oracle Instant Client 설치가 필요 없다.
- 커넥션 풀을 한 번 만들어 두고, with 문으로 커넥션을 빌려 쓰도록 헬퍼를 제공한다.
"""
import contextlib

import oracledb

import config

# 모듈이 처음 import 될 때 딱 한 번 생성되는 커넥션 풀.
# 매 요청마다 새로 연결하면 느리므로, 미리 만들어 둔 연결을 빌려 쓰고 반납한다.
#   min=1  : 평소 최소 1개 유지   max=8  : 동시에 최대 8개까지 확장
#   increment=1 : 부족하면 1개씩 늘린다
_pool = oracledb.create_pool(
    user=config.DB_USER,
    password=config.DB_PASSWORD,
    dsn=config.DSN,
    min=1,
    max=8,
    increment=1,
)


@contextlib.contextmanager
def get_conn():
    """풀에서 커넥션을 하나 빌려주는 컨텍스트 매니저.

    `with get_conn() as conn:` 형태로 사용한다. with 블록을 빠져나갈 때:
      - 정상 종료하면  → commit  (변경 사항 확정)
      - 예외가 발생하면 → rollback (변경 사항 전부 취소) 후 예외를 다시 던짐
    어느 경우든 마지막에는 커넥션을 풀에 반납(release)한다.
    덕분에 서비스 코드는 트랜잭션 처리를 신경 쓰지 않아도 안전하게 동작한다.
    """
    conn = _pool.acquire()          # 풀에서 커넥션 빌리기
    try:
        yield conn                  # with 블록 안에서 이 커넥션을 사용
        conn.commit()               # 블록이 예외 없이 끝나면 확정
    except Exception:
        conn.rollback()             # 도중에 오류가 나면 전부 되돌림
        raise                       # 오류는 호출한 쪽으로 그대로 전달
    finally:
        _pool.release(conn)         # 성공/실패와 무관하게 반드시 반납


def query_all(sql, params=None):
    """읽기 전용(SELECT) 질의를 실행해 결과를 돌려주는 헬퍼.

    반환 형식: (컬럼명 리스트, 행 리스트) — 각 행은 {컬럼명: 값} 딕셔너리.
    바인드 변수(params)는 딕셔너리로 넘긴다. 통계·DB 덤프 화면에서 사용한다.
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, params or {})
        cols = [d[0] for d in cur.description]            # 커서 메타데이터에서 컬럼명 추출
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]  # 각 행을 dict 로 변환
        return cols, rows
