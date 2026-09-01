"""보고서(7-3 User Manual · 7-1)용 화면 캡처 자동화 스크립트.

eval/process.md 의 9단계 시나리오를 Playwright(headless Chromium)로 그대로
구동하며, 각 기능의 화면을 docs/ 폴더에 PNG 로 저장한다.

흐름은 **판매자 C1 이 라이브로 등록한 '아이폰 3GS'(testPic1~3 사진) 물품을 중심**으로
검색→구매요청→채팅→승인→완료까지 이어진다. (등록 데모용 testPic 사진이 아이폰 3GS 라서
보고서 서술과 실제 화면이 일치하도록 맞춘 것이다.)

사용법:
    docker start tp_oracle && .venv/bin/python init_db.py
    TP_DEBUG=0 .venv/bin/python app.py &
    .venv/bin/python eval/capture_screens.py

전제: `.venv/bin/python -m pip install playwright && playwright install chromium`.
주의: 스크립트는 시드 상태를 변형(등록·요청·승인·완료·만료)하므로, 실제 데모 전에는
      init_db.py 로 다시 초기화한다.
"""
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # tp_demo/
DOCS = os.path.join(BASE, "docs")
PICS = [os.path.join(BASE, "eval", f"testPic{i}.png") for i in (1, 2, 3)]  # 아이폰 3GS 사진
URL = "http://127.0.0.1:5000"

# 데모 중심 물품: 판매자 C1 이 등록할 '아이폰 3GS'.
# 시드 물품이 C1/1~4 이므로 새 등록은 itemNo=5 가 된다.
HERO = "C1/5"

os.makedirs(DOCS, exist_ok=True)


def shot(page, name):
    """현재 화면을 docs/<name>.png 로 전체 캡처."""
    page.screenshot(path=os.path.join(DOCS, name + ".png"), full_page=True)
    print(f"  📷 {name}.png")


def login(page, cno, passwd):
    page.goto(f"{URL}/")
    page.fill("input[name=cno]", cno)
    page.fill("input[name=passwd]", passwd)
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")


def logout(page):
    page.goto(f"{URL}/logout")
    page.wait_for_load_state("networkidle")


