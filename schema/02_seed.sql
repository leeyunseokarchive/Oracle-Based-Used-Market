-- ============================================================
-- [TP-7] 데모 시드 데이터 (균형 축소판)
-- 평가표 9단계 시연에 필요한 최소 데이터만 적재하되, 통계 질의가
-- 의미 있게 나오도록 지역·카테고리·요청일자 다양성은 유지한다.
--   · 회원 6명(관리자 1 + 일반 5), 물품 13개, 구매요청 10건, 채팅방 2개, 메시지 6건
--   · 거래 완료 6건을 5개 지역·5개 카테고리에 분산(대전은 2건) → ROLLUP 소계/총계가 풍부
--   · 구매 요청 일자를 4/28~5/2로 분산 → 윈도우 함수(날짜 추이/RANK) 시연
-- 물품 사진(pic1~3)은 SQL로 바이너리를 넣을 수 없어 NULL 로 두고,
-- init_db.py 의 load_images() 가 static/seed/ 이미지를 BLOB 으로 주입한다.
--
-- 읽는 법: 아래는 전부 INSERT(데이터 넣기)와 일부 UPDATE(상태 보정)뿐이며,
-- 표는 부모 → 자식 순서(회원 → 물품 → 구매요청 → 채팅방 → 메시지)로 채운다.
-- 맨 끝의 COMMIT 으로 한 번에 확정된다.
-- ============================================================

-- 0. 회원 (관리자 c0 + 일반 회원 C1~C5) -----------------------
INSERT INTO Customer VALUES ('c0','admin','관리자','010-0000-0000','본사');   -- 관리자 계정
INSERT INTO Customer VALUES ('C1','pw1','nick1','010-0000-0001','대전');
INSERT INTO Customer VALUES ('C2','pw2','nick2','010-0000-0002','서울');
INSERT INTO Customer VALUES ('C3','pw3','nick3','010-0000-0003','부산');
INSERT INTO Customer VALUES ('C4','pw4','nick4','010-0000-0004','대구');
INSERT INTO Customer VALUES ('C5','pw5','nick5','010-0000-0005','인천');

-- 1. 물품 12개 — 5개 카테고리 분포 -----------------------------
-- 1-1. 판매 중 물품 (검색·등록·구매요청 시연 대상)
INSERT INTO Item VALUES ('C1',1,'아이폰 13','A급 상태, 케이스 포함','전자기기',800000,'대전',SYSTIMESTAMP,NULL,'판매 중',NULL,NULL,NULL,NULL);  -- 히어로(사진 3장)
INSERT INTO Item VALUES ('C1',3,'아이패드','펜슬 포함, 액정 깨끗','전자기기',500000,'대전',SYSTIMESTAMP,NULL,'판매 중',NULL,NULL,NULL,NULL);
INSERT INTO Item VALUES ('C2',1,'반팔 티셔츠','새상품, 택 미제거','의류',20000,'서울',SYSTIMESTAMP,NULL,'판매 중',NULL,NULL,NULL,NULL);     -- 사진 1장
INSERT INTO Item VALUES ('C2',2,'청바지','한 번 착용한 중고','의류',30000,'서울',SYSTIMESTAMP,NULL,'판매 중',NULL,NULL,NULL,NULL);
INSERT INTO Item VALUES ('C3',1,'자료구조 전공서적','밑줄 거의 없음','도서',15000,'부산',SYSTIMESTAMP,NULL,'판매 중',NULL,NULL,NULL,NULL);  -- 사진 1장
INSERT INTO Item VALUES ('C4',1,'전기포트','사용감 있으나 정상','생활용품',10000,'대구',SYSTIMESTAMP,NULL,'판매 중',NULL,NULL,NULL,NULL);
INSERT INTO Item VALUES ('C5',1,'원목 책상','상판 흠집 적음','가구',70000,'인천',SYSTIMESTAMP,NULL,'판매 중',NULL,NULL,NULL,NULL);

-- 1-2. 거래 완료 물품 (지역·카테고리별 거래 통계용 — ROLLUP)
INSERT INTO Item VALUES ('C1',2,'갤럭시 S22','정상 작동','전자기기',600000,'대전',SYSTIMESTAMP,NULL,'거래 완료',NULL,NULL,NULL,590000);
INSERT INTO Item VALUES ('C1',4,'토익 문제집','필기 없음','도서',20000,'대전',SYSTIMESTAMP,NULL,'거래 완료',NULL,NULL,NULL,17000);  -- 대전에 2번째 완료 → 지역 소계가 실제 합산
INSERT INTO Item VALUES ('C2',3,'후드티','거의 새것','의류',40000,'서울',SYSTIMESTAMP,NULL,'거래 완료',NULL,NULL,NULL,38000);
INSERT INTO Item VALUES ('C3',2,'운영체제 전공서적','필기 있음','도서',18000,'부산',SYSTIMESTAMP,NULL,'거래 완료',NULL,NULL,NULL,17000);
INSERT INTO Item VALUES ('C4',2,'무선 청소기','흡입력 좋음','생활용품',50000,'대구',SYSTIMESTAMP,NULL,'거래 완료',NULL,NULL,NULL,48000);  -- 사진 1장
INSERT INTO Item VALUES ('C5',2,'싱글 침대','매트리스 포함','가구',100000,'인천',SYSTIMESTAMP,NULL,'거래 완료',NULL,NULL,NULL,95000);

