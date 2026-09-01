"""채팅(ChatRoom/Message) 관련 로직: 방 보장 / 목록·안읽은 수 / 메시지 송수신 / 읽음 처리.

핵심 개념: 한 회원은 방마다 역할이 달라진다.
- ChatRoom.cno == 나        → 나는 그 방의 '판매자'(role 'S'), 상대가 보낸 메시지는 sender='B'
- ChatRoom.receiveCno == 나 → 나는 그 방의 '구매자'(role 'B'), 상대가 보낸 메시지는 sender='S'
그래서 '안 읽은 메시지'는 '상대가 보냈고 아직 isRead='N''인 메시지를 뜻한다.
"""
from db import get_conn


def _role_in_room(room, my_cno):
    """이 방에서 내 역할을 판정한다. 내가 판매자면 'S', 아니면(구매자면) 'B'."""
    return "S" if room["CNO"] == my_cno else "B"


def _ensure_room_cur(cur, buyer_cno, seller_cno, item_no):
    """(같은 트랜잭션의 커서를 받아) 구매자-판매자-물품 채팅방이 '있도록 보장'한다.

    UQ_ChatRoom(receiveCno, cno, itemNo) 제약 덕분에 물품당 (구매자,판매자) 방은 1개뿐이다.
    이미 있으면 그 방 번호를, 없으면 새로 INSERT 하고 그 번호를 돌려준다(=멱등).
    승인 트랜잭션 안에서도 같은 커서로 호출되어 한 묶음으로 처리된다.
    """
    # 먼저 같은 방이 이미 있는지 찾는다.
    cur.execute(
        "SELECT roomNo FROM ChatRoom "
        "WHERE receiveCno = :buyer AND cno = :cno AND itemNo = :ino",
        {"buyer": buyer_cno, "cno": seller_cno, "ino": item_no},
    )
    row = cur.fetchone()
    if row:
        return row[0]                 # 있으면 그 방 번호 그대로 반환
    # 없으면 새 방을 만들고, 자동 생성된 방 번호(roomNo)를 RETURNING 으로 돌려받는다.
    room_var = cur.var(int)           # RETURNING 값을 담을 변수
    cur.execute(
        "INSERT INTO ChatRoom (receiveCno, createDateTime, cno, itemNo) "
        "VALUES (:buyer, SYSTIMESTAMP, :cno, :ino) "
        "RETURNING roomNo INTO :rn",
        {"buyer": buyer_cno, "cno": seller_cno, "ino": item_no, "rn": room_var},
    )
    return room_var.getvalue()[0]     # 새로 만든 방 번호


def ensure_room(buyer_cno, seller_cno, item_no):
    """채팅방 보장(없으면 생성). 구매자가 상세 화면에서 '1:1 채팅하기'를 누를 때 사용.

    위 _ensure_room_cur 를 독립 트랜잭션으로 감싼 버전이다.
    """
    with get_conn() as conn:
        cur = conn.cursor()
        return _ensure_room_cur(cur, buyer_cno, seller_cno, item_no)


