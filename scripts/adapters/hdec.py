# -*- coding: utf-8 -*-
"""
현대건설 자체 채용 사이트 수집기 (2026-11-26 대표님 지시로 추가).

  목록  GET https://recruit.hdec.co.kr/v1/apply_list/search01?reClass=&reDtlClass=
  원문  https://recruit.hdec.co.kr/#/Recruit/{RE_NO}

2026-11-26 깃허브 러너에서 확인한 것
------------------------------------
- 채용 화면(#/JobPosting)이 위 목록 API 를 부릅니다. 화면은 헤더 api_key: Bearer 를 붙이는데
  값이 비어 있는 그대로라 비로그인 방문자와 같습니다. 같은 헤더를 보냅니다.
- 응답 {"success":true,"response":[...]} 의 한 줄
    RE_NO        3065                       공고 번호
    TITLE        [건축주택] 골조/가설 … 채용
    RE_CLASS_NM  경력 / 신입 / 인턴
    RE_DTL_CLASS_NM  본사 · 토목현장 …       근무 구분
    RCP_STA_YMD  2026.11.17   RCP_END_YMD 2026.12.04
    STATUS       접수중                     (그날 20건 모두 접수중)
    LOC_SRC_KEYWORD  &#35;본사 &#35;서울      근무지 꼬리표
- 공고 주소는 화면의 「링크 복사」 버튼이 만드는 주소를 그대로 씁니다
  (M4_RecruitCard 의 onGetLink: https://recruit.hdec.co.kr/#/Recruit/${RE_NO}).
- 화면 JOBS 숫자(25개)와 API 건수(20건)가 다른 것은 화면이 상시 채용을 따로 더하기
  때문으로 보입니다(?mode=always). 상시 쪽은 확인 전이라 넣지 않았습니다.

본문 (2026-11-26 추가, 대표님 「2번해」)
----------------------------------------
  상세  POST https://recruit.hdec.co.kr/v1/apply_view/search01?isPrivate=false
        {"RE_NO":"3065","NOTI_SEQ_NO":1}
- 응답의 NOTI_TXT 가 본문입니다. 확인한 3065·2766 둘 다 <img> 한 장뿐이었습니다
  (현대건설은 공고문을 그림으로 올립니다). 글자가 거의 없고 그림만 있으면
  다른 수집기와 같이 multiRole=True(이미지 공고)로 두고 본문은 비웁니다.
- 글자로 된 본문이 오면 그대로 씁니다.
"""
import html
import json
import re
import time
import urllib.request

API = "https://recruit.hdec.co.kr/v1/apply_list/search01?reClass=&reDtlClass="
DETAIL = "https://recruit.hdec.co.kr/v1/apply_view/search01?isPrivate=false"
VIEW = "https://recruit.hdec.co.kr/#/Recruit/{}"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

CAREER = {"경력": "경력", "신입": "신입", "인턴": "무관", "신입/경력": "신입/경력"}


def _get():
    req = urllib.request.Request(API, headers={
        "User-Agent": UA, "Accept": "application/json, text/plain, */*", "api_key": "Bearer"})
    last = None
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r)
        except Exception as e:
            last = e
            time.sleep(2 + i * 2)
    raise last


def _text(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()


def detail(re_no):
    """공고 본문 HTML. 못 가져오면 빈 문자열."""
    body = json.dumps({"RE_NO": str(re_no), "NOTI_SEQ_NO": 1}).encode()
    req = urllib.request.Request(DETAIL, data=body, method="POST", headers={
        "User-Agent": UA, "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json", "api_key": "Bearer"})
    for i in range(2):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                d = json.load(r)
            rows = d.get("response") or []
            return str((rows[0] if rows else {}).get("NOTI_TXT") or "")
        except Exception as e:
            last = e
            time.sleep(2)
    print(f"      ! 현대건설 {re_no} 본문을 못 가져왔습니다 {type(last).__name__}")
    return ""


def _date(s):
    m = re.search(r"(\d{4})\.(\d{2})\.(\d{2})", str(s or ""))
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""


def list_open():
    d = _get()
    rows = d.get("response") or []
    if not d.get("success") or not rows:
        print(f"      ! 현대건설: 목록이 비었거나 실패했습니다. success={d.get('success')} · {API}")
    return [x for x in rows if str(x.get("STATUS", "")).strip() in ("접수중", "")]


def fetch(company):
    name, slug = company["name"], company["slug"]
    jobs = []
    for x in list_open():
        raw = detail(x.get("RE_NO"))
        # 본문이 그림 한 장뿐이면 세부 내용을 읽을 수 없으니 원문으로 보냅니다.
        image_only = len(_text(raw)) < 50 and "<img" in raw.lower()
        loc = " ".join(t.strip() for t in html.unescape(str(x.get("LOC_SRC_KEYWORD") or "")).split("#") if t.strip())
        jobs.append({
            "id": f"hdec-{x.get('RE_NO')}",
            "unit": "공고",
            "company": name,
            "companySlug": slug,
            "title": str(x.get("TITLE") or "").strip(),
            "location": loc,
            "career": CAREER.get(str(x.get("RE_CLASS_NM") or "").strip(), "무관"),
            "postedAt": _date(x.get("RCP_STA_YMD")),
            "closesAt": _date(x.get("RCP_END_YMD")),
            "dday": None,
            "multiRole": image_only,
            "sourceTitle": "",
            "sourceUrl": VIEW.format(x.get("RE_NO")),
            "description": "" if image_only or not _text(raw) else raw,
        })
        time.sleep(0.3)
    return jobs