-- 2. 구매 요청 10건 -------------------------------------------
-- 2-1. 히어로 물품(C1 아이폰)에 3명 요청 → 다건 요청·승인 자동삭제 시연
INSERT INTO PurchaseReq VALUES ('C2','C1',1,TO_TIMESTAMP('2026-04-28 09:00:00','YYYY-MM-DD HH24:MI:SS'),750000,'구매 원해요~ 직거래 가능할까요?');
INSERT INTO PurchaseReq VALUES ('C3','C1',1,TO_TIMESTAMP('2026-04-28 11:00:00','YYYY-MM-DD HH24:MI:SS'),760000,'가격 협의 가능한가요?');
INSERT INTO PurchaseReq VALUES ('C4','C1',1,TO_TIMESTAMP('2026-04-28 15:00:00','YYYY-MM-DD HH24:MI:SS'),770000,'오늘 바로 거래 원합니다.');

-- 2-2. C1 아이패드 — C1 판매자의 요청 총합을 키워 인기 판매자 RANK 1위로
INSERT INTO PurchaseReq VALUES ('C2','C1',3,TO_TIMESTAMP('2026-05-01 10:00:00','YYYY-MM-DD HH24:MI:SS'),480000,'펜슬 상태 궁금합니다.');
INSERT INTO PurchaseReq VALUES ('C3','C1',3,TO_TIMESTAMP('2026-05-01 13:00:00','YYYY-MM-DD HH24:MI:SS'),490000,'네고 가능할까요?');

-- 2-3. C2 청바지 — 또 다른 다건 요청(날짜 분산)
INSERT INTO PurchaseReq VALUES ('C3','C2',2,TO_TIMESTAMP('2026-04-29 14:00:00','YYYY-MM-DD HH24:MI:SS'),28000,'사이즈 문의드려요.');
INSERT INTO PurchaseReq VALUES ('C4','C2',2,TO_TIMESTAMP('2026-04-29 18:00:00','YYYY-MM-DD HH24:MI:SS'),29000,'택배 거래 되나요?');
INSERT INTO PurchaseReq VALUES ('C5','C2',2,TO_TIMESTAMP('2026-05-02 11:00:00','YYYY-MM-DD HH24:MI:SS'),30000,'바로 구매 가능합니다.');

-- 2-4. 소수 추가(요청 받은 판매자 다양화 → RANK 2·3위 형성)
INSERT INTO PurchaseReq VALUES ('C5','C3',1,TO_TIMESTAMP('2026-05-02 16:00:00','YYYY-MM-DD HH24:MI:SS'),15000,'구매 원합니다.');
INSERT INTO PurchaseReq VALUES ('C2','C4',1,TO_TIMESTAMP('2026-05-02 17:00:00','YYYY-MM-DD HH24:MI:SS'),10000,'관심 있습니다.');

-- 3. 채팅방 2개 (roomNo 는 IDENTITY 로 1,2 자동 부여) ---------
INSERT INTO ChatRoom (receiveCno, createDateTime, cno, itemNo) VALUES ('C2', SYSTIMESTAMP, 'C1', 1);  -- room 1 : 구매자 C2 - 판매자 C1 - 아이폰
INSERT INTO ChatRoom (receiveCno, createDateTime, cno, itemNo) VALUES ('C3', SYSTIMESTAMP, 'C1', 1);  -- room 2 : 구매자 C3 - 판매자 C1 - 아이폰

-- 4. 채팅 메시지 6건 (각 방 3건, 마지막은 안읽음 'N') ---------
INSERT INTO Message (roomNo, sender, sentDateTime, content, isRead) VALUES (1,'B',SYSTIMESTAMP,'안녕하세요, 아이폰 구매 가능할까요?','Y');
INSERT INTO Message (roomNo, sender, sentDateTime, content, isRead) VALUES (1,'S',SYSTIMESTAMP,'네 가능합니다. 직거래 선호합니다.','Y');
INSERT INTO Message (roomNo, sender, sentDateTime, content, isRead) VALUES (1,'B',SYSTIMESTAMP,'오늘 저녁에 거래 가능할까요?','N');  -- 판매자(C1)가 안읽음
INSERT INTO Message (roomNo, sender, sentDateTime, content, isRead) VALUES (2,'B',SYSTIMESTAMP,'상품 상태 어떤가요?','Y');
INSERT INTO Message (roomNo, sender, sentDateTime, content, isRead) VALUES (2,'S',SYSTIMESTAMP,'거의 새 제품입니다.','Y');
INSERT INTO Message (roomNo, sender, sentDateTime, content, isRead) VALUES (2,'B',SYSTIMESTAMP,'가격 조금 조정 가능한가요?','N');  -- 판매자(C1)가 안읽음

COMMIT;
