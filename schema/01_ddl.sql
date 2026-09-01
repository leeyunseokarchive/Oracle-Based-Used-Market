-- ============================================================
-- [TP-7] 온라인 중고거래 플랫폼 — 스키마 정의 (DDL)
-- TP-3 DDL-Solution 을 그대로 옮긴 것. Oracle 23ai Free 기준.
--
-- 이 파일은 "테이블 구조"를 만든다. init_db.py 가 실행하며,
-- '--' 로 시작하는 줄은 실행 전에 제거되므로 자유롭게 설명을 달아도 된다.
-- 표 5개의 관계: Customer(회원) 1 — N Item(물품),
--               Item 1 — N PurchaseReq(구매요청) / ChatRoom(채팅방),
--               ChatRoom 1 — N Message(메시지).
-- ============================================================

-- 기존 테이블이 있다면 자식 → 부모 순서로 삭제
-- (FK 로 엮여 있어, 참조하는 쪽(자식)부터 지워야 한다. 최초 실행 땐 대상이 없어 무시됨.)
DROP TABLE Message      CASCADE CONSTRAINTS;
DROP TABLE PurchaseReq  CASCADE CONSTRAINTS;
DROP TABLE ChatRoom     CASCADE CONSTRAINTS;
DROP TABLE Item         CASCADE CONSTRAINTS;
DROP TABLE Customer     CASCADE CONSTRAINTS;

-- 1. Customer (회원) -----------------------------------------
-- 회원번호(cno)가 기본키. 닉네임은 UNIQUE 라 서로 겹칠 수 없다.
CREATE TABLE Customer (
    cno      VARCHAR2(10),
    passwd   VARCHAR2(100) NOT NULL,
    nickname VARCHAR2(50)  NOT NULL UNIQUE,   -- 닉네임 중복 불가
    phone    VARCHAR2(20),
    region   VARCHAR2(100),
    CONSTRAINT PK_Customer PRIMARY KEY (cno)
);

-- 2. Item (물품) ---------------------------------------------
-- 한 물품은 (판매자 cno + 그 판매자 안에서의 번호 itemNo) 두 값으로 식별한다(복합 기본키).
-- sellStatus 는 '판매 중/예약 중/거래 완료' 세 값만 허용(CHECK). 사진 3장은 BLOB.
CREATE TABLE Item (
    cno         VARCHAR2(10),                 -- 판매자(회원번호)
    itemNo      NUMBER,                        -- 판매자별로 1,2,3... 수동 부여
    title       VARCHAR2(100) NOT NULL,
    description VARCHAR2(300),
    category    VARCHAR2(50)  NOT NULL,
    price       NUMBER        NOT NULL,
    tradePlace  VARCHAR2(200),
    regDateTime TIMESTAMP     NOT NULL,        -- 물품 등록일시 (불변)
    resDateTime TIMESTAMP,                     -- 예약 승인일시 (48시간 타이머 기준)
    sellStatus  VARCHAR2(20)  DEFAULT '판매 중',
    pic1        BLOB,
    pic2        BLOB,
    pic3        BLOB,
    finalPrice  NUMBER,                        -- 최종 거래 금액
    CONSTRAINT PK_Item       PRIMARY KEY (cno, itemNo),
    CONSTRAINT FK_Item_Customer FOREIGN KEY (cno) REFERENCES Customer(cno),
    CONSTRAINT CHK_SELL_STATUS CHECK (sellStatus IN ('판매 중', '예약 중', '거래 완료'))
);

-- 3. PurchaseReq (구매 요청) ---------------------------------
-- (요청자 + 판매자 + 물품) 세 값이 기본키라, 같은 사람이 같은 물품에 두 번 요청할 수 없다.
CREATE TABLE PurchaseReq (
    requestCno VARCHAR2(10),                   -- 구매 요청자
    cno        VARCHAR2(10),                   -- 물품 판매자
    itemNo     NUMBER,                          -- 물품 번호
    reqDateTime TIMESTAMP,
    reqPrice   NUMBER,
    reqMessage VARCHAR2(1000),
    CONSTRAINT PK_PurchaseReq PRIMARY KEY (requestCno, cno, itemNo),
    CONSTRAINT FK_PurReq_Customer FOREIGN KEY (requestCno) REFERENCES Customer(cno),
    CONSTRAINT FK_PurReq_Item     FOREIGN KEY (cno, itemNo) REFERENCES Item(cno, itemNo)
);

-- 4. ChatRoom (채팅방) ---------------------------------------
-- roomNo 는 IDENTITY 로 1,2,3... 자동 채번. UNIQUE 제약으로 '물품당 (구매자,판매자) 방 1개'를 보장한다.
CREATE TABLE ChatRoom (
    roomNo         NUMBER GENERATED ALWAYS AS IDENTITY,
    receiveCno     VARCHAR2(10),               -- 구매자(채팅 상대)
    createDateTime TIMESTAMP,
    cno            VARCHAR2(10),               -- 물품 판매자
    itemNo         NUMBER,
    CONSTRAINT PK_ChatRoom PRIMARY KEY (roomNo),
    CONSTRAINT FK_Chat_Customer FOREIGN KEY (receiveCno) REFERENCES Customer(cno),
    CONSTRAINT FK_Chat_Item     FOREIGN KEY (cno, itemNo) REFERENCES Item(cno, itemNo),
    CONSTRAINT UQ_ChatRoom UNIQUE (receiveCno, cno, itemNo)   -- 물품당 구매자-판매자 1방
);

-- 5. Message (메시지) ----------------------------------------
-- 방(roomNo)별 메시지. seqNo 는 자동 채번. sender 는 'S'(판매자)/'B'(구매자)만, isRead 는 'Y'/'N'만 허용.
CREATE TABLE Message (
    roomNo       NUMBER,
    seqNo        NUMBER GENERATED ALWAYS AS IDENTITY,
    sender       CHAR(1) CHECK (sender IN ('S', 'B')),   -- 'S'=판매자, 'B'=구매자
    sentDateTime TIMESTAMP,
    content      VARCHAR2(2000),
    isRead       CHAR(1) DEFAULT 'N' CHECK (isRead IN ('Y', 'N')),
    CONSTRAINT PK_Message PRIMARY KEY (roomNo, seqNo),
    CONSTRAINT FK_Message_ChatRoom FOREIGN KEY (roomNo) REFERENCES ChatRoom(roomNo)
);
