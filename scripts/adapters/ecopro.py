# -*- coding: utf-8 -*-
"""
에코프로그룹(ecoprorecruit.co.kr) 채용 수집기.

목록  GET https://ecoprorecruit.co.kr/eco_pro/api/user/apply/list
상세  https://ecoprorecruit.co.kr/apply/view/{공고번호}

이차전지 양극재(에코프로비엠)·환경사업(에코프로에이치엔) 등 계열사 공고가
한곳에 모여 옵니다. 2026-10-01 확인 10건이었습니다.

GET 입니다
----------
POST 로 부르면 HTTP 405 가 납니다. 값도 필요 없고 GET 한 번이면 전체가
옵니다. 쪽 나눔이 없습니다.

응답
----
    success      true
    open_count   진행 중 건수
    data         공고 배열

공고 한 건의 칸

    title      [에코프로BM] 구매부문 경력 채용
    company    에코프로비엠
    recType    경력 / 신입 / 신입·경력
    sDate      202609221330        접수 시작(연월일시분)
    eDate      202610052359        접수 마감
    region     근무지(비어 있는 경우가 많습니다)
    status     지원자모집
    annoId     2451487             공고 번호
    content    본문(HTML)

날짜가 열두 자리입니다
----------------------
202610052359 처럼 연월일시분이 붙어 옵니다. 앞 여덟 자리만 끊어 씁니다.

제목에 회사 이름이 또 들어갑니다
--------------------------------
"[에코프로BM] 구매부문 경력 채용" 처럼 말머리가 붙는데, company 칸에
"에코프로비엠" 이 따로 옵니다. 회사명은 company 를 쓰고 제목은 그대로
둡니다. 말머리를 떼면 "구매부문 경력 채용" 만 남아 어느 회사인지 모르는
채로 검색 결과에 섞입니다.
"""
import html
import json
import re
import time
import urllib.error
import urllib.request

BASE = "https://ecoprorecruit.co.kr"
LIST_API = BASE + "/eco_pro/api/user/apply/list"
VIEW = BASE + "/apply/view/{}"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")


def _get():
    """일시적 실패만 몇 초 쉬었다 다시 시도합니다."""
    req = urllib.request.Request(LIST_API, headers={
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": BASE + "/",
    })
    last = None
    for i in range(2):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError:
            raise
        except Exception as e:
            last = e
            if i < 1:
                time.sleep(3)
    raise last


def _text(s):
    s = re.sub(r"<[^>]+>", " ", str(s or ""))
    s = html.unescape(s).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def _date(v):
    """'202610052359' → '2026-10-05'. 앞 여덟 자리만 씁니다."""
    s = re.sub(r"[^0-9]", "", str(v or ""))
    if len(s) < 8:
        return ""
    return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"


def _career(row):
    t = f"{_text(row.get('recType'))} {_text(row.get('title'))}"
    has_new = "신입" in t
    has_exp = "경력" in t
    if has_new and has_exp:
        return "신입/경력"
    if has_exp:
        return "경력"
    if has_new:
        return "신입"
    return "무관"


def _norm(s):
    return re.sub(r"[\s()（）㈜.,·-]|주식회사", "", str(s or "")).lower()


def list_open(code=""):
    """공고 목록. probe 용으로 밖에서도 씁니다."""
    data = _get()
    rows = data.get("data") or []
    if not rows:
        print(f"  ! 에코프로: 공고 목록이 비어 있습니다. 이 API 는 GET 입니다"
              f"(POST 는 405). {LIST_API}")
        return []

    # 모집이 끝난 공고가 섞여 오면 걸러냅니다.
    open_rows = [x for x in rows
                 if str(x.get("openYn") or "Y").upper() != "N"]
    if len(open_rows) != len(rows):
        print(f"  · 에코프로: 진행중 {len(open_rows)}건 (닫힌 공고 "
              f"{len(rows) - len(open_rows)}건 제외)")
    return open_rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    rows = list_open(company.get("code"))

    want = [_norm(a) for a in (company.get("affiliates") or []) if str(a).strip()]
    if want:
        before = len(rows)
        rows = [x for x in rows if any(w in _norm(x.get("company")) for w in want)]
        if before != len(rows):
            print(f"      · {name}: 계열사 거르기 {before}건 → {len(rows)}건")

    jobs = []
    for x in rows:
        no = str(x.get("annoId") or x.get("id") or "").strip()
        title = _text(x.get("title"))
        if not no or not title:
            continue

        body = str(x.get("content") or "")

        jobs.append({
            "id": f"ecopro-{re.sub(r'[^0-9A-Za-z]', '', no)[:20]}",
            "unit": "공고",
            "company": _text(x.get("company")) or name,
            "companySlug": slug,
            "title": title,
            # region 이 비어 오는 경우가 많습니다. 지어내지 않습니다.
            "location": _text(x.get("region")),
            "career": _career(x),
            "postedAt": _date(x.get("sDate")),
            "closesAt": _date(x.get("eDate")),
            "dday": None,
            "multiRole": False,
            "sourceTitle": "",
            "sourceUrl": VIEW.format(no),
            "description": body if len(_text(body)) >= 50 else "",
        })
    return jobs
