"""관리자(c0) 전용 통계 — TP-5 의 두 질의를 그대로 사용한다.

관리자 통계 화면은 SQL 의 '집계' 기능 두 가지를 보여 주기 위한 것이다.
1) 그룹 함수(ROLLUP): 지역·카테고리별 거래 활성도 + 소계/총계
2) 윈도우 함수(RANK/누적합): 판매자 인기 순위와 판매자별 물품 요청 누적

아래 두 SQL 은 문자열 상수로 두고, 맨 끝의 두 함수가 이를 실행해 결과를 돌려준다.
(SQL 문 자체는 손대지 않으며, 설명은 이 파이썬 주석으로만 단다.)
"""
from db import query_all

# 5-1. 그룹 함수(ROLLUP) — '거래 완료'된 물품을 지역·카테고리로 묶어 건수와 금액 합계를 낸다.
#   · ROLLUP(지역, 카테고리)  → 상세 행 + 지역별 소계 + 전체 총계까지 한 번에 집계
#   · GROUPING(...) = 1 이면 그 칼럼이 '합쳐진(소계/총계)' 행이라는 뜻 → CASE 로 라벨을 붙인다.
#   · NVL(SUM(finalPrice), 0) → 합계가 비어 있으면(NULL) 0 으로 표시
GROUP_FUNCTION_SQL = """
SELECT
    CASE WHEN GROUPING(c.region) = 1
         THEN '전체 합계' ELSE c.region END AS 거래지역,
    CASE WHEN GROUPING(i.category) = 1 AND GROUPING(c.region) = 0
         THEN '지역 소계'
         WHEN GROUPING(i.category) = 1 AND GROUPING(c.region) = 1
         THEN '전체 소계'
         ELSE i.category END AS 상품카테고리,
    COUNT(*) AS 거래건수,
    NVL(SUM(i.finalPrice), 0) AS 총거래금액합계
FROM Item i
JOIN Customer c ON i.cno = c.cno
WHERE i.sellStatus = '거래 완료'
GROUP BY ROLLUP(c.region, i.category)
ORDER BY c.region, i.category
"""

# 5-2. 윈도우 함수 — 판매자별 인기순위 & 판매자 내 물품별 요청 누적
#   ① 판매자(유저)를 '받은 요청 총합'으로 RANK → 인기 판매자 순위
#   ② 그 판매자 아래에 물품들을 나열하고, SUM() OVER (PARTITION BY 판매자) 로 판매자별 누적
#   ③ ROW_NUMBER() 로 판매자 첫 행에만 순위/이름 표시(머리행), 이하 물품 행은 공백
#   요청을 "받은" 사람 기준이므로 PurchaseReq.cno(판매자)로 Item·Customer 와 조인한다.
#   (WITH 절: item_req=물품별 요청수 → seller_tot=판매자 총합·순위 → joined=누적까지 계산)
WINDOW_FUNCTION_SQL = """
WITH item_req AS (
  SELECT i.cno AS seller_cno, c.nickname AS seller_nick,
         i.itemNo AS item_no, i.title AS item_title, COUNT(*) AS req_cnt
  FROM PurchaseReq p
  JOIN Item i     ON p.cno = i.cno AND p.itemNo = i.itemNo
  JOIN Customer c ON i.cno = c.cno
  GROUP BY i.cno, c.nickname, i.itemNo, i.title
),
seller_tot AS (
  SELECT seller_cno, SUM(req_cnt) AS seller_total,
         RANK() OVER (ORDER BY SUM(req_cnt) DESC) AS seller_rank
  FROM item_req GROUP BY seller_cno
),
joined AS (
  SELECT ir.seller_cno, ir.seller_nick, ir.item_no, ir.item_title, ir.req_cnt,
         st.seller_rank,
         ROW_NUMBER() OVER (PARTITION BY ir.seller_cno
              ORDER BY ir.req_cnt DESC, ir.item_no) AS rn,
         SUM(ir.req_cnt) OVER (PARTITION BY ir.seller_cno
              ORDER BY ir.req_cnt DESC, ir.item_no
              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS seller_cum
  FROM item_req ir JOIN seller_tot st ON ir.seller_cno = st.seller_cno
)
SELECT
  CASE WHEN rn = 1 THEN TO_CHAR(seller_rank) ELSE ' ' END                     AS 판매자순위,
  CASE WHEN rn = 1 THEN seller_nick || ' (' || seller_cno || ')' ELSE ' ' END AS 판매자,
  item_title  AS 물품명,
  req_cnt     AS 물품별요청수,
  seller_cum  AS 판매자누적요청수
FROM joined
ORDER BY seller_rank, seller_cno, req_cnt DESC, item_no
"""


def group_function_stat():
    """위 ROLLUP 질의를 실행해 지역/카테고리 거래 통계를 (컬럼, 행)으로 돌려준다."""
    return query_all(GROUP_FUNCTION_SQL)


def window_function_stat():
    """위 윈도우 함수 질의를 실행해 판매자 인기 순위·누적 요청 통계를 (컬럼, 행)으로 돌려준다."""
    return query_all(WINDOW_FUNCTION_SQL)