def list_rooms(my_cno):
    """내가 참여한 모든 채팅방 목록을 돌려준다.

    각 방마다 상대 닉네임(partner)·물품 제목·내 역할(role)과 함께,
    '상대가 보냈는데 내가 아직 안 읽은 메시지 수'(unread)를 계산해 붙인다(배지 표시용).
    """
    with get_conn() as conn:
        cur = conn.cursor()
        # 내가 판매자(r.cno)이거나 구매자(r.receiveCno)인 방을 모두 가져온다.
        cur.execute(
            "SELECT r.roomNo, r.receiveCno, r.cno, r.itemNo, i.title, "
            "       buyer.nickname AS buyer_nick, seller.nickname AS seller_nick "
            "FROM ChatRoom r "
            "  JOIN Item i      ON r.cno = i.cno AND r.itemNo = i.itemNo "
            "  JOIN Customer buyer  ON r.receiveCno = buyer.cno "    # 구매자 닉네임
            "  JOIN Customer seller ON r.cno = seller.cno "          # 판매자 닉네임
            "WHERE r.cno = :me OR r.receiveCno = :me "
            "ORDER BY r.roomNo",
            {"me": my_cno},
        )
        cols = [d[0] for d in cur.description]
        rooms = [dict(zip(cols, r)) for r in cur.fetchall()]

        # 방마다 내 역할과 안 읽은 메시지 수를 추가로 계산한다.
        for room in rooms:
            role = _role_in_room(room, my_cno)          # 이 방에서 내 역할
            other_sender = "B" if role == "S" else "S"  # 상대가 보낸 메시지의 sender 코드
            room["role"] = role
            room["partner"] = room["BUYER_NICK"] if role == "S" else room["SELLER_NICK"]
            # 안 읽은 메시지 수 = 상대가 보냈고(sender=상대) 아직 안 읽은(isRead='N') 것
            cur.execute(
                "SELECT COUNT(*) FROM Message "
                "WHERE roomNo = :rn AND sender = :s AND isRead = 'N'",
                {"rn": room["ROOMNO"], "s": other_sender},
            )
            room["unread"] = cur.fetchone()[0]
        return rooms


def get_room(room_no, my_cno):
    """방 1건의 정보 + 내 역할을 돌려준다. 내가 이 방의 당사자가 아니면 None(접근 차단)."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT r.roomNo, r.receiveCno, r.cno, r.itemNo, i.title, i.sellStatus, "
            "       buyer.nickname, seller.nickname "
            "FROM ChatRoom r "
            "  JOIN Item i ON r.cno = i.cno AND r.itemNo = i.itemNo "
            "  JOIN Customer buyer  ON r.receiveCno = buyer.cno "
            "  JOIN Customer seller ON r.cno = seller.cno "
            "WHERE r.roomNo = :rn",
            {"rn": room_no},
        )
        row = cur.fetchone()
        if not row:
            return None                                  # 없는 방
        room = {"ROOMNO": row[0], "RECEIVECNO": row[1], "CNO": row[2], "ITEMNO": row[3],
                "title": row[4], "sellStatus": row[5], "buyer_nick": row[6], "seller_nick": row[7]}
        # 내 번호가 판매자도 구매자도 아니면 이 방의 당사자가 아니다 → 접근 거부
        if my_cno not in (room["CNO"], room["RECEIVECNO"]):
            return None  # 이 방의 당사자가 아님
        room["role"] = _role_in_room(room, my_cno)
        room["partner"] = room["buyer_nick"] if room["role"] == "S" else room["seller_nick"]
        return room


def get_messages(room_no):
    """방의 모든 메시지를 보낸 순서(seqNo)대로 돌려준다."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT seqNo, sender, content, sentDateTime, isRead "
            "FROM Message WHERE roomNo = :rn ORDER BY seqNo",
            {"rn": room_no},
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def send_message(room_no, role, content):
    """메시지 전송. 보낸 사람(sender)은 내 역할(role 'S'/'B')이고, 처음엔 안 읽음('N')."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO Message (roomNo, sender, sentDateTime, content, isRead) "
            "VALUES (:rn, :s, SYSTIMESTAMP, :c, 'N')",
            {"rn": room_no, "s": role, "c": content[:2000]},   # 내용은 최대 2000자
        )


def mark_read(room_no, my_role):
    """내가 방에 들어오면, 상대가 보낸 '안 읽은' 메시지를 모두 '읽음'으로 바꾼다."""
    other_sender = "B" if my_role == "S" else "S"   # 상대가 보낸 메시지의 sender 코드
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE Message SET isRead = 'Y' "
            "WHERE roomNo = :rn AND sender = :s AND isRead = 'N'",
            {"rn": room_no, "s": other_sender},
        )
        return cur.rowcount   # 읽음으로 바뀐 메시지 수