def run(page):
    # ============================================================
    # [기능 1] 로그인 & 권한 구분
    # ============================================================
    page.goto(f"{URL}/")
    shot(page, "f1_login")                      # 로그인 폼(상단 메뉴바 없음)

    # 비밀번호 오류 → 빨간 테두리 + 경고
    page.fill("input[name=cno]", "C1")
    page.fill("input[name=passwd]", "wrongpw")
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")
    shot(page, "f1_login_error")

    # 일반 회원 로그인 → 검색 홈(회원 메뉴 등장)
    login(page, "C1", "pw1")
    shot(page, "f1_search_home")

    # 권한 구분: 일반 회원(C1)이 관리자 전용 통계 페이지 접근 → 403 차단
    page.goto(f"{URL}/admin/stats")
    page.wait_for_load_state("networkidle")
    shot(page, "f1_member_denied")
    logout(page)

    # ============================================================
    # [기능 9 · 7-1] 관리자 통계 + DB 덤프 — 깨끗한 시드 상태에서 먼저 캡처
    #   (이후 등록·승인·완료가 데이터를 바꾸기 전에 찍어 7-1 요약과 일치시킨다)
    # ============================================================
    login(page, "c0", "admin")
    shot(page, "f9_stats")                      # ① ROLLUP ② 윈도우 함수
    page.goto(f"{URL}/admin/db-dump")
    page.wait_for_load_state("networkidle")
    shot(page, "f71_db_dump")                   # [7-1] DB 테이블 내용
    logout(page)

    # ============================================================
    # [기능 2] 물품 등록 — 판매자 C1 이 '아이폰 3GS'를 등록(사진 3장 라이브 업로드)
    # ============================================================
    login(page, "C1", "pw1")
    page.goto(f"{URL}/items/new")
    page.wait_for_load_state("networkidle")
    # 검증 오류: 제목/가격 비우고 등록
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")
    shot(page, "f2_register_error")
    # 정상 등록 (제목·장소를 testPic 의 실제 물품에 맞춰 '아이폰 3GS' / '충남대학교')
    page.goto(f"{URL}/items/new")
    page.fill("input[name=title]", "아이폰 3GS")
    page.select_option("select[name=category]", "전자기기")
    page.fill("input[name=price]", "150000")
    page.fill("input[name=tradePlace]", "충남대학교")
    page.fill("textarea[name=description]", "정상 작동, 32GB 화이트. 배터리 교체 이력 있음")
    for sel, p in zip(("pic1", "pic2", "pic3"), PICS):
        page.set_input_files(f"input[name={sel}]", p)
    shot(page, "f2_register_form")              # 입력 완료된 등록 폼
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")
    shot(page, "f2_register_after")             # 등록된 아이폰 3GS 상세(판매자 시점, 사진 3장)
    logout(page)

    # ============================================================
    # [기능 3] 물품 검색 — AND/OR/NOT·정렬  (구매자 C2)
    # ============================================================
    login(page, "C2", "pw2")
    page.goto(f"{URL}/search?title=%EC%95%84%EC%9D%B4%ED%8F%B0")   # 제목=아이폰 → 아이폰 13·3GS
    page.wait_for_load_state("networkidle")
    shot(page, "f3_search_single")
    # 조합: 카테고리=전자기기 AND 가격 100000~900000, SQL 패널 펼침
    page.goto(f"{URL}/search?category=%EC%A0%84%EC%9E%90%EA%B8%B0%EA%B8%B0"
              "&price_min=100000&price_max=900000&connector=AND&sort=recent")
    page.wait_for_load_state("networkidle")
    page.eval_on_selector("details.sql-box", "el => el.open = true")
    shot(page, "f3_search_combo_sql")
    # 정렬: 가격 낮은순
    page.goto(f"{URL}/search?sort=price_asc")
    page.wait_for_load_state("networkidle")
    shot(page, "f3_search_sort")

    # ============================================================
    # [기능 4] 구매 요청 — 구매자 C2 가 아이폰 3GS 상세에서 요청
    # ============================================================
    page.goto(f"{URL}/items/{HERO}")
    page.wait_for_load_state("networkidle")
    shot(page, "f2_detail_3pics")               # 구매자 시점: 아이폰 3GS 사진 3장 + 요청/채팅
    page.eval_on_selector("#reqForm", "el => el.scrollIntoView()")
    shot(page, "f4_request_form")               # 구매 요청 보내기 폼
    page.fill("#reqForm input[name=reqPrice]", "140000")
    page.fill("#reqForm input[name=reqMessage]", "직거래 원해요. 오늘 가능할까요?")
    page.locator("#reqForm button").click()
    page.wait_for_load_state("networkidle")

    # 구매자 C2 가 1:1 채팅 시작 + 메시지 전송 (판매자에게 안읽음으로 쌓임)
    page.goto(f"{URL}/items/{HERO}")
    page.wait_for_load_state("networkidle")
    page.locator("form[action='/items/C1/5/chat'] button").click()
    page.wait_for_url("**/chats/**")
    page.fill("form.send-form input[name=content]", "안녕하세요! 아이폰 3GS 구매하고 싶어요.")
    page.locator("form.send-form button").click()
    page.wait_for_load_state("networkidle")
    logout(page)

    # 또 다른 구매자 C3 도 같은 물품에 요청 (여러 명 요청 시연)
    login(page, "C3", "pw3")
    page.goto(f"{URL}/items/{HERO}")
    page.wait_for_load_state("networkidle")
    page.fill("#reqForm input[name=reqPrice]", "145000")
    page.fill("#reqForm input[name=reqMessage]", "상태 좋아 보이네요. 택배 가능한가요?")
    page.locator("#reqForm button").click()
    page.wait_for_load_state("networkidle")
    logout(page)

    # ============================================================
    # [기능 4·5] 판매자 C1: 여러 요청 목록 + 채팅(안읽음/읽음)
    # ============================================================
    login(page, "C1", "pw1")
    page.goto(f"{URL}/items/{HERO}")            # 판매자 시점: C2·C3 요청 목록
    page.wait_for_load_state("networkidle")
    shot(page, "f4_seller_requests")

    page.goto(f"{URL}/chats")                    # 안 읽은 메시지 수 배지(아이폰 3GS 방)
    page.wait_for_load_state("networkidle")
    shot(page, "f5_chat_list_badge")
    page.goto(f"{URL}/chats/3")                  # 아이폰 3GS(C1/5) 채팅방 = roomNo 3
    page.wait_for_load_state("networkidle")
    shot(page, "f5_chat_room")                  # 보낸사람·시간·내용·읽음여부

    # ============================================================
    # [기능 6] 거래 승인 → 예약 중  (아이폰 3GS 의 C2 요청 승인)
    # ============================================================
    page.goto(f"{URL}/mypage/seller")
    page.wait_for_load_state("networkidle")
    shot(page, "f6_mypage_before_approve")      # 승인 전: 아이폰 3GS 에 C2·C3 요청
    page.locator("form[action='/items/C1/5/approve'] button").first.click()
    page.wait_for_url("**/chats/**")            # 승인 후 채팅방으로 이동
    page.goto(f"{URL}/mypage/seller")
    page.wait_for_load_state("networkidle")
    shot(page, "f6_after_approve_reserved")     # 아이폰 3GS '예약 중' + 거래완료/만료 버튼

    # ============================================================
    # [기능 7] 거래 완료 (최종 금액 입력)
    # ============================================================
    page.fill("form[action='/items/C1/5/complete'] input[name=finalPrice]", "140000")
    page.locator("form[action='/items/C1/5/complete'] button").click()
    page.wait_for_url("**/mypage/seller")
    page.goto(f"{URL}/items/{HERO}")
    page.wait_for_load_state("networkidle")
    shot(page, "f7_complete_done")              # 아이폰 3GS '거래 완료' + 최종 금액

    # ============================================================
    # [기능 8] 예약 자동 취소 (48시간 초과) — 아이패드(C1/3)로 독립 시연
    # ============================================================
    page.goto(f"{URL}/mypage/seller")
    page.wait_for_load_state("networkidle")
    page.locator("form[action='/items/C1/3/approve'] button").first.click()  # 아이패드 승인 → 예약 중
    page.wait_for_url("**/chats/**")
    page.goto(f"{URL}/mypage/seller")
    page.wait_for_load_state("networkidle")
    shot(page, "f8_expire_before")              # 아이패드 '예약 중' + [48시간 경과] 버튼
    page.locator("form[action='/items/C1/3/force-expire'] button").click()
    page.wait_for_url("**/mypage/seller")
    page.goto(f"{URL}/mypage/seller")
    page.wait_for_load_state("networkidle")
    shot(page, "f8_expire_after")               # 아이패드 '판매 중' 복귀

    # ============================================================
    # [예외] 없는 주소 → 안내 페이지(error.html)
    # ============================================================
    page.goto(f"{URL}/no-such-page")
    page.wait_for_load_state("networkidle")
    shot(page, "ex_404")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 900},
                                      device_scale_factor=2)
        page = context.new_page()
        try:
            run(page)
        finally:
            browser.close()
    print("완료: docs/ 에 캡처 저장됨.")


if __name__ == "__main__":
    sys.exit(main())
