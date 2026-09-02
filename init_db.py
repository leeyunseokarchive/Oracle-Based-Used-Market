"""스키마/시드 적재 스크립트 (DB 초기화 도구).

이 스크립트 하나로 데이터베이스를 "깨끗한 초기 상태"로 다시 만든다. 실행 순서는
  1) schema/01_ddl.sql  : 테이블을 모두 지우고 새로 생성(구조)
  2) schema/02_seed.sql : 데모·통계용 초기 데이터 적재(내용)
  3) load_images()      : 물품 사진(BLOB)을 Item 테이블에 주입
이다.

  사용법:  python init_db.py

처음 실행할 때는 지울 테이블이 아직 없어 DROP 문에서 ORA-00942 오류가 날 수 있는데,
이는 정상이므로 무시한다(아래 run_file 의 ignore_missing 참고).
"""
import os
import sys

import oracledb

import config

# SQL 파일 폴더(schema/)와 시드 이미지 폴더(static/seed/)의 절대 경로.
SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "schema")
SEED_IMG_DIR = os.path.join(os.path.dirname(__file__), "static", "seed")

# 시드 물품 ↔ 사진 파일 매핑.  (판매자번호, 물품번호) → [pic1, pic2, pic3] 파일명.
# 이미지 같은 바이너리(BLOB)는 SQL INSERT 로 넣기 까다로워, 시드 SQL 에서는 비워 두고
# 여기 load_images() 가 파일을 읽어 UPDATE 로 채워 넣는다.
# 모든 시드 물품에 물품 종류에 맞는 사진을 둔다(대표 물품 아이폰 13 은 3장).
SEED_IMAGES = {
    ("C1", 1): ["c1_1_a.jpg", "c1_1_b.jpg", "c1_1_c.jpg"],  # 아이폰 13 (대표, 3장)
    ("C1", 2): ["c1_2.jpg"],                                  # 갤럭시 S22
    ("C1", 3): ["c1_3.jpg"],                                  # 아이패드
    ("C1", 4): ["c1_4.jpg"],                                  # 토익 문제집
    ("C2", 1): ["c2_1.jpg"],                                  # 반팔 티셔츠
    ("C2", 2): ["c2_2.jpg"],                                  # 청바지
    ("C2", 3): ["c2_3.jpg"],                                  # 후드티
    ("C3", 1): ["c3_1.jpg"],                                  # 자료구조 전공서적
    ("C3", 2): ["c3_2.jpg"],                                  # 운영체제 전공서적
    ("C4", 1): ["c4_1.jpg"],                                  # 전기포트
    ("C4", 2): ["c4_2.jpg"],                                  # 무선 청소기
    ("C5", 1): ["c5_1.jpg"],                                  # 원목 책상
    ("C5", 2): ["c5_2.jpg"],                                  # 싱글 침대
}


def split_statements(sql_text):
    """하나의 SQL 스크립트 문자열을 '실행 가능한 문장 리스트'로 잘라 준다.

    oracledb 의 execute() 는 한 번에 한 문장만 받으므로, 파일 전체를 문장 단위로
    나눠야 한다. 처리 규칙은 다음과 같다.
      - '--' 로 시작하는 한 줄 주석은 버린다.
      - 세미콜론(;) 을 문장 구분자로 본다(이 프로젝트엔 PL/SQL 블록이 없어 안전하다).
    """
    lines = []
    for line in sql_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):   # 주석 줄은 건너뛴다
            continue
        lines.append(line)
    body = "\n".join(lines)
    # ';' 로 쪼갠 뒤 공백만 남는 조각은 버린다.
    return [s.strip() for s in body.split(";") if s.strip()]


def run_file(cursor, path, ignore_missing=False):
    """SQL 파일을 읽어 문장 하나씩 차례로 실행한다.

    ignore_missing=True 이면, 없는 테이블을 DROP 할 때 나는 ORA-00942 오류를
    "정상"으로 보고 건너뛴다(최초 실행 시 DROP 대상이 없는 경우 대비).
    그 밖의 오류는 어떤 문장에서 났는지 출력하고 그대로 다시 던진다.
    """
    with open(path, encoding="utf-8") as f:
        statements = split_statements(f.read())
    for stmt in statements:
        try:
            cursor.execute(stmt)
        except oracledb.DatabaseError as e:
            (err,) = e.args
            # ORA-00942 = "table or view does not exist". DROP 대상이 없을 뿐이므로 통과.
            if ignore_missing and err.code == 942:
                continue
            print(f"[오류] {err.code}: {err.message}\n  문장: {stmt[:80]}...")
            raise
    print(f"  실행 완료: {os.path.basename(path)} ({len(statements)} 문장)")


def load_images(cursor):
    """static/seed/ 의 사진 파일을 해당 물품의 pic1~3 (BLOB) 컬럼에 주입한다.

    위 SEED_IMAGES 매핑을 돌며, 각 물품에 연결된 파일을 바이트로 읽어 UPDATE 한다.
    파일이 실제로 없으면 그 자리는 건너뛴다(사진이 없어도 나머지 기능은 정상 동작).
    반환값: 실제로 주입한 사진 장수(콘솔 출력용).
    """
    loaded = 0
    for (cno, item_no), files in SEED_IMAGES.items():
        # pic1·pic2·pic3 세 자리를 준비하고, 파일이 있는 만큼만 채운다(없으면 None).
        blobs = [None, None, None]
        for i, name in enumerate(files[:3]):       # 최대 3장까지만 사용
            path = os.path.join(SEED_IMG_DIR, name)
            if os.path.exists(path):
                with open(path, "rb") as f:        # 'rb' = 바이너리로 읽기
                    blobs[i] = f.read()
                loaded += 1
        cursor.execute(
            "UPDATE Item SET pic1 = :p1, pic2 = :p2, pic3 = :p3 "
            "WHERE cno = :cno AND itemNo = :ino",
            {"p1": blobs[0], "p2": blobs[1], "p3": blobs[2],
             "cno": cno, "ino": item_no},
        )
    return loaded


def main():
    """DB 접속 → DDL → 시드 → 이미지 순으로 적재하고, 결과 행 수를 출력한다."""
    conn = oracledb.connect(user=config.DB_USER, password=config.DB_PASSWORD, dsn=config.DSN)
    cur = conn.cursor()
    print(f"DB 접속 성공: {config.DSN} (user={config.DB_USER})")

    # 1) 구조 만들기(DROP 실패는 무시) → 2) 데이터 넣기 → 3) 사진 주입
    run_file(cur, os.path.join(SCHEMA_DIR, "01_ddl.sql"), ignore_missing=True)
    run_file(cur, os.path.join(SCHEMA_DIR, "02_seed.sql"))
    n_img = load_images(cur)
    print(f"  이미지 주입 완료: {n_img}장")
    conn.commit()                                  # 여기까지 성공해야 실제 반영

    # 적재가 잘 됐는지 테이블별 행 수를 찍어 확인한다.
    for t in ("Customer", "Item", "PurchaseReq", "ChatRoom", "Message"):
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        print(f"  {t:12s}: {cur.fetchone()[0]} rows")

    cur.close()
    conn.close()
    print("초기화 완료.")


if __name__ == "__main__":
    sys.exit(main())
