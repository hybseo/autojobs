# -*- coding: utf-8 -*-
"""
포스코그룹(recruit.posco.com) 채용 수집기.

목록  GET https://recruit.posco.com/h22a01-recruit/H22A1000/list?{파라미터}
상세  https://recruit.posco.com/h22a01-front/H22A1010.html?noticeId={공고번호}

포스코·포스코DX·포스코퓨처엠·포스코인터내셔널 등 계열사 40곳 안팎의
공고가 한곳에 모여 옵니다. 2026-10-01 확인 16건이었습니다.

GET 입니다. POST 가 아닙니다
----------------------------
화면 코드(h22Common.submitAjax)가 POST 처럼 보이고 JSON 본문을 만드는
자리가 있어 POST 로 여러 번 시도했는데 전부 HTTP 500 이 났습니다.
실제로 목록을 부를 때는 GET 이고, 값은 본문이 아니라 주소 뒤에 붙습니다.
2026-09-22 에 이것을 못 찾아 어댑터를 포기했던 적이 있습니다.

    AJAX: true        헤더가 있어야 합니다. 없으면 화면 HTML 이 옵니다.

파라미터
--------
    rowCount, pageSize   한 번에 받을 건수. 100 을 넣으면 전부 옵니다
    currPage, offset     1, 0 고정
    SEARCH_ORDER         s1 (마감순)
    SEARCH_TYPE          빈 값 = 전체
    SEARCH_COMP          빈 값 = 전 계열사. 숫자를 넣으면 그 계열사만
    SEARCH_KEYWORD       빈 값
    SEARCH_VALUE         빈 값

응답
----
    recuList   공고 배열
    summary    상단 숫자(전체/신입/경력 등)

공고 한 건의 칸

    HR_AFTC_MRG_ADOP_NTIC_SUJX   2026년 포스코리튬솔루션(주) 경력직 채용(구매)
    COMPANY_NAME                 포스코리튬솔루션
    RECU_FIELD                   구매/계약
    HR_AFTC_MRG_ADOP_CLTA_TP_TP_NM  전문경력 / 신입 / 연봉계약직
    END_ACTIVE_DATE              2026.10.14
    DDAY                         13
    HR_AFTC_MRG_ADOP_NTIC_ID     707002
    TOT_CNT                      16          전체 건수

게시일이 없습니다
-----------------
목록에 접수 시작일이 없습니다. 지어내지 않고 비웁니다. 마감일은 있어서
사이트가 마감 임박순으로 줄을 세울 수 있습니다.

계열사 거르기
-------------
철강·소재·건설·IT 가 섞여 옵니다. companies.json 의 affiliates 를 적으면
그곳만 담습니다. 비워 두면 전부 담습니다.
"""
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://recruit.posco.com"
LIST_API = BASE + "/h22a01-recruit/H22A1000/list"
LIST_PAGE = BASE + "/h22a01-front/H22A1000.html"
VIEW = BASE + "/h22a01-front/H22A1010.html?noticeId={}"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

DATE = re.compile(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})")


def _get(params):
    """일시적 실패만 몇 초 쉬었다 다시 시도합니다."""
    url = LIST_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        # 이 헤더가 없으면 목록 JSON 대신 화면 HTML 이 옵니다.
        "AJAX": "true",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": LIST_PAGE,
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
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def _date(v):
    m = DATE.search(str(v or ""))
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else ""


def _career(row):
    """'전문경력' '신입' '연봉계약직' 같은 값이 옵니다."""
    t = _text(row.get("HR_AFTC_MRG_ADOP_CLTA_TP_TP_NM"))
    title = _text(row.get("HR_AFTC_MRG_ADOP_NTIC_SUJX"))
    both = f"{t} {title}"
    has_new = "신입" in both
    has_exp = "경력" in both
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
    params = {
        "rowCount": 100,
        "pageSize": 100,
        "currPage": 1,
        "offset": 0,
        "SEARCH_TYPE": "",
        "SEARCH_ORDER": "s1",
        "SEARCH_KEYWORD": "",
        "SEARCH_COMP": "",
        "SEARCH_VALUE": "",
    }
    data = _get(params)
    rows = data.get("recuList") or []
    if not rows:
        print(f"  ! 포스코: 공고 목록이 비어 있습니다. 이 API 는 POST 가 아니라 "
              f"GET 이고 AJAX 헤더가 필요합니다. {LIST_API}")
        return []

    total = int(rows[0].get("TOT_CNT") or len(rows))
    if total > len(rows):
        print(f"  · 포스코: 전체 {total}건 중 {len(rows)}건만 받았습니다. "
              f"rowCount 를 늘리세요")
    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    rows = list_open(company.get("code"))

    want = [_norm(a) for a in (company.get("affiliates") or []) if str(a).strip()]
    if want:
        before = len(rows)
        rows = [x for x in rows
                if any(w in _norm(x.get("COMPANY_NAME")) for w in want)]
        if before != len(rows):
            print(f"      · {name}: 계열사 거르기 {before}건 → {len(rows)}건")

    jobs = []
    for x in rows:
        no = str(x.get("HR_AFTC_MRG_ADOP_NTIC_ID") or "").strip()
        title = _text(x.get("HR_AFTC_MRG_ADOP_NTIC_SUJX"))
        if not no or not title:
            continue

        field = _text(x.get("RECU_FIELD"))
        # 직무가 제목에 없으면 뒤에 붙입니다. 어떤 자리인지 보이게 합니다.
        if field and field not in title:
            title = f"{title} · {field}"

        jobs.append({
            "id": f"posco-{re.sub(r'[^0-9A-Za-z]', '', no)[:20]}",
            "unit": "공고",
            "company": _text(x.get("COMPANY_NAME")) or name,
            "companySlug": slug,
            "title": title,
            # 목록에 근무지가 없습니다. 지어내지 않습니다.
            "location": "",
            "career": _career(x),
            # 목록에 접수 시작일이 없습니다.
            "postedAt": "",
            "closesAt": _date(x.get("END_ACTIVE_DATE")),
            "dday": None,
            "multiRole": False,
            "sourceTitle": "",
            "sourceUrl": VIEW.format(no),
            # 목록에 본문이 없습니다. 원문으로 보냅니다.
            "description": "",
        })
    return jobs
