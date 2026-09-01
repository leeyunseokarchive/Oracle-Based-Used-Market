"""회원(Customer) 관련 로직: 로그인, 닉네임 조회.

이 파일은 '회원' 한 가지 주제만 담당한다. 비밀번호 등 사용자 입력은 모두
바인드 변수(:cno, :pw)로 넘겨 SQL 인젝션을 막는다.
"""
from db import get_conn


def login(cno, passwd):
    """회원번호+비밀번호로 로그인 확인.

    입력: 회원번호(cno), 비밀번호(passwd)
    출력: 일치하는 회원이 있으면 {cno, nickname, region} 딕셔너리, 없으면 None.
    """
    with get_conn() as conn:                 # DB 커넥션 빌리기(끝나면 자동 정리)
        cur = conn.cursor()
        cur.execute(
            "SELECT cno, nickname, region FROM Customer "
            "WHERE cno = :cno AND passwd = :pw",
            {"cno": cno, "pw": passwd},        # 값은 바인드 변수로만 전달
        )
        row = cur.fetchone()                  # 일치하는 회원 1줄(없으면 None)
        if not row:
            return None                       # 아이디·비번 불일치
        return {"cno": row[0], "nickname": row[1], "region": row[2]}


def get_nickname(cno):
    """회원번호로 닉네임을 찾아 준다(해당 회원이 없으면 회원번호를 그대로 돌려줌)."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT nickname FROM Customer WHERE cno = :cno", {"cno": cno})
        row = cur.fetchone()
        return row[0] if row else cno
