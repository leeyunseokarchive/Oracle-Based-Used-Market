"""물품(Item) 관련 로직: 등록 / 조건 검색(AND·OR·NOT) / 상세 / 상태 전이 / 48h 만료.

이 파일은 물품과 관련된 모든 DB 작업을 모아 둔, 서비스 계층에서 가장 큰 모듈이다.
검색·등록·삭제·거래완료·예약만료 같은 기능이 함수 하나씩으로 나뉘어 있다.
"""
from db import get_conn
import config

# 물품 상태 3종과 카테고리 5종(드롭다운·상태 배지 색에 쓰인다).
SELL_STATUSES = ("판매 중", "예약 중", "거래 완료")
CATEGORIES = ("전자기기", "의류", "도서", "생활용품", "가구")


def expire_reservations():
    """48시간이 지난 '예약 중' 물품을 '판매 중'으로 자동 복귀시킨다.

    별도 스케줄러 없이, 화면을 조회하기 직전에 호출하는 'lazy(게으른)' 방식이다.
    예약 시각(resDateTime)으로부터 48시간(config 값)이 지난 물품에 대해
      (1) 그 물품에 남아 있던 구매 요청(승인됐던 예약 포함)을 삭제하고
      (2) 물품 상태를 '판매 중'으로 되돌리며 resDateTime 을 비운다.
    (1)·(2)는 한 트랜잭션으로 처리된다. 복귀된 물품 수를 반환한다.
    """
    # '만료 조건'을 문자열로 한 번 정의해 아래 두 SQL 에서 재사용한다.
    # 뜻: 예약 중이고, 예약 시각이 있고, 지금이 예약 시각보다 :h 시간 넘게 지났다.
    expired = (
        "sellStatus = '예약 중' "
        "AND resDateTime IS NOT NULL "
        "AND SYSTIMESTAMP - resDateTime > NUMTODSINTERVAL(:h, 'HOUR')"
    )
    with get_conn() as conn:
        cur = conn.cursor()
        # 1) 만료 대상 물품에 남은 구매 요청(승인됐던 예약 포함) 삭제
        cur.execute(
            "DELETE FROM PurchaseReq pr "
            f"WHERE EXISTS (SELECT 1 FROM Item i "
            f"              WHERE i.cno = pr.cno AND i.itemNo = pr.itemNo AND {expired})",
            {"h": config.RESERVE_TIMEOUT_HOURS},
        )
        # 2) 물품 상태 '판매 중'으로 복귀(예약 시각도 비움)
        cur.execute(
            f"UPDATE Item SET sellStatus = '판매 중', resDateTime = NULL WHERE {expired}",
            {"h": config.RESERVE_TIMEOUT_HOURS},
        )
        return cur.rowcount   # 마지막 UPDATE 로 바뀐(복귀된) 물품 수


