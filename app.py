"""온라인 중고거래 플랫폼 데모 — Flask 진입점(표현 계층).

이 파일은 웹 주소(URL)와 화면을 연결하는 "교통정리" 역할을 한다. 사용자가 어떤
주소로 들어오면, 여기서 ① 로그인/권한을 확인하고 ② 입력값을 가볍게 검사한 뒤
③ 실제 일은 services/ 의 함수에 맡기고 ④ 결과 화면(templates/)을 보여 준다.
DB·SQL 은 직접 다루지 않는다.

화면 흐름은 TP-6 UI 설계서를 따른다.
  로그인 → 검색 홈 → (물품 등록 / 물품 상세·구매요청 / 마이페이지 / 채팅 / 거래완료)
  관리자(c0) → 통계 / DB 덤프

용어 메모: cno = 회원번호, itemNo = 판매자별 물품 번호, '판매 중/예약 중/거래 완료' = 물품 상태.
"""
import functools
import os

from flask import (Flask, abort, flash, redirect, render_template, request,
                   send_file, session, url_for)
import io

import config
from services import (chat_service, customer_service, dump_service,
                      item_service, purchase_service, stats_service)

app = Flask(__name__)
app.secret_key = config.SECRET_KEY   # 세션(로그인 정보)을 안전하게 서명하는 데 쓰는 키


# --------------------------------------------------------------------------
# 인증 헬퍼
# --------------------------------------------------------------------------
def login_required(view):
    """로그인 안 한 사용자를 막는 '문지기' 데코레이터.

    @login_required 를 붙인 화면은, 세션에 회원번호(cno)가 없으면(=비로그인)
    내용을 보여 주지 않고 로그인 화면으로 돌려보낸다.
    """
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if "cno" not in session:                 # 로그인 흔적이 없으면
            return redirect(url_for("login"))    # 로그인 화면으로
        return view(*args, **kwargs)             # 있으면 원래 화면 실행
    return wrapped


def current_cno():
    """현재 로그인한 사용자의 회원번호를 돌려준다(없으면 None)."""
    return session.get("cno")


@app.context_processor
def inject_user():
    """모든 템플릿(화면)에서 자동으로 쓸 수 있는 공통 값을 넣어 준다.

    덕분에 각 화면이 따로 넘기지 않아도 me(내 번호)·my_nick(내 닉네임)·
    is_admin(관리자 여부)을 바로 쓸 수 있다(상단 메뉴 분기 등에 사용).
    """
    return {
        "me": session.get("cno"),
        "my_nick": session.get("nickname"),
        "is_admin": session.get("cno") == config.ADMIN_CNO,
    }


# --------------------------------------------------------------------------
# 로그인 / 로그아웃
# --------------------------------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def login():
    """로그인 화면(GET) 및 로그인 처리(POST).

    POST 로 아이디·비밀번호가 들어오면 검증하고, 성공하면 세션에 저장한 뒤
    관리자는 통계 화면으로, 일반 회원은 검색 홈으로 보낸다.
    """
    if request.method == "POST":
        cno = request.form.get("cno", "").strip()
        passwd = request.form.get("passwd", "")
        user = customer_service.login(cno, passwd)   # DB 에서 계정 확인
        if not user:
            # 일치하는 계정이 없으면 같은 화면에 경고 문구를 띄운다(TP-6).
            return render_template("login.html", error="회원번호 또는 비밀번호가 일치하지 않습니다.")
        # 로그인 성공 → 세션에 내 정보 기록(다음 요청부터 '로그인 상태'가 유지됨)
        session["cno"] = user["cno"]
        session["nickname"] = user["nickname"]
        if user["cno"] == config.ADMIN_CNO:
            return redirect(url_for("admin_stats"))   # 관리자 전용 첫 화면
        return redirect(url_for("search_home"))       # 일반 회원 첫 화면
    if "cno" in session:                              # 이미 로그인 상태면
        return redirect(url_for("search_home"))       # 로그인 화면을 건너뛴다
    return render_template("login.html")              # 처음 방문 → 로그인 폼


@app.route("/logout")
def logout():
    """로그아웃: 세션을 비워 로그인 정보를 모두 지우고 로그인 화면으로."""
    session.clear()
    return redirect(url_for("login"))


