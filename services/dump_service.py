"""DB 테이블 전체 내용 출력 — 보고서 7-1(구축된 DB의 각 테이블 내용)용.

관리자 'DB 내용' 화면에서, 5개 테이블의 실제 적재 행을 그대로 보여 주기 위한 파일이다.
사진처럼 큰 BLOB 값은 화면이 무거워지지 않도록 길이만 표시한다.
"""
from db import get_conn

# 출력할 테이블 순서(부모 → 자식 순으로 보기 좋게 나열).
TABLES = ("Customer", "Item", "PurchaseReq", "ChatRoom", "Message")
# 실제 값 대신 '길이'만 표시할 BLOB(사진) 컬럼들. (컬럼명은 대문자로 들어온다.)
_BLOB_COLS = {"PIC1", "PIC2", "PIC3"}


def dump_all():
    """모든 테이블의 내용을 [{table, columns, rows}, ...] 형태로 모아 돌려준다.

    각 BLOB 셀은 '<BLOB n바이트>'(없으면 빈 칸)로 바꿔, 화면에 바이너리가 쏟아지지 않게 한다.
    """
    result = []
    with get_conn() as conn:
        cur = conn.cursor()
        for t in TABLES:                       # 테이블 하나씩
            cur.execute(f"SELECT * FROM {t}")  # 전체 행 조회
            cols = [d[0] for d in cur.description]   # 컬럼명들
            rows = []
            for r in cur.fetchall():           # 행 하나씩
                cells = []
                for col, val in zip(cols, r):  # 셀(컬럼, 값) 하나씩
                    if col in _BLOB_COLS:
                        # 사진 컬럼: 값이 있으면 바이트 길이만, 없으면 빈 칸
                        cells.append(f"<BLOB {len(val.read())}B>" if val is not None else "")
                    else:
                        cells.append(val)      # 일반 컬럼: 값 그대로
                rows.append(cells)
            result.append({"table": t, "columns": cols, "rows": rows})
    return result
