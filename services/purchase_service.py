"""구매 요청(PurchaseReq) 관련 로직: 요청 생성 / 목록 조회 / 승인 트랜잭션.

이 파일은 '구매 요청' 주제를 담당한다. 특히 승인(approve_request)은 여러 변경을
하나로 묶어 처리하는 트랜잭션이라, 이 프로젝트에서 가장 중요한 로직 중 하나다.
"""
from db import get_conn
from services import chat_service


def create_request(request_cno, seller_cno, item_no, req_price, req_message):
    """구매 요청 생성. 한 물품에 여러 사람이 각자 요청할 수 있다.

    (requestCno, cno, itemNo)가 복합 기본키이므로, 같은 사람이 같은 물품에
    다시 요청하면 무결성 위반(중복) 오류가 난다 → 호출한 쪽(app.py)에서
    그 오류를 잡아 "이미 요청함" 안내로 바꿔 준다.
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO PurchaseReq (requestCno, cno, itemNo, reqDateTime, reqPrice, reqMessage) "
            "VALUES (:rc, :cno, :ino, SYSTIMESTAMP, :price, :msg)",  # 요청 시각은 현재 시각
            {"rc": request_cno, "cno": seller_cno, "ino": item_no,
             "price": req_price, "msg": req_message},
        )


def requests_for_item(seller_cno, item_no):
    """판매자의 한 물품에 들어온 구매 요청 목록을 (요청자 닉네임 포함) 돌려준다."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT p.requestCno, c.nickname, p.reqPrice, p.reqMessage, p.reqDateTime "
            "FROM PurchaseReq p JOIN Customer c ON p.requestCno = c.cno "  # 요청자 닉네임 조인
            "WHERE p.cno = :cno AND p.itemNo = :ino "
            "ORDER BY p.reqDateTime",                                     # 먼저 온 요청부터
            {"cno": seller_cno, "ino": item_no},
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def my_requests(request_cno):
    """구매자가 보낸 요청 목록 + 그 물품의 현재 상태를 (최근 순으로) 돌려준다."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT p.cno, p.itemNo, i.title, p.reqPrice, p.reqDateTime, i.sellStatus "
            "FROM PurchaseReq p JOIN Item i "          # 물품 제목·상태를 함께 보기 위해 조인
            "  ON p.cno = i.cno AND p.itemNo = i.itemNo "
            "WHERE p.requestCno = :rc "
            "ORDER BY p.reqDateTime DESC",             # 최근 보낸 요청부터
            {"rc": request_cno},
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def approve_request(seller_cno, item_no, buyer_cno):
    """구매 요청 승인 — 세 가지 변경을 '하나의 트랜잭션'으로 처리한다.

    순서:
      1) 물품을 '예약 중'으로 바꾸고 예약 시각(resDateTime)을 지금으로 → 48시간 타이머 시작
      2) 승인되지 않은 '다른' 요청들을 모두 삭제(승인된 구매자의 요청은 이력으로 남김)
      3) 승인 구매자–판매자의 채팅방을 보장(없으면 만들고, 있으면 그대로 사용)
    중간에 하나라도 실패하면 get_conn 컨텍스트가 전체를 ROLLBACK 하므로,
    "절반만 처리되는" 상태가 생기지 않는다. 반환: 활성화된 채팅방 번호(roomNo).
    """
    with get_conn() as conn:
        cur = conn.cursor()

        # 1) 물품 상태 → 예약 중 (단, 지금 '판매 중'인 물품만 대상)
        cur.execute(
            "UPDATE Item SET sellStatus = '예약 중', resDateTime = SYSTIMESTAMP "
            "WHERE cno = :cno AND itemNo = :ino AND sellStatus = '판매 중'",
            {"cno": seller_cno, "ino": item_no},
        )
        # 바뀐 행이 1이 아니면 이미 예약/거래완료된 물품 → 예외로 중단(→ 전체 롤백)
        if cur.rowcount != 1:
            raise ValueError("판매 중 상태의 물품만 승인할 수 있습니다.")

        # 2) 승인된 구매자(:buyer) 외의 요청은 모두 삭제(<> 는 '같지 않음')
        cur.execute(
            "DELETE FROM PurchaseReq "
            "WHERE cno = :cno AND itemNo = :ino AND requestCno <> :buyer",
            {"cno": seller_cno, "ino": item_no, "buyer": buyer_cno},
        )

        # 3) 채팅방 보장 (UQ_ChatRoom: receiveCno+cno+itemNo 가 유일)
        #    구매자가 승인 전에 이미 '1:1 채팅하기'로 방을 열었다면 그 방을 그대로 활성화한다.
        #    같은 커서(트랜잭션)를 넘겨 호출하므로 위 변경들과 한 묶음으로 처리된다.
        return chat_service._ensure_room_cur(cur, buyer_cno, seller_cno, item_no)