# --------------------------------------------------------------------------
# 물품 검색 홈 (구매자/판매자 공통)
# --------------------------------------------------------------------------
@app.route("/search")
@login_required
def search_home():
    """검색 홈: 제목·카테고리·가격 조건으로 물품을 찾아 목록으로 보여 준다."""
    item_service.expire_reservations()   # 화면을 열 때마다 48시간 지난 예약을 정리

    # URL 쿼리스트링(?title=...&category=...)에서 검색 조건을 뽑아 리스트로 만든다.
    # 각 조건에는 'NOT 체크' 여부(negate)도 함께 담는다.
    conditions = []
    title = request.args.get("title", "").strip()
    if title:
        conditions.append({"field": "title", "value": title,
                           "negate": request.args.get("title_not") == "1"})
    category = request.args.get("category", "").strip()
    if category:
        conditions.append({"field": "category", "value": category,
                           "negate": request.args.get("category_not") == "1"})
    pmin = request.args.get("price_min", "").strip()
    pmax = request.args.get("price_max", "").strip()
    if pmin or pmax:
        conditions.append({"field": "price", "min": pmin or None, "max": pmax or None,
                           "negate": request.args.get("price_not") == "1"})

    # 조건들을 묶는 방식(AND/OR)과 정렬 기준. 이상한 값이 오면 기본값으로 보정한다.
    connector = request.args.get("connector", "AND").upper()
    if connector not in ("AND", "OR"):
        connector = "AND"
    sort = request.args.get("sort", "recent")

    # 실제 검색은 서비스에 맡긴다. 화면에서 보여 줄 '실행된 SQL'도 함께 받는다.
    items, sql = item_service.search(conditions, connector, sort)
    return render_template(
        "search_home.html", items=items, categories=item_service.CATEGORIES,
        f=request.args, connector=connector, sort=sort, sql=sql,
    )