def search(conditions, connector="AND", sort="recent"):
    """조건 검색 — 화면에서 고른 조건들을 SQL 로 조립해 결과와 실행 SQL 을 함께 돌려준다.

    conditions: [{'field': 'title'|'category'|'price', ..., 'negate': bool}, ...]
    connector : 조건들을 묶는 논리 연산자 'AND'(모두 만족) | 'OR'(하나라도)
    sort      : 'recent'(최신순) | 'price_asc'(가격↑) | 'price_desc'(가격↓)

    동작 방식: 각 조건을 '술어(predicate)' 한 조각으로 만들어 리스트에 모은 뒤,
    사용자가 고른 연산자(AND/OR)로 이어 붙인다. NOT 체크는 술어 앞에 'NOT'을 붙여
    표현한다. 검색어·가격 같은 값은 전부 바인드 변수(:t0, :lo1 …)로만 전달하므로
    SQL 인젝션에 안전하다. 반환: (결과 행 리스트, 실제 실행된 SQL 문자열).
    """
    preds, binds = [], {}   # preds=술어 조각들, binds=바인드 변수 값들
    for i, c in enumerate(conditions):     # i 는 변수 이름이 겹치지 않게 하는 번호
        field = c.get("field")
        neg = "NOT " if c.get("negate") else ""   # NOT 체크 시 술어 앞에 붙일 말
        if field == "title" and c.get("value"):
            # 제목은 부분 일치(LIKE '%검색어%')
            binds[f"t{i}"] = f"%{c['value']}%"
            preds.append(f"{neg}(title LIKE :t{i})")
        elif field == "category" and c.get("value"):
            # 카테고리는 정확히 일치(=)
            binds[f"c{i}"] = c["value"]
            preds.append(f"{neg}(category = :c{i})")
        elif field == "price":
            # 가격은 입력된 범위에 따라 BETWEEN / >= / <= 로 갈라진다.
            lo, hi = c.get("min"), c.get("max")
            if lo not in (None, "") and hi not in (None, ""):
                binds[f"lo{i}"], binds[f"hi{i}"] = int(lo), int(hi)
                preds.append(f"{neg}(price BETWEEN :lo{i} AND :hi{i})")
            elif lo not in (None, ""):
                binds[f"lo{i}"] = int(lo)
                preds.append(f"{neg}(price >= :lo{i})")
            elif hi not in (None, ""):
                binds[f"hi{i}"] = int(hi)
                preds.append(f"{neg}(price <= :hi{i})")

    # 조건이 하나라도 있으면 WHERE 절을 만든다(연산자로 술어들을 연결).
    where = ""
    if preds:
        where = "WHERE " + f" {connector} ".join(preds)

    # 정렬 기준을 안전한 값으로만 매핑(임의 문자열이 SQL 에 들어가지 않게).
    order = {
        "recent": "regDateTime DESC",
        "price_asc": "price ASC",
        "price_desc": "price DESC",
    }.get(sort, "regDateTime DESC")

    # has_pic: 대표 사진(pic1) 유무를 1/0 으로 — 목록 썸네일 표시에 사용.
    sql = (
        "SELECT cno, itemNo, title, category, price, tradePlace, "
        "       sellStatus, regDateTime, "
        "       CASE WHEN pic1 IS NOT NULL THEN 1 ELSE 0 END AS has_pic "
        f"FROM Item {where} ORDER BY {order}"
    )
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, binds)
        cols = [d[0] for d in cur.description]            # 컬럼명 목록
        # 각 행을 dict 로 바꾼 리스트와, 화면에 보여 줄 SQL 문자열을 함께 반환
        return [dict(zip(cols, r)) for r in cur.fetchall()], sql


def get_item(cno, itemNo):
    """물품 한 건의 상세 정보 + 판매자 닉네임을 dict 로 돌려준다(없으면 None).

    사진은 실제 바이트 대신 has_pic1~3(있음 1/없음 0)만 가져와 화면에서 표시 여부만 판단한다.
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT i.cno, i.itemNo, i.title, i.description, i.category, i.price, "
            "       i.tradePlace, i.sellStatus, i.regDateTime, i.resDateTime, "
            "       i.finalPrice, c.nickname, "
            "       CASE WHEN i.pic1 IS NOT NULL THEN 1 ELSE 0 END, "
            "       CASE WHEN i.pic2 IS NOT NULL THEN 1 ELSE 0 END, "
            "       CASE WHEN i.pic3 IS NOT NULL THEN 1 ELSE 0 END "
            "FROM Item i JOIN Customer c ON i.cno = c.cno "   # 판매자 닉네임을 위해 조인
            "WHERE i.cno = :cno AND i.itemNo = :itemNo",
            {"cno": cno, "itemNo": itemNo},
        )
        row = cur.fetchone()
        if not row:
            return None
        # 조회 결과(튜플)에 이름을 붙여 dict 로 만든다(화면에서 item.title 처럼 쓰기 위해).
        keys = ["cno", "itemNo", "title", "description", "category", "price",
                "tradePlace", "sellStatus", "regDateTime", "resDateTime",
                "finalPrice", "seller_nick", "has_pic1", "has_pic2", "has_pic3"]
        return dict(zip(keys, row))


def get_image(cno, itemNo, idx):
    """물품 사진(BLOB) 바이트를 돌려준다. idx 는 1~3(pic1~3). 없으면 None.

    /items/.../image/<idx> 요청이 이 함수를 호출해 실제 이미지를 응답한다.
    """
    col = {1: "pic1", 2: "pic2", 3: "pic3"}.get(idx)   # idx → 컬럼명(잘못된 값이면 None)
    if not col:
        return None
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT {col} FROM Item WHERE cno = :cno AND itemNo = :itemNo",
            {"cno": cno, "itemNo": itemNo},
        )
        row = cur.fetchone()
        if not row or row[0] is None:    # 물품이 없거나 그 자리에 사진이 없으면
            return None
        return row[0].read()   # LOB(대용량 객체) → 실제 bytes 로 읽어 반환


def register_item(cno, title, description, category, price, tradePlace, images):
    """물품 등록. 판매자별 itemNo 를 'max+1'로 자동 부여한다.

    images: 사진 bytes 리스트(최대 3장, 없으면 빈 리스트) → pic1~pic3 에 매핑.
    등록 시각은 SYSTIMESTAMP, 상태는 '판매 중'으로 들어간다.
    반환: 새로 부여된 itemNo.
    """
    images = (images or [])[:3]   # None 방지 + 최대 3장으로 자르기
    with get_conn() as conn:
        cur = conn.cursor()
        # 이 판매자의 기존 물품 번호 중 가장 큰 값 + 1 = 새 물품 번호(없으면 1).
        cur.execute(
            "SELECT NVL(MAX(itemNo), 0) + 1 FROM Item WHERE cno = :cno", {"cno": cno}
        )
        new_no = cur.fetchone()[0]
        pics = (images + [None, None, None])[:3]   # 사진이 3장보다 적으면 None 으로 채움
        cur.execute(
            "INSERT INTO Item (cno, itemNo, title, description, category, price, "
            "                  tradePlace, regDateTime, sellStatus, pic1, pic2, pic3) "
            "VALUES (:cno, :itemNo, :title, :descr, :cat, :price, :place, "
            "        SYSTIMESTAMP, '판매 중', :p1, :p2, :p3)",
            {"cno": cno, "itemNo": new_no, "title": title, "descr": description,
             "cat": category, "price": price, "place": tradePlace,
             "p1": pics[0], "p2": pics[1], "p3": pics[2]},
        )
        return new_no


def update_item(cno, itemNo, title, description, category, price, tradePlace):
    """소유자 물품의 글자 항목(제목·설명·카테고리·가격·장소)을 수정한다.

    (이미지는 이 단순 버전에서는 변경하지 않는다.) 반환: 수정된 행 수.
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE Item SET title = :title, description = :descr, category = :cat, "
            "                price = :price, tradePlace = :place "
            "WHERE cno = :cno AND itemNo = :itemNo",
            {"title": title, "descr": description, "cat": category, "price": price,
             "place": tradePlace, "cno": cno, "itemNo": itemNo},
        )
        return cur.rowcount