# --------------------------------------------------------------------------
# 물품 등록 (판매자)
# --------------------------------------------------------------------------
@app.route("/items/new", methods=["GET", "POST"])
@login_required
def item_register():
    """물품 등록: GET 은 등록 폼, POST 는 입력값 검증 후 실제 등록."""
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        price = request.form.get("price", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        trade_place = request.form.get("tradePlace", "").strip()

        # 서버측 검증: 제목은 비면 안 되고, 가격은 숫자여야 한다.
        if not title or not price.isdigit():
            return render_template("item_register.html",
                                   categories=item_service.CATEGORIES,
                                   error="유효한 제목, 가격 값을 입력해주세요.",
                                   form=request.form)
        # 업로드된 사진을 최대 3장까지 바이트로 읽어 모은다(BLOB 로 저장될 예정).
        images = []
        for key in ("pic1", "pic2", "pic3"):
            file = request.files.get(key)
            if file and file.filename:           # 실제로 파일이 첨부된 경우만
                images.append(file.read())

        # 카테고리를 안 골랐으면 '기타'로 둔다. 등록 후 그 물품 상세로 이동.
        new_no = item_service.register_item(
            current_cno(), title, description, category or "기타",
            int(price), trade_place, images)
        flash(f"물품이 등록되었습니다. (itemNo={new_no})")
        return redirect(url_for("item_detail", cno=current_cno(), item_no=new_no))
    return render_template("item_register.html", categories=item_service.CATEGORIES, form={})


# --------------------------------------------------------------------------
# 물품 수정 / 삭제 (소유자 전용)
# --------------------------------------------------------------------------
@app.route("/items/<cno>/<int:item_no>/edit", methods=["GET", "POST"])
@login_required
def item_edit(cno, item_no):
    """물품 수정(소유자만). 등록과 같은 검증을 거쳐 텍스트 항목을 갱신한다."""
    if cno != current_cno():           # 내 물품이 아니면 접근 차단
        abort(403)
    item = item_service.get_item(cno, item_no)
    if not item:                       # 없는 물품이면 404
        abort(404)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        price = request.form.get("price", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        trade_place = request.form.get("tradePlace", "").strip()
        if not title or not price.isdigit():   # 등록과 동일한 검증
            return render_template("item_edit.html", item=item,
                                   categories=item_service.CATEGORIES,
                                   error="유효한 제목, 가격 값을 입력해주세요.",
                                   form=request.form)
        item_service.update_item(cno, item_no, title, description,
                                 category or "기타", int(price), trade_place)
        flash("물품 정보가 수정되었습니다.")
        return redirect(url_for("item_detail", cno=cno, item_no=item_no))
    return render_template("item_edit.html", item=item,
                           categories=item_service.CATEGORIES, form={})


@app.route("/items/<cno>/<int:item_no>/delete", methods=["POST"])
@login_required
def item_delete(cno, item_no):
    """물품 삭제(소유자만). 관련 요청·채팅도 함께 지운다(서비스가 처리)."""
    if cno != current_cno():           # 소유자만 삭제 가능
        abort(403)
    item_service.delete_item(cno, item_no)
    flash("물품이 삭제되었습니다.")
    return redirect(url_for("mypage_seller"))


# --------------------------------------------------------------------------
# 물품 상세 + 구매 요청 (구매자) / 요청 목록·승인 (판매자)
# --------------------------------------------------------------------------
@app.route("/items/<cno>/<int:item_no>")
@login_required
def item_detail(cno, item_no):
    """물품 상세 화면. 판매자가 보면 들어온 구매 요청 목록까지 함께 보여 준다."""
    item_service.expire_reservations()
    item = item_service.get_item(cno, item_no)
    if not item:
        abort(404)
    is_seller = (cno == current_cno())   # 이 화면을 보는 사람이 판매자인지
    # 판매자일 때만 요청 목록을 조회한다(구매자에게는 빈 목록).
    requests = purchase_service.requests_for_item(cno, item_no) if is_seller else []
    return render_template("item_detail.html", item=item, is_seller=is_seller, requests=requests)


@app.route("/items/<cno>/<int:item_no>/image/<int:idx>")
def item_image(cno, item_no, idx):
    """물품 사진(BLOB)을 이미지 응답으로 내보낸다. idx 는 1~3(pic1~3)."""
    data = item_service.get_image(cno, item_no, idx)
    if data is None:                     # 해당 사진이 없으면 404
        abort(404)
    # 바이트를 파일처럼 감싸서 이미지로 응답한다.
    return send_file(io.BytesIO(data), mimetype="image/*")


@app.route("/items/<cno>/<int:item_no>/chat", methods=["POST"])
@login_required
def start_chat(cno, item_no):
    """구매자가 물품 상세에서 '1:1 채팅하기'를 누르면 채팅방을 열고(없으면 생성) 입장한다."""
    if cno == current_cno():             # 내 물품엔 내가 채팅을 걸 수 없음
        flash("본인 물품에는 채팅을 시작할 수 없습니다.")
        return redirect(url_for("item_detail", cno=cno, item_no=item_no))
    if not item_service.get_item(cno, item_no):
        flash("존재하지 않는 물품입니다.")
        return redirect(url_for("search_home"))
    # 이미 방이 있으면 그 방, 없으면 새로 만든 방 번호를 받아 입장한다.
    room_no = chat_service.ensure_room(current_cno(), cno, item_no)
    return redirect(url_for("chat_room", room_no=room_no))


@app.route("/items/<cno>/<int:item_no>/request", methods=["POST"])
@login_required
def create_request(cno, item_no):
    """구매 요청 보내기. 본인 물품·판매중 아님·중복 요청 등은 막고 안내 메시지를 띄운다."""
    if cno == current_cno():             # 내 물품에는 요청할 수 없음
        flash("본인 물품에는 구매 요청을 보낼 수 없습니다.")
        return redirect(url_for("item_detail", cno=cno, item_no=item_no))
    item = item_service.get_item(cno, item_no)
    if not item:
        flash("존재하지 않는 물품입니다.")
        return redirect(url_for("search_home"))
    if item["sellStatus"] != "판매 중":   # 예약중·거래완료 물품엔 요청 불가
        flash(f"'{item['sellStatus']}' 상태의 물품에는 구매 요청을 보낼 수 없습니다.")
        return redirect(url_for("item_detail", cno=cno, item_no=item_no))
    req_price = request.form.get("reqPrice", "").strip()
    req_message = request.form.get("reqMessage", "").strip()
    if not req_price.isdigit():
        flash("요청 금액은 숫자로 입력해주세요.")
        return redirect(url_for("item_detail", cno=cno, item_no=item_no))
    try:
        purchase_service.create_request(current_cno(), cno, item_no,
                                        int(req_price), req_message)
        flash("구매 요청을 보냈습니다.")
    except Exception:
        # 같은 물품에 또 요청하면 복합 기본키 위반 → 중복 안내로 처리.
        flash("이미 이 물품에 구매 요청을 보냈습니다.")
    return redirect(url_for("item_detail", cno=cno, item_no=item_no))


@app.route("/items/<cno>/<int:item_no>/approve", methods=["POST"])
@login_required
def approve_request(cno, item_no):
    """판매자가 한 구매 요청을 승인 → 물품이 '예약 중'으로 바뀌고 채팅방으로 이동."""
    if cno != current_cno():             # 판매자(소유자)만 승인 가능
        abort(403)
    buyer = request.form.get("buyer")    # 어떤 구매자의 요청을 승인할지
    try:
        room_no = purchase_service.approve_request(cno, item_no, buyer)
        flash("구매 요청을 승인했습니다. 예약 중 상태로 전환되고 채팅방이 활성화됩니다.")
        return redirect(url_for("chat_room", room_no=room_no))
    except ValueError as e:              # 이미 예약/판매완료 등 → 안내 후 상세로
        flash(str(e))
        return redirect(url_for("item_detail", cno=cno, item_no=item_no))


@app.route("/items/<cno>/<int:item_no>/complete", methods=["POST"])
@login_required
def complete_trade(cno, item_no):
    """거래 완료 처리: 최종 금액을 입력받아 물품을 '거래 완료'로 바꾼다(예약 중일 때만)."""
    if cno != current_cno():
        abort(403)
    final_price = request.form.get("finalPrice", "").strip()
    if not final_price.isdigit():
        flash("올바른 금액을 숫자로만 입력해 주세요.")
        return redirect(request.referrer or url_for("mypage_seller"))
    # 서비스가 1(성공)/0(예약중 아님)을 돌려주므로, 그 결과로 안내를 분기한다.
    ok = item_service.complete_trade(cno, item_no, int(final_price))
    flash("거래가 완료되었습니다." if ok else "예약 중 상태의 물품만 완료할 수 있습니다.")
    return redirect(url_for("mypage_seller"))


@app.route("/items/<cno>/<int:item_no>/force-expire", methods=["POST"])
@login_required
def force_expire(cno, item_no):
    """데모용: 예약 시각을 49시간 전으로 돌려 48h 자동취소를 즉시 시연."""
    if cno != current_cno():
        abort(403)
    item_service.force_expire(cno, item_no)      # 예약 시각을 과거로 조작
    item_service.expire_reservations()           # 곧바로 만료 처리 실행
    flash("48시간 경과 처리: 예약이 취소되고 '판매 중'으로 복귀했습니다.")
    return redirect(url_for("mypage_seller"))


# --------------------------------------------------------------------------
# 마이페이지 (판매자 / 구매자)
# --------------------------------------------------------------------------
@app.route("/mypage/seller")
@login_required
def mypage_seller():
    """판매 마이페이지: 내가 올린 물품과 각 물품에 들어온 구매 요청을 모아 보여 준다."""
    item_service.expire_reservations()
    # 전체 물품을 조회한 뒤 내 회원번호(CNO)인 것만 추린다.
    all_items, _ = item_service.search([], "AND", "recent")
    my_items = [it for it in all_items if it["CNO"] == current_cno()]
    # 내 물품마다 들어온 요청 목록을 붙여 화면으로 넘긴다.
    for it in my_items:
        it["requests"] = purchase_service.requests_for_item(it["CNO"], it["ITEMNO"])
    return render_template("mypage_seller.html", items=my_items)


@app.route("/mypage/buyer")
@login_required
def mypage_buyer():
    """구매 마이페이지: 내가 보낸 구매 요청 이력과 그 물품의 현재 상태를 보여 준다."""
    item_service.expire_reservations()
    reqs = purchase_service.my_requests(current_cno())
    return render_template("mypage_buyer.html", requests=reqs)


# --------------------------------------------------------------------------
# 채팅
# --------------------------------------------------------------------------
@app.route("/chats")
@login_required
def chat_list():
    """채팅 목록: 내가 참여한 방들과 각 방의 안 읽은 메시지 수를 보여 준다."""
    rooms = chat_service.list_rooms(current_cno())
    return render_template("chat_list.html", rooms=rooms)


@app.route("/chats/<int:room_no>")
@login_required
def chat_room(room_no):
    """채팅방 입장. 당사자가 아니면 막고, 입장 시 상대 메시지를 읽음 처리한다."""
    room = chat_service.get_room(room_no, current_cno())
    if not room:                         # 이 방의 당사자가 아니면 접근 차단
        abort(403)
    chat_service.mark_read(room_no, room["role"])   # 입장 시 상대 메시지 읽음 처리
    messages = chat_service.get_messages(room_no)
    return render_template("chat_room.html", room=room, messages=messages)


@app.route("/chats/<int:room_no>/send", methods=["POST"])
@login_required
def chat_send(room_no):
    """메시지 전송. 내용이 있을 때만 보내고, 다시 같은 방으로 돌아온다."""
    room = chat_service.get_room(room_no, current_cno())
    if not room:
        abort(403)
    content = request.form.get("content", "").strip()
    if content:                          # 빈 메시지는 보내지 않는다
        chat_service.send_message(room_no, room["role"], content)
    return redirect(url_for("chat_room", room_no=room_no))


# --------------------------------------------------------------------------
# 관리자(c0): 통계 + DB 덤프
# --------------------------------------------------------------------------
def admin_required(view):
    """관리자 전용 '문지기' 데코레이터: 관리자(c0)가 아니면 403 으로 막는다."""
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("cno") != config.ADMIN_CNO:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


@app.route("/admin/stats")
@login_required
@admin_required
def admin_stats():
    """관리자 통계 화면: 그룹 함수(ROLLUP)와 윈도우 함수 결과 두 표를 보여 준다."""
    g_cols, g_rows = stats_service.group_function_stat()
    w_cols, w_rows = stats_service.window_function_stat()
    return render_template("admin_stats.html",
                           g_cols=g_cols, g_rows=g_rows,
                           w_cols=w_cols, w_rows=w_rows)


@app.route("/admin/db-dump")
@login_required
@admin_required
def admin_db_dump():
    """관리자 'DB 내용' 화면: 5개 테이블의 실제 적재 행을 그대로 출력한다(7-1)."""
    tables = dump_service.dump_all()
    return render_template("db_dump.html", tables=tables)


# --------------------------------------------------------------------------
# 예외/오류 처리 — 기본 오류 화면 대신 안내 페이지를 보여준다 (TP 평가: 예외 처리)
# --------------------------------------------------------------------------
def _render_error(code, message):
    """오류 코드와 안내 문구를 받아 error.html 을 같은 코드로 응답하는 공통 함수."""
    return render_template("error.html", code=code, message=message), code


@app.errorhandler(403)
def err_forbidden(e):
    """403(권한 없음)을 안내 페이지로."""
    return _render_error(403, "접근 권한이 없습니다.")


@app.errorhandler(404)
def err_not_found(e):
    """404(없는 페이지)를 안내 페이지로."""
    return _render_error(404, "요청하신 페이지를 찾을 수 없습니다.")


@app.errorhandler(500)
def err_internal(e):
    """500(서버 내부 오류)을 안내 페이지로."""
    return _render_error(500, "요청을 처리하는 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.")


if __name__ == "__main__":
    # 데모 중에는 디버그 트레이스백 대신 위 500 핸들러가 동작하도록 기본 off.
    # 개발 중 자동 리로드가 필요하면 TP_DEBUG=1 로 실행한다.
    debug = os.getenv("TP_DEBUG", "0") == "1"
    # macOS 는 5000 번 포트를 AirPlay 수신기가 점유하므로(접속 시 AirTunes 가 가로채
    # 정적 파일·화면이 안 뜬다), 충돌이 없는 5001 을 기본값으로 둔다. TP_PORT 로 변경 가능.
    port = int(os.getenv("TP_PORT", "5001"))
    app.run(debug=debug, port=port)