def delete_item(cno, itemNo):
    """소유자 물품 삭제. 외래키(FK) 제약 때문에 '자식 → 부모' 순서로 지운다(한 트랜잭션).

    삭제 순서: Message → ChatRoom → PurchaseReq → Item.
    (메시지는 채팅방을, 채팅방·요청은 물품을 참조하므로 가장 아래쪽부터 지워야 한다.)
    """
    with get_conn() as conn:
        cur = conn.cursor()
        binds = {"cno": cno, "itemNo": itemNo}
        # 1) 이 물품의 채팅방들에 속한 메시지부터 삭제
        cur.execute(
            "DELETE FROM Message WHERE roomNo IN "
            "(SELECT roomNo FROM ChatRoom WHERE cno = :cno AND itemNo = :itemNo)",
            binds,
        )
        # 2) 채팅방 → 3) 구매 요청 → 4) 물품 본체 순으로 삭제
        cur.execute("DELETE FROM ChatRoom WHERE cno = :cno AND itemNo = :itemNo", binds)
        cur.execute("DELETE FROM PurchaseReq WHERE cno = :cno AND itemNo = :itemNo", binds)
        cur.execute("DELETE FROM Item WHERE cno = :cno AND itemNo = :itemNo", binds)
        return cur.rowcount


def complete_trade(cno, itemNo, final_price):
    """거래 완료 처리: 최종 금액을 저장하고 상태를 '거래 완료'로 바꾼다.

    WHERE 에 sellStatus='예약 중' 조건이 있어, 예약 중인 물품만 완료된다(중복 완료 차단).
    반환: 바뀐 행 수(1=성공, 0=예약 중이 아니라 처리 안 됨).
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE Item SET sellStatus = '거래 완료', finalPrice = :fp "
            "WHERE cno = :cno AND itemNo = :itemNo AND sellStatus = '예약 중'",
            {"fp": final_price, "cno": cno, "itemNo": itemNo},
        )
        return cur.rowcount  # 1이면 성공


def force_expire(cno, itemNo):
    """데모용: 특정 예약 물품의 예약 시각을 49시간 전으로 돌려 '48시간 만료'를 즉시 재현한다.

    이 함수로 시각만 과거로 바꾼 뒤 expire_reservations()를 부르면 곧바로 만료 처리가 된다.
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE Item SET resDateTime = SYSTIMESTAMP - NUMTODSINTERVAL(49, 'HOUR') "
            "WHERE cno = :cno AND itemNo = :itemNo AND sellStatus = '예약 중'",
            {"cno": cno, "itemNo": itemNo},
        )
        return cur.rowcount
